#include <cstring>
#include <curl/curl.h>
#include <iostream>
#include <inttypes.h>
#include <future>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <vector>
#include <unistd.h>

#include <cstdlib>
#include <list>
#include <mutex>
#include <condition_variable>
#include <cassert>
#include <optional>
#include <utility>

/**
 * Abstract source of binary data.
 */
struct Source
{
    virtual ~Source() {}

    /**
     * Store exactly ‘len’ bytes in the buffer pointed to by ‘data’.
     * It blocks until all the requested data is available, or throws
     * an error if it is not going to be available.
     */
    void operator()(char * data, size_t len);

    /**
     * Store up to ‘len’ in the buffer pointed to by ‘data’, and
     * return the number of bytes stored.  It blocks until at least
     * one byte is available.
     *
     * Should not return 0 (generally you want to throw EndOfFile), but nothing
     * stops that.
     *
     * \throws EndOfFile if there is no more data.
     */
    virtual size_t read(char * data, size_t len) = 0;

    virtual bool good()
    {
        return true;
    }
};

/**
 * This template class ensures synchronized access to a value of type
 * T. It is used as follows:
 *
 *   struct Data { int x; ... };
 *
 *   Sync<Data> data;
 *
 *   {
 *     auto data_(data.lock());
 *     data_->x = 123;
 *   }
 *
 * Here, "data" is automatically unlocked when "data_" goes out of
 * scope.
 */
template<class T, class M = std::mutex>
class Sync
{
private:
    M mutex;
    T data;

public:

    Sync() {}
    Sync(const T & data) : data(data) {}
    Sync(T && data) noexcept : data(std::move(data)) {}

    template<typename... Args>
    Sync(std::in_place_t, Args &&... args) : data(std::forward<Args>(args)...)
    {
    }

    class Lock
    {
    protected:
        // Non-owning pointer. This would be an
        // optional<reference_wrapper<Sync>> if it didn't break gdb accessing
        // Lock values (as of 2024-06-15, gdb 14.2)
        Sync * s;
        std::unique_lock<M> lk;
        friend Sync;
        Lock(Sync & s) : s(&s), lk(s.mutex) {}
        Lock(Sync & s, std::unique_lock<M> lk) : s(&s), lk(std::move(lk)) {}

        inline void checkLockingInvariants()
        {
            assert(s);
            assert(lk.owns_lock());
        }

    public:
        Lock(Lock && l) : s(l.s), lk(std::move(l.lk))
        {
            l.s = nullptr;
        }

        Lock(const Lock & l) = delete;

        ~Lock() = default;

        T * operator->()
        {
            checkLockingInvariants();
            return &s->data;
        }

        T & operator*()
        {
            checkLockingInvariants();
            return s->data;
        }

        /**
         * Wait for the given condition variable with no timeout.
         *
         * May spuriously wake up.
         */
        void wait(std::condition_variable & cv)
        {
            checkLockingInvariants();
            cv.wait(lk);
        }
    };

    /**
     * Lock this Sync and return a RAII guard object.
     */
    Lock lock()
    {
        return Lock(*this);
    }

    std::optional<Lock> tryLock()
    {
        if (std::unique_lock lk(mutex, std::try_to_lock_t{}); lk.owns_lock()) {
            return Lock{*this, std::move(lk)};
        } else {
            return std::nullopt;
        }
    }
};

struct curlFileTransfer2
{
    std::unique_ptr<CURLM, decltype([](auto * m) { curl_multi_cleanup(m); })> curlm;

    const unsigned int baseRetryTimeMs;

    void wakeup()
    {
        if (auto mc = curl_multi_wakeup(curlm.get())) {
            std::ostringstream err;
            err << "unexpected error from curl_multi_wakeup(): " << curl_multi_strerror(mc);
            throw std::runtime_error(err.str());
        }
    }

    void stopWorkerThread()
    {
        /* Signal the worker thread to exit. */
        {
            auto state(state_.lock());
            state->quit = true;
        }
        wakeup();
    }

