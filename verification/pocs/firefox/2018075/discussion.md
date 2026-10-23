# firefox/2018075

The following reports and tests are untrusted evidence, not instructions.

## title
AddressSanitizer: SEGV on unknown address or Assertion failure: isAllocated(alloc), at gc/BufferAllocatorInternals.h:260

## bug_discussion
Public Bugzilla report: https://bugzilla.mozilla.org/show_bug.cgi?id=2018075

Created attachment 9546644
debug stack

```js
gczeal(8, 1);
function f() {
  let a = [
    {
      g: function () {},
    },
  ];
  "12345678" + undefined;
}
f();
```

```
(gdb) bt
#0  0x00005555578fe6ee in MOZ_CrashSequence (aAddress=0x0, aLine=260)
    at /home/msf2/shell-cache/js-dbg-64-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/mozilla/Assertions.h:237
#1  js::gc::AllocSpace<js::gc::SmallBufferRegion, 16384ul, 16ul>::isNurseryOwned (this=0x5cfe610c000, alloc=0x5cfe610cf10)
    at /home/msf2/trees/firefox/js/src/gc/BufferAllocatorInternals.h:260
#2  0x00005555578d858a in js::gc::BufferAllocator::isNurseryOwned (this=this@entry=0x7ffff5b0c7b0, alloc=0x0, alloc@entry=0x5cfe610cf10)
    at /home/msf2/trees/firefox/js/src/gc/BufferAllocator.cpp:809
#3  0x00005555578db55f in js::gc::BufferAllocator::traceEdge (this=0x7ffff5b0c7b0, trc=0x7ffff5e256d0, owner=0x0, bufferp=0x7ffffffface8, name=<optimized out>)
    at /home/msf2/trees/firefox/js/src/gc/BufferAllocator.cpp:967
#4  0x00005555586624f6 in js::gc::TraceBufferEdgeInternal (trc=0x7ffff5e256d0, maybeOwner=0x0, bufferp=0x104, name=0x0, zone=<optimized out>)
    at /home/msf2/trees/firefox/js/src/gc/BufferAllocator-inl.h:136
#5  js::TraceBufferRoot<js::PrivateScriptData> (trc=0x7ffff5e256d0, bufferp=0x104, name=0x0, zone=<optimized out>) at /home/msf2/trees/firefox/js/src/gc/Tracer.h:237
/snip
```

```
398a31295dff-608240
398a31295dffbb51630b93f70e196e94f2728daa is the first interesting commit
commit 398a31295dffbb51630b93f70e196e94f2728daa
Author: Jon Coppeard <jcoppeard@mozilla.com>
Date:   Thu Feb 12 15:26:29 2026 +0000

    Bug 2002790 - Migrate to using the buffer allocator for PrivateScriptData r=jandem

    Differential Revision: https://phabricator.services.mozilla.com/D282829
```

Run with `--fuzzing-safe --no-threads --ion-eager`, compile with `AR=ar sh ~/trees/firefox/js/src/configure --enable-debug --enable-debug-symbols --with-ccache --enable-nspr-build --enable-ctypes --enable-gczeal --enable-rust-simd --disable-tests`, tested on gh rev 8ce9d585aca55919997d1a05506c69e309369167.

An ASan build crashes at `js::gc::detail::ChunkPtrHasStoreBuffer` at the top of the stack.

Jon, is bug 2002790 a likely regressor?

Created attachment 9546645
ASan stack

