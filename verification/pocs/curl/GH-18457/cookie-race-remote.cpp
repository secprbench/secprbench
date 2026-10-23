#include <curl/curl.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <future>
#include <mutex>
#include <string>
#include <thread>

struct LockInfo {
  CURL* main_easy = nullptr;
  std::promise<void> begin_replace;
  std::future<void> begin_future = begin_replace.get_future();
  std::promise<void> replace_done;
  std::future<void> done_future = replace_done.get_future();
  int main_cookie_unlocks = 0;
  int pause_at = 3;
  bool paused = false;
};

static std::mutex cookie_lock;

static void share_lock(CURL*, curl_lock_data, curl_lock_access, void*) {
  cookie_lock.lock();
}

static void share_unlock(CURL* easy, curl_lock_data data, void* user) {
  auto* info = static_cast<LockInfo*>(user);
  cookie_lock.unlock();
  if(easy == info->main_easy && data == CURL_LOCK_DATA_COOKIE) {
    int n = ++info->main_cookie_unlocks;
    std::fprintf(stderr, "MAIN_COOKIE_UNLOCK=%d\n", n);
    if(n == info->pause_at) {
      info->paused = true;
      info->begin_replace.set_value();
      if(info->done_future.wait_for(std::chrono::seconds(10)) != std::future_status::ready)
        std::fprintf(stderr, "REPLACE_TIMEOUT\n");
      else
        std::fprintf(stderr, "REPLACE_COMPLETED_BEFORE_MAIN_CONTINUES\n");
    }
  }
}

static size_t discard(char*, size_t a, size_t b, void*) { return a * b; }

static CURL* make_easy(CURLSH* share, curl_slist* resolve, const std::string& url) {
  CURL* e = curl_easy_init();
  curl_easy_setopt(e, CURLOPT_SHARE, share);
  curl_easy_setopt(e, CURLOPT_COOKIEFILE, "");
  curl_easy_setopt(e, CURLOPT_URL, url.c_str());
  curl_easy_setopt(e, CURLOPT_RESOLVE, resolve);
  curl_easy_setopt(e, CURLOPT_IPRESOLVE, CURL_IPRESOLVE_V4);
  curl_easy_setopt(e, CURLOPT_PROXY, "");
  curl_easy_setopt(e, CURLOPT_NOSIGNAL, 1L);
  curl_easy_setopt(e, CURLOPT_WRITEFUNCTION, discard);
  curl_easy_setopt(e, CURLOPT_TIMEOUT, 8L);
  return e;
}

int main(int argc, char** argv) {
  if(argc != 3) return 2;
  int port = std::stoi(argv[1]);
  int pause_at = std::stoi(argv[2]);
  curl_global_init(CURL_GLOBAL_DEFAULT);
  LockInfo info;
  info.pause_at = pause_at;
  CURLSH* share = curl_share_init();
  curl_share_setopt(share, CURLSHOPT_USERDATA, &info);
  curl_share_setopt(share, CURLSHOPT_LOCKFUNC, share_lock);
  curl_share_setopt(share, CURLSHOPT_UNLOCKFUNC, share_unlock);
  curl_share_setopt(share, CURLSHOPT_SHARE, CURL_LOCK_DATA_COOKIE);
  std::string base = "http://race.test:" + std::to_string(port);
  std::string resolve_line = "race.test:" + std::to_string(port) + ":127.0.0.1";
  curl_slist* resolve = curl_slist_append(nullptr, resolve_line.c_str());

  CURL* main_easy = make_easy(share, resolve, base + "/main");
  info.main_easy = main_easy;
  curl_easy_setopt(main_easy, CURLOPT_COOKIELIST,
                   "race.test\tFALSE\t/\tFALSE\t0\tfoo\told");
  std::thread replace([&]() {
    if(info.begin_future.wait_for(std::chrono::seconds(10)) != std::future_status::ready) {
      std::fprintf(stderr, "BEGIN_TIMEOUT\n");
      return;
    }
    CURL* other = make_easy(share, resolve, base + "/replace");
    CURLcode rc = curl_easy_perform(other);
    long status = 0;
    curl_easy_getinfo(other, CURLINFO_RESPONSE_CODE, &status);
    std::fprintf(stderr, "REPLACE_RESULT=%d HTTP=%ld\n", static_cast<int>(rc), status);
    curl_easy_cleanup(other);
    info.replace_done.set_value();
  });

  CURLcode rc = curl_easy_perform(main_easy);
  long status = 0;
  curl_easy_getinfo(main_easy, CURLINFO_RESPONSE_CODE, &status);
  std::fprintf(stderr, "MAIN_RESULT=%d HTTP=%ld PAUSED=%d\n",
               static_cast<int>(rc), status, static_cast<int>(info.paused));
  replace.join();
  curl_easy_cleanup(main_easy);
  curl_slist_free_all(resolve);
  curl_share_cleanup(share);
  curl_global_cleanup();
  return (rc == CURLE_OK && status == 200 && info.paused) ? 0 : 1;
}