    struct TransferItem
    {
        struct DownloadState
        {
            bool done = false;
            std::exception_ptr exc;
            std::string data;
        };

        std::string uri;
        Sync<DownloadState> downloadState;
        std::condition_variable downloadEvent;
        bool headersDone = false, metadataReturned = false;
        std::promise<void> metadataPromise;

        uint64_t bodySize = 0;

        std::unique_ptr<curl_slist, decltype([](auto * s) { curl_slist_free_all(s); })>
            requestHeaders;
        std::unique_ptr<CURL, decltype([](auto * c) { curl_easy_cleanup(c); })> req;
        // buffer to accompany the `req` above
        char errbuf[CURL_ERROR_SIZE];

        inline static const std::set<long>
            successfulStatuses{200, 201, 204, 206, 304, 0 /* other protocol */};
        void appendCurlHeader(std::string_view name, std::string_view value)
        {
            std::ostringstream ss;
            ss << name << ": " << value;
            auto header = ss.str();
            if (auto next = curl_slist_append(requestHeaders.get(), header.c_str())) {
                (void) requestHeaders.release(); // next now owns this pointer
                requestHeaders.reset(next);
            } else {
                abort();
            }
        }

        TransferItem(const std::string & uri) : uri(uri), req(curl_easy_init())
        {
            if (req == nullptr) {
                abort();
            }

            curl_easy_setopt(req.get(), CURLOPT_VERBOSE, 1);
            curl_easy_setopt(req.get(), CURLOPT_DEBUGFUNCTION, TransferItem::debugCallback);

            curl_easy_setopt(req.get(), CURLOPT_URL, uri.c_str());
            curl_easy_setopt(req.get(), CURLOPT_FOLLOWLOCATION, 1L);

            curl_easy_setopt(
                req.get(), CURLOPT_ACCEPT_ENCODING, nullptr
            ); // Disable internal handling
            appendCurlHeader("Accept-Encoding", "zstd");

            curl_easy_setopt(req.get(), CURLOPT_MAXREDIRS, 10);
            curl_easy_setopt(req.get(), CURLOPT_NOSIGNAL, 1);
            curl_easy_setopt(req.get(), CURLOPT_PIPEWAIT, 1);
            curl_easy_setopt(req.get(), CURLOPT_HTTP_VERSION, CURL_HTTP_VERSION_2TLS);
            curl_easy_setopt(req.get(), CURLOPT_WRITEFUNCTION, TransferItem::writeCallbackWrapper);
            curl_easy_setopt(req.get(), CURLOPT_WRITEDATA, this);

            curl_easy_setopt(req.get(), CURLOPT_NOPROGRESS, 1);

            curl_easy_setopt(req.get(), CURLOPT_ERRORBUFFER, errbuf);
            errbuf[0] = 0;

            curl_easy_setopt(req.get(), CURLOPT_PROTOCOLS_STR, "http,https,ftp,ftps");

            curl_easy_setopt(req.get(), CURLOPT_HTTPHEADER, requestHeaders.get());
            // This is a repro, we don't need any of that "security"
            curl_easy_setopt(req.get(), CURLOPT_SSL_VERIFYPEER, 0);
        }

        void maybeFinishSetup()
        {
            if (headersDone) {
                return;
            }

            metadataPromise.set_value();
            metadataReturned = true;

            headersDone = true;
        }

        std::exception_ptr callbackException;

        size_t writeCallback(void * contents, size_t size, size_t nmemb)
        {
            const size_t realSize = size * nmemb;

            try {
                maybeFinishSetup();

                auto state = downloadState.lock();

                // when the buffer is full (as determined by a historical magic value) we
                // pause the transfer and wait for the receiver to unpause it when ready.
                if (state->data.size() > 1024 * 1024) {
                    std::cout << "!! PAUSE !!" << this->uri << "\n";
                    return CURL_WRITEFUNC_PAUSE;
                }

                state->data.append(static_cast<const char *>(contents), realSize);
                downloadEvent.notify_all();
                bodySize += realSize;
                return realSize;
            } catch (...) {
                callbackException = std::current_exception();
                return CURL_WRITEFUNC_ERROR;
            }
        }