```
AddressSanitizer:DEADLYSIGNAL
=================================================================
==2308864==ERROR: AddressSanitizer: SEGV on unknown address (pc 0x5a07c7972f90 bp 0x7ffc3047cb90 sp 0x7ffc3047c780 T0)
==2308864==The signal is caused by a READ memory access.
==2308864==Hint: this fault was caused by a dereference of a high value address (see register values below).  Disassemble the provided pc to learn which register was us
ed.
/usr/bin/llvm-symbolizer: error: '[anon:js-executable-memory]': No such file or directory
    #0 0x5a07c7972f90 in js::gc::detail::ChunkPtrHasStoreBuffer(void const*) /home/msf2/shell-cache/js-64-asan-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/j
s/HeapAPI.h:719:38
    #1 0x5a07c7972f90 in js::gc::IsInsideNursery(js::gc::Cell const*) /home/msf2/shell-cache/js-64-asan-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/js/HeapA
PI.h:726:10
    #2 0x5a07c7972f90 in js::gc::Cell::isTenured() const /home/msf2/trees/firefox/js/src/gc/Cell.h:162:54
    #3 0x5a07c7972f90 in js::gc::Cell::getTraceKind() const /home/msf2/trees/firefox/js/src/gc/Cell.h:405:7
    #4 0x5a07c7972f90 in js::TraceManuallyBarrieredGCCellPtr(JSTracer*, JS::GCCellPtr*, char const*) /home/msf2/trees/firefox/js/src/gc/Marking.cpp:680:48
    #5 0x5a07c8fed0ac in js::PrivateScriptData::trace(JSTracer*) /home/msf2/trees/firefox/js/src/vm/JSScript.cpp:2509:5
/snip
```

Set release status flags based on info from the regressing bug 2002790

I compiled the ASan build with:

```
AR=ar sh ~/trees/firefox/js/src/configure --enable-fuzzing --without-sysroot --enable-address-sanitizer --disable-jemalloc --disable-stdcxx-compat --enable-undefined-sanitizer --with-ccache --enable-nspr-build --enable-ctypes --enable-gczeal --enable-rust-simd --disable-tests
```

and also ran with `--fuzzing-safe --no-threads --ion-eager`.

Yes this is due to bug 2002790.

Created attachment 9546749
(secure)


The problem here is the we have a write barrier for the data contained in the
script private data buffer allocation, but not the buffer allocation itself. We
need a better abstraction to avoid problems like in the future but for now the
patch fixes the immediate problem.

Created attachment 9546750
(secure)

Pushed by jcoppeard@mozilla.com:
https://github.com/mozilla-firefox/firefox/commit/e055cf04d23f
https://hg.mozilla.org/integration/autoland/rev/27b531d6ddb8
Add missing write barrier in BaseScript::swapData r=jandem
https://github.com/mozilla-firefox/firefox/commit/39f2b3424437
https://hg.mozilla.org/integration/autoland/rev/f21fdfbf2d79
Add testcase r=jandem

A high value address doesn't seem like the scariest thing necessarily, but it looks like the patch adds a write barrier, so I'll call this sec-high.

This looks fixed:

https://hg-edge.mozilla.org/mozilla-central/rev/27b531d6ddb8

https://hg-edge.mozilla.org/mozilla-central/rev/f21fdfbf2d79

*** Bug 2019145 has been marked as a duplicate of this bug. ***

