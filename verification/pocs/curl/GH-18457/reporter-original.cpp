#include <future>
#include <mutex>
#include <thread>
#include <vector>
#include <curl/curl.h>
// #include <iostream>

static std::mutex& getShareMutex(curl_lock_data data)
{
    static std::vector<std::mutex> mx(CURL_LOCK_DATA_LAST);
    return mx[data];
}

struct LockInfo
{
    CURL* mainEasy = nullptr;
    std::promise<void> p1, p2;
    int hits = 0;
};

static void shareLock(CURL* easy, curl_lock_data data, curl_lock_access access, void* userdata)
{
    getShareMutex(data).lock();
}

static void shareUnlock(CURL* easy, curl_lock_data data, void* userdata)
{
    getShareMutex(data).unlock();
    LockInfo* info = (LockInfo*)userdata;
    // if (easy == info->mainEasy && data == CURL_LOCK_DATA_COOKIE)
    //     std::cout << "hit: " << ++info->hits << std::endl;
    if (easy == info->mainEasy && data == CURL_LOCK_DATA_COOKIE && ++info->hits == 3)
    {
        info->p1.set_value();
        info->p2.get_future().wait();
    }
}

CURL* easyShare(CURLSH* share)
{
    CURL* easy = curl_easy_init();
    curl_easy_setopt(easy, CURLOPT_SHARE, share);
    return easy;
}

void modifyCookies(CURLSH* share, LockInfo& info)
{
    info.p1.get_future().wait();
    CURL* easy = easyShare(share);
    curl_easy_setopt(easy, CURLOPT_COOKIELIST, "ALL");
    curl_easy_cleanup(easy);
    info.p2.set_value();
}

int main()
{
    LockInfo info;
    CURLSH* share = curl_share_init();
    curl_share_setopt(share, CURLSHOPT_USERDATA, &info);
    curl_share_setopt(share, CURLSHOPT_LOCKFUNC, shareLock);
    curl_share_setopt(share, CURLSHOPT_UNLOCKFUNC, shareUnlock);
    curl_share_setopt(share, CURLSHOPT_SHARE, CURL_LOCK_DATA_COOKIE);
    std::thread t(modifyCookies, share, std::ref(info));
    CURL* easy = easyShare(share);
    info.mainEasy = easy;
    curl_easy_setopt(easy, CURLOPT_COOKIEFILE, "");
    curl_easy_setopt(easy, CURLOPT_COOKIELIST, "example.com\tFALSE\t/\tFALSE\t0\tfoo\tbar");
    curl_easy_setopt(easy, CURLOPT_URL, "http://example.com/");
    curl_easy_setopt(easy, CURLOPT_CUSTOMREQUEST, "GET");
    curl_easy_setopt(easy, CURLOPT_TCP_KEEPALIVE, 1L);
    curl_easy_setopt(easy, CURLOPT_TCP_KEEPIDLE, 60L);
    curl_easy_setopt(easy, CURLOPT_TCP_KEEPINTVL, 60L);
    curl_easy_perform(easy);
    curl_easy_cleanup(easy);
    t.join();
}