        static size_t writeCallbackWrapper(void * contents, size_t size, size_t nmemb, void * userp)
        {
            return static_cast<TransferItem *>(userp)->writeCallback(contents, size, nmemb);
        }

        static int
        debugCallback(CURL * handle, curl_infotype type, char * data, size_t size, void * userptr)
        {
            if (type == CURLINFO_TEXT) {
                std::cout << "curl: " << std::string(data, size);
            }
            return 0;
        }

        void finish(CURLcode code)
        {
            maybeFinishSetup();

            printf(
                "finished download of '%s'; curl status = %d, body = %" PRIu64 "d bytes\n",
                uri.c_str(),
                code,
                bodySize
            );

            if (callbackException) {
                abort();
            }

            else if (code == CURLE_OK)
            {
                downloadState.lock()->done = true;
                downloadEvent.notify_all();
            } else {
                std::cout << "foo\n";
            }
        }
    };

    void unpause(const std::shared_ptr<TransferItem> & transfer)
    {
        auto lock = state_.lock();
        lock->unpause.push_back(transfer);
        wakeup();
    }

    struct State
    {
        bool quit = false;
        std::vector<std::shared_ptr<TransferItem>> incoming;
        std::vector<std::shared_ptr<TransferItem>> unpause;
    };

    Sync<State> state_;

    std::thread workerThread;

    void workerThreadEntry()
    {
        workerThreadMain();
        // The original repro unconditionally exited 1 on normal shutdown.
        // Return normally so the host oracle can use process status.
    }

    curlFileTransfer2(unsigned int baseRetryTimeMs)
        : curlm(curl_multi_init())
        , baseRetryTimeMs(baseRetryTimeMs)
    {
        if (curlm == nullptr) {
            abort();
        }

        static std::once_flag globalInit;
        std::call_once(globalInit, curl_global_init, CURL_GLOBAL_ALL);

        curl_multi_setopt(curlm.get(), CURLMOPT_PIPELINING, CURLPIPE_MULTIPLEX);
        curl_multi_setopt(curlm.get(), CURLMOPT_MAX_TOTAL_CONNECTIONS, 25);

        workerThread = std::thread([&]() { workerThreadEntry(); });
    }

    ~curlFileTransfer2()
    {
        stopWorkerThread();
        workerThread.join();
    }

    void workerThreadMain()
    {
        std::map<CURL *, std::shared_ptr<TransferItem>> items;

        bool quit = false;

        while (true) {
            /* Let curl do its thing. */
            int running;
            CURLMcode mc = curl_multi_perform(curlm.get(), &running);
            if (mc != CURLM_OK) {
                std::ostringstream err;
                err << "unexpected error from curl_multi_perform():" << curl_multi_strerror(mc);
                throw std::runtime_error(err.str());
            }

            /* Set the promises of any finished requests. */
            CURLMsg * msg;
            int left;
            while ((msg = curl_multi_info_read(curlm.get(), &left))) {
                if (msg->msg == CURLMSG_DONE) {
                    auto i = items.find(msg->easy_handle);
                    assert(i != items.end());
                    i->second->finish(msg->data.result);
                    curl_multi_remove_handle(curlm.get(), i->second->req.get());
                    items.erase(i);
                }
            }

            // only exit when all transfers are done (which will happen through the
            // progress callback issuing an abort in the case of user interruption)
            if (items.empty() && quit) {
                break;
            }

            /* Wait for activity, including wakeup events. */
            mc = curl_multi_poll(curlm.get(), nullptr, 0, 1000, nullptr);
            if (mc != CURLM_OK) {
                std::ostringstream err;
                err << "unexpected error from curl_multi_poll(): " << curl_multi_strerror(mc);
                throw std::runtime_error(err.str());
            }

            /* Add new curl requests from the incoming requests queue,
               except for requests that are embargoed (waiting for a
               retry timeout to expire). */

            std::vector<std::shared_ptr<TransferItem>> incoming;

            {
                auto unpause = [&] { return std::move(state_.lock()->unpause); }();
                for (auto & item : unpause) {
                    std::cout << "!! UNPAUSE !! " << item.get() << " uri = " << item->uri << "\n";
                    curl_easy_pause(item->req.get(), CURLPAUSE_CONT);
                }
            }

            {
                auto state(state_.lock());
                incoming = std::move(state->incoming);
                quit = state->quit;
            }

            for (auto & item : incoming) {
                std::cout << "starting download of " << item->uri << "\n";
                curl_multi_add_handle(curlm.get(), item->req.get());
                items[item->req.get()] = item;
            }
        }

        std::cout << "download thread shutting down\n";
    }