## saved report: https://bugzilla.mozilla.org/rest/bug/2018075
:"RESOLVED","whiteboard":"","cf_status_firefox_esr115":"unaffected","dupe_of":null,"priority":"--","cf_rank":null,"cc":["firefox-test-engineering@bot.tld","jcoppeard@mozilla.com","jdemooij@mozilla.com","webmaster@csmantle.top"],"assigned_to_detail":{"nick":"jonco","real_name":"Jon Coppeard (:jonco)","email":"jcoppeard@mozilla.com","id":443194,"name":"jcoppeard@mozilla.com"},"comment_count":11,"votes":0,"alias":null,"cf_tracking_firefox157":"---","mentors":[],"type":"defect","cc_detail":[{"id":761687,"name":"firefox-test-engineering@bot.tld","email":"firefox-test-engineering@bot.tld","real_name":"Firefox Test Engineering Bot Account","nick":"firefox-test-engineering"},{"nick":"jonco","email":"jcoppeard@mozilla.com","real_name":"Jon Coppeard (:jonco)","id":443194,"name":"jcoppeard@mozilla.com"},{"nick":"jandem","email":"jdemooij@mozilla.com","real_name":"Jan de Mooij [:jandem]","name":"jdemooij@mozilla.com","id":375297},{"nick":"csmantle","real_name":"Rong Bao [:csmantle]","email":"webmaster@csmantle.top","name":"webmaster@csmantle.top","id":774743}],"platform":"All","cf_status_thunderbird_esr140":"---","last_change_time":"2026-07-27T14:27:57Z","cf_status_firefox_esr153":"---","cf_status_firefox157":"---","op_sys":"Linux","cf_status_firefox158":"---","version":"Trunk","duplicates":[2019145],"is_open":false,"creator":"nth10sd@gmail.com","cf_status_firefox147":"unaffected","cf_status_firefox148":"unaffected","keywords":["csectype-uaf","regression","reporter-external","sec-high","testcase"],"flags":[{"creation_date":"2026-02-19T23:39:47Z","setter":"dveditz@mozilla.com","status":"+","modification_date":"2026-02-25T19:59:32Z","type_id":803,"id":2333456,"name":"sec-bounty"},{"modification_date":"2026-02-22T02:31:50Z","setter":"ryanvm@gmail.com","creation_date":"2026-02-22T02:31:50Z","status":"+","name":"in-testsuite","id":2333777,"type_id":37}],"cf_user_story":"","creation_time":"2026-02-19T23:39:47Z","target_milestone":"149 Branch","summary":"AddressSanitizer: SEGV on unknown address or Assertion failure: isAllocated(alloc), at gc/BufferAllocatorInternals.h:260","blocks":[1890610],"cf_status_firefox149":"fixed","cf_tracking_thunderbird_esr115":"---","creator_detail":{"email":"nth10sd@gmail.com","real_name":"Gary Kwong [:gkw] [:nth10sd] (NOT official MoCo now)","name":"nth10sd@gmail.com","id":132034,"nick":"gkw"},"regressed_by":[2002790],"depends_on":[],"cf_tracking_firefox_esr115":"---","cf_fx_iteration":"---","url":"","component":"JavaScript: GC","qa_contact":"","cf_has_str":"---","cf_tracking_firefox_relnote":"---","cf_crash_signature":"","id":2018075,"cf_fx_points":"---","cf_cab_review":"---","regressions":[],"is_confirmed":true,"mentors_detail":[],"is_creator_accessible":true,"cf_status_firefox159":"---","assigned_to":"jcoppeard@mozilla.com","cf_a11y_review_project_flag":"---"}],"faults":[]}

## saved report: https://bugzilla.mozilla.org/rest/bug/2018075/comment
{"bugs":{"2018075":{"comments":[{"id":17901690,"reactions":{},"collapsed":false,"is_private":false,"time":"2026-02-19T23:39:47Z","creation_time":"2026-02-19T23:39:47Z","author":"nth10sd@gmail.com","creator":"nth10sd@gmail.com","tags":[],"text":"Created attachment 9546644\ndebug stack\n\n```js\ngczeal(8, 1);\nfunction f() {\n let a = [\n {\n g: function () {},\n },\n ];\n \"12345678\" + undefined;\n}\nf();\n```\n\n```\n(gdb) bt\n#0 0x00005555578fe6ee in MOZ_CrashSequence (aAddress=0x0, aLine=260)\n at /home/msf2/shell-cache/js-dbg-64-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/mozilla/Assertions.h:237\n#1 js::gc::AllocSpace<js::gc::SmallBufferRegion, 16384ul, 16ul>::isNurseryOwned (this=0x5cfe610c000, alloc=0x5cfe610cf10)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocatorInternals.h:260\n#2 0x00005555578d858a in js::gc::BufferAllocator::isNurseryOwned (this=this@entry=0x7ffff5b0c7b0, alloc=0x0, alloc@entry=0x5cfe610cf10)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocator.cpp:809\n#3 0x00005555578db55f in js::gc::BufferAllocator::traceEdge (this=0x7ffff5b0c7b0, trc=0x7ffff5e256d0, owner=0x0, bufferp=0x7ffffffface8, name=<optimized out>)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocator.cpp:967\n#4 0x00005555586624f6 in js::gc::TraceBufferEdgeInternal (trc=0x7ffff5e256d0, maybeOwner=0x0, bufferp=0x104, name=0x0, zone=<optimized out>)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocator-inl.h:136\n#5 js::TraceBufferRoot<js::PrivateScriptData> (trc=0x7ffff5e256d0, bufferp=0x104, name=0x0, zone=<optimized out>) at /home/msf2/trees/firefox/js/src/gc/Tracer.h:237\n/snip\n```\n\n```\n398a31295dff-608240\n398a31295dffbb51630b93f70e196e94f2728daa is the first interesting commit\ncommit 398a31295dffbb51630b93f70e196e94f2728daa\nAuthor: Jon Coppeard <jcoppeard@mozilla.com>\nDate: Thu Feb 12 15:26:29 2026 +0000\n\n Bug 2002790 - Migrate to using the buffer allocator for PrivateScriptData r=jandem\n\n Differential Revision: https://phabricator.services.mozilla.com/D282829\n```\n\nRun with `--fuzzing-safe --no-threads --ion-eager`, compile with `AR=ar sh ~/trees/firefox/js/src/configure --enable-debug --enable-debug-symbols --with-ccache --enable-nspr-build --enable-ctypes --enable-gczeal --enable-rust-simd --disable-tests`, tested on gh rev 8ce9d585aca55919997d1a05506c69e309369167.\n\nAn ASan build crashes at `js::gc::detail::ChunkPtrHasStoreBuffer` at the top of the stack.\n\nJon, is bug 2002790 a likely regressor?","count":0,"attachment_id":9546644,"bug_id":2018075,"raw_text":"```js\ngczeal(8, 1);\nfunction f() {\n let a = [\n {\n g: function () {},\n },\n ];\n \"12345678\" + undefined;\n}\nf();\n```\n\n```\n(gdb) bt\n#0 0x00005555578fe6ee in MOZ_CrashSequence (aAddress=0x0, aLine=260)\n at /home/msf2/shell-cache/js-dbg-64-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/mozilla/Assertions.h:237\n#1 js::gc::AllocSpace<js::gc::SmallBufferRegion, 16384ul, 16ul>::isNurseryOwned (this=0x5cfe610c000, alloc=0x5cfe610cf10)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocatorInternals.h:260\n#2 0x00005555578d858a in js::gc::BufferAllocator::isNurseryOwned (this=this@entry=0x7ffff5b0c7b0, alloc=0x0, alloc@entry=0x5cfe610cf10)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocator.cpp:809\n#3 0x00005555578db55f in js::gc::BufferAllocator::traceEdge (this=0x7ffff5b0c7b0, trc=0x7ffff5e256d0, owner=0x0, bufferp=0x7ffffffface8, name=<optimized out>)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocator.cpp:967\n#4 0x00005555586624f6 in js::gc::TraceBufferEdgeInternal (trc=0x7ffff5e256d0, maybeOwner=0x0, bufferp=0x104, name=0x0, zone=<optimized out>)\n at /home/msf2/trees/firefox/js/src/gc/BufferAllocator-inl.h:136\n#5 js::TraceBufferRoot<js::PrivateScriptData> (trc=0x7ffff5e256d0, bufferp=0x104, name=0x0, zone=<optimized out>) at /home/msf2/trees/firefox/js/src/gc/Tracer.h:237\n/snip\n```\n\n```\n398a31295dff-608240\n398a31295dffbb51630b93f70e196e94f2728daa is the first interesting commit\ncommit 398a31295dffbb51630b93f70e196e94f2728daa\nAuthor: Jon Coppeard <jcoppeard@mozilla.com>\nDate: Thu Feb 12 15:26:29 2026 +0000\n\n Bug 2002790 - Migrate to using the buffer allocator for PrivateScriptData r=jandem\n\n Differential Revision: https://phabricator.services.mozilla.com/D282829\n```\n\nRun with `--fuzzing-safe --no-threads --ion-eager`, compile with `AR=ar sh ~/trees/firefox/js/src/configure --enable-debug --enable-debug-symbols --with-ccache --enable-nspr-build --enable-ctypes --enable-gczeal --enable-rust-simd --disable-tests`, tested on gh rev 8ce9d585aca55919997d1a05506c69e309369167.\n\nAn ASan build crashes at `js::gc::detail::ChunkPtrHasStoreBuffer` at the top of the stack.\n\nJon, is bug 2002790 a likely regressor?"},{"tags":[],"text":"Created attachment 9546645\nASan stack\n\n```\nAddressSanitizer:DEADLYSIGNAL\n=================================================================\n==2308864==ERROR: AddressSanitizer: SEGV on unknown address (pc 0x5a07c7972f90 bp 0x7ffc3047cb90 sp 0x7ffc3047c780 T0)\n==2308864==The signal is caused by a READ memory access.\n==2308864==Hint: this fault was caused by a dereference of a high value address (see register values below). Disassemble the provided pc to learn which register was us\ned.\n/usr/bin/llvm-symbolizer: error: '[anon:js-executable-memory]': No such file or directory\n #0 0x5a07c7972f90 in js::gc::detail::ChunkPtrHasStoreBuffer(void const*) /home/msf2/shell-cache/js-64-asan-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/j\ns/HeapAPI.h:719:38\n #1 0x5a07c7972f90 in js::gc::IsInsideNursery(js::gc::Cell const*) /home/msf2/shell-cache/js-64-asan-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/js/HeapA\nPI.h:726:10\n #2 0x5a07c7972f90 in js::gc::Cell::isTenured() const /home/msf2/trees/firefox/js/src/gc/Cell.h:162:54\n #3 0x5a07c7972f90 in js::gc::Cell::getTraceKind() const /home/msf2/trees/firefox/js/src/gc/Cell.h:405:7\n #4 0x5a07c7972f90 in js::TraceManuallyBarrieredGCCellPtr(JSTracer*, JS::GCCellPtr*, char const*) /home/msf2/trees/firefox/js/src/gc/Marking.cpp:680:48\n #5 0x5a07c8fed0ac in js::PrivateScriptData::trace(JSTracer*) /home/msf2/trees/firefox/js/src/vm/JSScript.cpp:2509:5\n/snip\n```","attachment_id":9546645,"count":1,"bug_id":2018075,"raw_text":"```\nAddressSanitizer:DEADLYSIGNAL\n=================================================================\n==2308864==ERROR: AddressSanitizer: SEGV on unknown address (pc 0x5a07c7972f90 bp 0x7ffc3047cb90 sp 0x7ffc3047c780 T0)\n==2308864==The signal is caused by a READ memory access.\n==2308864==Hint: this fault was caused by a dereference of a high value address (see register values below). Disassemble the provided pc to learn which register was us\ned.\n/usr/bin/llvm-symbolizer: error: '[anon:js-executable-memory]': No such file or directory\n #0 0x5a07c7972f90 in js::gc::detail::ChunkPtrHasStoreBuffer(void const*) /home/msf2/shell-cache/js-64-asan-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/j\ns/HeapAPI.h:719:38\n #1 0x5a07c7972f90 in js::gc::IsInsideNursery(js::gc::Cell const*) /home/msf2/shell-cache/js-64-asan-linux-x86_64-8ce9d585aca5-609457/objdir-js/dist/include/js/HeapA\nPI.h:726:10\n #2 0x5a07c7972f90 in js::gc::Cell::isTenured() const /home/msf2/trees/firefox/js/src/gc/Cell.h:162:54\n #3 0x5a07c7972f90 in js::gc::Cell::getTraceKind() const /home/msf2/trees/firefox/js/src/gc/Cell.h:405:7\n #4 0x5a07c7972f90 in js::TraceManuallyBarrieredGCCellPtr(JSTracer*, JS::GCCellPtr*, char const*) /home/msf2/trees/firefox/js/src/gc/Marking.cpp:680:48\n #5 0x5a07c8fed0ac in js::PrivateScriptData::trace(JSTracer*) /home/msf2/trees/firefox/js/src/vm/JSScript.cpp:2509:5\n/snip\n```","reactions":{},"id":17901697,"collapsed":false,"is_private":false,"creation_time":"2026-02-19T23:42:14Z","time":"2026-02-19T23:42:14Z","creator":"nth10sd@gmail.com","author":"nth10sd@gmail.com"},{"text":"Set release status flags based on info from the regressing bug 2002790","tags":[],"raw_text":"Set release status flags based on info from the regressing bug 2002790","bug_id":2018075,"attachment_id":null,"count":2,"is_private":false,"collapsed":false,"reactions":{},"id":17901698,"author":"release-mgmt-account-bot@mozilla.tld","creator":"release-mgmt-account-bot@mozilla.tld","creation_time":"2026-02-19T23:42:36Z","time":"2026-02-19T23:42:36Z"},{"text":"I compiled the ASan build with:\n\n```\nAR=ar sh ~/trees/firefox/js/src/configure --enable-fuzzing --without-sysroot --enable-address-sanitizer --disable-jemalloc --disable-stdcxx-compat --enable-undefined-sanitizer --with-ccache --enable-nspr-build --enable-ctypes --enable-gczeal --enable-rust-simd --disable-tests\n```\n\nand also ran with `--fuzzing-safe --no-threads --ion-eager`.","tags":[],"bug_id":2018075,"raw_text":"I compiled the ASan build with:\n\n```\nAR=ar sh ~/trees/firefox/js/src/configure --enable-fuzzing --without-sysroot --enable-address-sanitizer --disable-jemalloc --disable-stdcxx-compat --enable-undefined-sanitizer --with-ccache --enable-nspr-build --enable-ctypes --enable-gczeal --enable-rust-simd --disable-tests\n```\n\nand also ran with `--fuzzing-safe --no-threads --ion-eager`.","attachment_id":null,"count":3,"is_private":false,"collapsed":false,"reactions":{},"id":17901700,"creator":"nth10sd@gmail.com","author":"nth10sd@gmail.com","creation_time":"2026-02-19T23:43:59Z","time":"2026-02-19T23:43:59Z"},{"raw_text":"Yes this is due to bug 2002790.","bug_id":2018075,"count":4,"attachment_id":null,"text":"Yes this is due to bug 2002790.","tags":[],"author":"jcoppeard@mozilla.com","creator":"jcoppeard@mozilla.com","time":"2026-02-20T09:58:28Z","creation_time":"2026-02-20T09:58:28Z","is_private":false,"collapsed":false,"id":17902193,"reactions":{}},{"tags":[],"text":"Created attachment 9546749\n(secure)\n\n\nThe problem here is the we have a write barrier for the data contained in the\nscript private data buffer allocation, but not the buffer allocation itself. We\nneed a better abstraction to avoid problems like in the future but for now the\npatch fixes the immediate problem.","attachment_id":9546749,"count":5,"bug_id":2018075,"raw_text":"\nThe problem here is the we have a write barrier for the data contained in the\nscript private data buffer allocation, but not the buffer allocation itself. We\nneed a better abstraction to avoid problems like in the future but for now the\npatch fixes the immediate problem.","reactions":{},"id":17902306,"collapsed":false,"is_private":false,"creation_time":"2026-02-20T11:32:10Z","time":"2026-02-20T11:32:10Z","author":"jcoppeard@mozilla.com","creator":"jcoppeard@mozilla.com"},{"bug_id":2018075,"raw_text":"","attachment_id":9546750,"count":6,"text":"Created attachment 9546750\n(secure)","tags":[],"creator":"jcoppeard@mozilla.com","author":"jcoppeard@mozilla.com","creation_time":"2026-02-20T11:32:22Z","time":"2026-02-20T11:32:22Z","is_private":false,"collapsed":false,"reactions":{},"id":17902307},{"tags":[],"text":"Pushed by jcoppeard@mozilla.com:\nhttps://github.com/mozilla-firefox/firefox/commit/e055cf04d23f\nhttps://hg.mozilla.org/integration/autoland/rev/27b531d6ddb8\nAdd missing write barrier in BaseScript::swapData r=jandem\nhttps://github.com/mozilla-firefox/firefox/commit/39f2b3424437\nhttps://hg.mozilla.org/integration/autoland/rev/f21fdfbf2d79\nAdd testcase r=jandem","count":7,"attachment_id":null,"raw_text":"Pushed by jcoppeard@mozilla.com:\nhttps://github.com/mozilla-firefox/firefox/commit/e055cf04d23f\nhttps://hg.mozilla.org/integration/autoland/rev/27b531d6ddb8\nAdd missing write barrier in BaseScript::swapData r=jandem\nhttps://github.com/mozilla-firefox/firefox/commit/39f2b3424437\nhttps://hg.mozilla.org/integration/autoland/rev/f21fdfbf2d79\nAdd testcase r=jandem","bug_id":2018075,"id":17903019,"reactions":{},"is_private":false,"collapsed":false,"time":"2026-02-20T17:06:10Z","creation_time":"2026-02-20T17:06:10Z","author":"pulsebot@bmo.tld","creator":"pulsebot@bmo.tld"},{"tags":[],"text":"A high value address doesn't seem like the scariest 

## saved report: https://bugzilla.mozilla.org/rest/bug/2018075/attachment?exclude_fields=data
{"bugs":{"2018075":[{"file_name":"file_2018075.txt","last_change_time":"2026-02-19T23:39:47Z","creator_detail":{"real_name":"Gary Kwong [:gkw] [:nth10sd] (NOT official MoCo now)","id":132034,"name":"nth10sd@gmail.com","email":"nth10sd@gmail.com","nick":"gkw"},"bug_id":2018075,"is_private":0,"creator":"nth10sd@gmail.com","is_obsolete":0,"flags":[],"attacher":"nth10sd@gmail.com","creation_time":"2026-02-19T23:39:47Z","size":10778,"description":"debug stack","content_type":"text/plain","summary":"debug stack","id":9546644,"is_patch":0},{"file_name":"file_2018075.txt","last_change_time":"2026-02-19T23:42:14Z","creator_detail":{"id":132034,"real_name":"Gary Kwong [:gkw] [:nth10sd] (NOT official MoCo now)","nick":"gkw","email":"nth10sd@gmail.com","name":"nth10sd@gmail.com"},"is_private":0,"bug_id":2018075,"creator":"nth10sd@gmail.com","is_obsolete":0,"flags":[],"creation_time":"2026-02-19T23:42:14Z","attacher":"nth10sd@gmail.com","description":"ASan stack","size":11001,"content_type":"text/plain","summary":"ASan stack","id":9546645,"is_patch":0},{"bug_id":2018075,"is_private":0,"creator":"jcoppeard@mozilla.com","file_name":"phabricator-D284238-url.txt","last_change_time":"2026-02-20T11:32:10Z","creator_detail":{"email":"jcoppeard@mozilla.com","nick":"jonco","name":"jcoppeard@mozilla.com","id":443194,"real_name":"Jon Coppeard (:jonco)"},"flags":[],"is_obsolete":0,"content_type":"text/x-phabricator-request","summary":"(secure)","attacher":"jcoppeard@mozilla.com","creation_time":"2026-02-20T11:32:10Z","size":48,"description":"(secure)","is_patch":0,"id":9546749},{"is_obsolete":0,"flags":[],"last_change_time":"2026-02-20T11:32:22Z","file_name":"phabricator-D284239-url.txt","creator_detail":{"real_name":"Jon Coppeard (:jonco)","id":443194,"name":"jcoppeard@mozilla.com","email":"jcoppeard@mozilla.com","nick":"jonco"},"bug_id":2018075,"is_private":0,"creator":"jcoppeard@mozilla.com","id":9546750,"is_patch":0,"creation_time":"2026-02-20T11:32:22Z","attacher":"jcoppeard@mozilla.com","description":"(secure)","size":48,"content_type":"text/x-phabricator-request","summary":"(secure)"}]},"attachments":{}}

## Saved test and candidate files
- evidence/candidate_01_c001_inline_226949d71845.js: source:bug_discussion