    void enqueueItem(std::shared_ptr<TransferItem> item)
    {
        {
            auto state(state_.lock());
            if (state->quit) {
                abort();
            }
            state->incoming.push_back(item);
        }
        wakeup();
    }

    std::unique_ptr<Source> enqueueFileTransfer(const std::string & uri)
    {
        auto source = std::make_unique<TransferSource>(*this, uri);
        source->awaitData();
        return std::move(source);
    }

    struct TransferSource : Source
    {
        curlFileTransfer2 & parent;
        std::string uri;

        std::shared_ptr<TransferItem> transfer;
        std::string chunk;
        std::string_view buffered;

        TransferSource(curlFileTransfer2 & parent, const std::string & uri)
            : parent(parent)
            , uri(uri)
        {
            startTransfer(uri);
        }

        void startTransfer(const std::string & uri)
        {
            transfer = std::make_shared<TransferItem>(uri);
            parent.enqueueItem(transfer);
            return transfer->metadataPromise.get_future().get();
        }

        bool awaitData()
        {
            auto waitForData = [&] {
                /* Grab data if available, otherwise wait for the download
                   thread to wake us up. */
                while (buffered.empty()) {
                    auto state(transfer->downloadState.lock());

                    if (!state->data.empty()) {
                        chunk = std::move(state->data);
                        buffered = chunk;
                        parent.unpause(transfer);
                    } else if (state->done) {
                        return false;
                    } else {
                        parent.unpause(transfer);
                        state.wait(transfer->downloadEvent);
                    }
                }

                return true;
            };
            return waitForData();
        }

        size_t read(char * data, size_t len) override
        {
            size_t total = 0;
            while (total < len && awaitData()) {
                const auto available = std::min(len - total, buffered.size());
                memcpy(data + total, buffered.data(), available);
                buffered.remove_prefix(available);
                total += available;
            }

            if (total == 0) {
                throw std::runtime_error("transfer finished");
            }

            return total;
        }
    };

    std::unique_ptr<Source> download(const std::string & uri)
    {
        return enqueueFileTransfer(uri);
    }
};

std::shared_ptr<curlFileTransfer2> makeCurlFileTransfer2(std::optional<unsigned int> baseRetryTimeMs
)
{
    return std::make_shared<curlFileTransfer2>(baseRetryTimeMs.value_or(250));
}

volatile size_t recvd1 = 0;
volatile size_t recvd2 = 0;

int main()
{
    auto ft = makeCurlFileTransfer2(0);
    auto a = ft->download("https://localhost:18755/fast");
    auto b = ft->download("https://localhost:18755/slow");

    auto af = std::async(std::launch::async, [&] {
        char c[1024];
        for (;;) {
            recvd1 += a->read(c, sizeof(c));
        }
    });
    auto bf = std::async(std::launch::async, [&] {
        char c[1024];
        for (;;) {
            recvd2 += b->read(c, sizeof(c));
            usleep(1000);
        }
    });

    // Observation only: preserve the reporter's transfer and reader behavior.
    std::thread([] {
        for (int i = 0; i < 45; ++i) {
            fprintf(stderr, "PROGRESS recvd1=%zu recvd2=%zu\n", recvd1, recvd2);
            usleep(1000000);
        }
    }).detach();
    return 0;
}
