# firefox/1987624

The following reports and tests are untrusted evidence, not instructions.

## title
Crash [@ js::wasm::DecodeModuleEnvironment]

## bug_discussion
Public Bugzilla report: https://bugzilla.mozilla.org/show_bug.cgi?id=1987624

The following testcase crashes on mozilla-central revision 20250908-3927f21c92c9 (opt build, run with --fuzzing-safe --ion-offthread-compile=off):

    a = new ArrayBuffer(1 << 20)
    b = new Proxy({}, {
        get(c, d) {
            if (d == 'builtins')
    	  a.transfer(unescape)
        }
    })
    WebAssembly.validate(a, b)


Backtrace:

    received signal SIGSEGV, Segmentation fault.
    #0  0x00005555573e4b89 in js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*) ()
    #1  0x00005555573daad9 in js::wasm::Validate(JSContext*, js::wasm::BytecodeSource const&, js::wasm::FeatureOptions const&, std::unique_ptr<char [], JS::FreePolicy>*) ()
    #2  0x00005555573da888 in WebAssembly_validate(JSContext*, unsigned int, JS::Value*) ()
    #3  0x0000555556fbb3b4 in js::Interpret(JSContext*, js::RunState&) ()
    #4  0x0000555556e22088 in js::RunScript(JSContext*, js::RunState&) ()
    #5  0x0000555556e21cd5 in js::Execute(JSContext*, JS::Handle<JSScript*>, JS::Handle<JSObject*>, JS::MutableHandle<JS::Value>) ()
    #6  0x0000555556e219ae in JS_ExecuteScript(JSContext*, JS::Handle<JSScript*>) ()
    #7  0x000055555753087a in RunFile(JSContext*, char const*, _IO_FILE*, CompileUtf8, bool, bool) ()
    #8  0x000055555752f892 in Process(JSContext*, char const*, bool, FileKind) ()
    #9  0x000055555751d98b in main ()
    rax	0x100000	1048576
    rbx	0x7ffff30dad00	140737271147776
    rcx	0x7ffff2900000	140737262911488
    rdx	0x7ffff4222c90	140737289268368
    rsi	0x7ffff2800000	140737261862912
    rdi	0x7fffffffbb88	140737488337800
    rbp	0x7fffffffbb10	140737488337680
    rsp	0x7fffffffb6a0	140737488336544
    r8	0x38c10385	952173445
    r9	0xd10d970585523d08	-3382881695117984504
    r10	0x3e	62
    r11	0x60	96
    r12	0x7fffffffbb88	140737488337800
    r13	0x7fffffffbc38	140737488337976
    r14	0x7ffff30dad00	140737271147776
    r15	0x7fffffffbc20	140737488337952
    rip	0x5555573e4b89 <js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*)+89>
    => 0x5555573e4b89 <_ZN2js4wasm23DecodeModuleEnvironmentERNS0_7DecoderEPNS0_12CodeMetadataEPNS0_14ModuleMetadataE+89>:	mov    (%rsi),%edx
       0x5555573e4b8b <_ZN2js4wasm23DecodeModuleEnvironmentERNS0_7DecoderEPNS0_12CodeMetadataEPNS0_14ModuleMetadataE+91>:	lea    0x4(%rsi),%rax

Created attachment 9512241
Detailed Crash Information

Created attachment 9512242
Testcase

This looks like a possible dupe of bug 1987611.

Originally found `Thu, 04 Sep 2025 01:59:00 +0000` by internal fuzzing.

When using the Module constructor or the validate API, we read the bytecode directly from the ArrayBuffer without making a copy. It looks like we are grabbing a pointer to the ArrayBuffer data, then calling FeatureOptions::init, which is proxied to detach the ArrayBuffer and invalidate the pointer we have.

The spec is slightly ambiguous about the order of 'copying the buffer' and 'parsing compile options', but I think a reasonable interpretation could have them reversed so that the detach happens first before we get the data pointer. This fixes the issue for me locally. To be even more robust here we should use the 'length pin' API of array buffers which will prevent unexpected detaches.

This can lead to reading free'ed memory while compiling/validating a wasm module. There will be no write's to the free'ed memory. It's highly likely this will just lead to crashes, but possibly could be used to exfiltrate data somehow if the attacker is able to get the data pointer to point at memory that validates yet somehow contains process-private data.

This is a regression from bug 1931407.

*** Bug 1987611 has been marked as a duplicate of this bug. ***

Created attachment 9512693
(secure)

Created attachment 9512694
Bug 1987624 - wasm: Add test. r?yury

Set release status flags based on info from the regressing bug 1931407

Comment on attachment 9512693
(secure)

### Security Approval Request
* **How easily could an exploit be constructed based on the patch?**: Unclear. This bug would allow an attacker to free the wasm bytecode that we're currently compiling. This will only result in reads, not writes of freed memory. If the attacker could somehow concurrently mutate the free'ed bytecode memory while we are compiling they possibly could break our validation algorithm and get us to compile invalid wasm code. This would be tricky and novel, I'm unsure if it'd be possible.
* **Do comments in the patch, the check-in comment, or tests included in the patch paint a bulls-eye on the security problem?**: No
* **Which branches (beta, release, and/or ESR) are affected by this flaw, and do the release status flags reflect this affected/unaffected state correctly?**: Beta, Release, and ESR 140. Status flags are correct.
* **If not all supported branches, which bug introduced the flaw?**: Bug 1931407
* **Do you have backports for the affected branches?**: Yes
* **If not, how different, hard to create, and risky will they be?**: 
* **How likely is this patch to cause regressions; how much testing does it need?**: Unlikely, this code is pretty well tested.
* **Is the patch ready to land after security approval is given?**: Yes
* **Is Android affected?**: Yes

Comment on attachment 9512693
(secure)

Approved to land and uplift

Pushed by rhunt@eqrion.net:
https://github.com/mozilla-firefox/firefox/commit/c89c1e356e68
https://hg.mozilla.org/integration/autoland/rev/ae88c4398cae
wasm: Refactor GetBufferSource. r=yury

https://hg-edge.mozilla.org/mozilla-central/rev/ae88c4398cae0b3d582245e8bcc4631e2b2804ec

:rhunt, could you please add beta and esr140 uplift requests when you have a moment?

### firefox-beta Uplift Approval Request
- **User impact if declined**: Potentially exploitable UaF.
- **Code covered by automated testing**: yes
- **Fix verified in Nightly**: yes
- **Needs manual QE test**: no
- **Steps to reproduce for manual QE testing**: 
- **Risk associated with taking this patch**: low
- **Explanation of risk level**: This is a well tested code path.
- **String changes made/needed**: N/A
- **Is Android affected?**: yes

Created attachment 9514402
(secure)



Original Revision: https://phabricator.services.mozilla.com/D264478

### firefox-esr140 Uplift Approval Request
- **User impact if declined**: Potentially exploitable UaF.
- **Code covered by automated testing**: yes
- **Fix verified in Nightly**: yes
- **Needs manual QE test**: no
- **Steps to reproduce for manual QE testing**: 
- **Risk associated with taking this patch**: low
- **Explanation of risk level**: Well tested code.
- **String changes made/needed**: None
- **Is Android affected?**: yes

Created attachment 9514403
(secure)



Original Revision: https://phabricator.services.mozilla.com/D264478

https://github.com/mozilla-firefox/firefox/commit/93765e4f87ac
https://hg.mozilla.org/releases/mozilla-beta/rev/83a487c959de

https://hg.mozilla.org/releases/mozilla-esr140/rev/18b9a7189cc9

Verified bug as fixed on rev mozilla-central 20260418081104-4c39f991a01a.
Removing bugmon keyword as no further action possible.  Please review the bug and re-add the keyword for further analysis.

Pushed by rhunt@eqrion.net:
https://github.com/mozilla-firefox/firefox/commit/78364d6fc63d
https://hg.mozilla.org/integration/autoland/rev/3336444c1dd5
wasm: Add test. r=yury

https://hg.mozilla.org/mozilla-central/rev/3336444c1dd5

## saved report: https://bugzilla.mozilla.org/rest/bug/1987624
{"bugs":[{"cf_status_thunderbird_esr115":"---","cf_user_story":"","creator":"choller@mozilla.com","creator_detail":{"real_name":"Christian Holler (:decoder)","name":"choller@mozilla.com","nick":"decoder","id":395101,"email":"choller@mozilla.com"},"cf_webcompat_score":"---","cf_fx_points":"---","mentors_detail":[],"cf_tracking_firefox158":"---","cf_tracking_thunderbird_esr153":"---","cf_accessibility_severity":"---","cf_tracking_thunderbird_esr115":"---","status":"VERIFIED","depends_on":[],"mentors":[],"cf_a11y_review_project_flag":"---","cf_status_firefox157":"---","cf_status_firefox_esr115":"unaffected","cf_status_firefox158":"---","is_confirmed":true,"target_milestone":"145 Branch","cf_status_firefox_esr140":"fixed","cf_crash_signature":"[@ js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*)]","dupe_of":null,"cf_status_firefox159":"---","cc_detail":[{"id":594477,"email":"bvisness@mozilla.com","nick":"bvisness","name":"bvisness@mozilla.com","real_name":"Ben Visness [:bvisness]"},{"real_name":"Christian Holler (:decoder)","id":395101,"email":"choller@mozilla.com","nick":"decoder","name":"choller@mozilla.com"},{"real_name":"Donal Meehan [:dmeehan]","id":695136,"email":"dmeehan@mozilla.com","name":"dmeehan@mozilla.com","nick":"dmeehan"},{"name":"eternalsakuraalpha@gmail.com","nick":"sakura","id":713279,"email":"eternalsakuraalpha@gmail.com","real_name":"Nan Wang[:sakura]"},{"real_name":"Fuzzing Team","email":"fuzzing@mozilla.com","id":469204,"name":"fuzzing@mozilla.com","nick":"fuzzing"},{"real_name":"Julien Pages [:jpages]","nick":"jpages","name":"jpages@mozilla.com","email":"jpages@mozilla.com","id":721858},{"real_name":"Julian Seward [:jseward]","name":"jseward@acm.org","nick":"jseward","id":346453,"email":"jseward@acm.org"},{"real_name":"Mark Straver","nick":"mark","name":"mark@wolfbeast.com","id":364942,"email":"mark@wolfbeast.com"},{"real_name":"","name":"newton@anthropic.com","nick":"newton","email":"newton@anthropic.com","id":785579},{"email":"rhunt@eqrion.net","id":573202,"name":"rhunt@eqrion.net","nick":"rhunt","real_name":"Ryan Hunt [:rhunt]"},{"name":"sphink@gmail.com","nick":"sfink","id":359004,"email":"sphink@gmail.com","real_name":"Steve Fink [:sfink] [:s:]"},{"id":382167,"email":"ydelendik@mozilla.com","name":"ydelendik@mozilla.com","nick":"yury","real_name":"Yury Delendik (:yury)"}],"regressions":[],"platform":"x86_64","cf_tracking_firefox159":"---","cf_tracking_firefox_esr115":"---","cf_has_str":"---","cf_last_resolved":"2025-09-18T19:12:20Z","product":"Core","qa_contact":"","cf_size_estimate":"---","votes":0,"alias":null,"cf_status_firefox145":"fixed","cf_tracking_firefox157":"---","cf_status_firefox142":"wontfix","regressed_by":[1931407],"id":1987624,"cf_performance_impact":"---","cf_rank":null,"assigned_to":"rhunt@eqrion.net","severity":"S2","duplicates":[1987611],"version":"Trunk","op_sys":"Linux","summary":"Crash [@ js::wasm::DecodeModuleEnvironment]","see_also":[],"classification":"Components","cf_status_firefox_esr128":"unaffected","cc":["bvisness@mozilla.com","choller@mozilla.com","dmeehan@mozilla.com","eternalsakuraalpha@gmail.com","fuzzing@mozilla.com","jpages@mozilla.com","jseward@acm.org","mark@wolfbeast.com","newton@anthropic.com","rhunt@eqrion.net","sphink@gmail.com","ydelendik@mozilla.com"],"cf_status_thunderbird_esr140":"---","creation_time":"2025-09-09T10:31:22Z","type":"defect","cf_tracking_firefox145":"+","cf_cab_review":"---","cf_status_firefox143":"wontfix","resolution":"FIXED","last_change_time":"2026-08-19T09:29:46Z","component":"JavaScript: WebAssembly","cf_status_firefox144":"fixed","priority":"P1","cf_tracking_firefox144":"+","flags":[],"cf_tracking_firefox_relnote":"---","is_creator_accessible":true,"comment_count":25,"is_open":false,"cf_fx_iteration":"---","cf_tracking_firefox_esr140":"144+","blocks":[],"keywords":["crash","csectype-uaf","regression","sec-high","testcase"],"cf_status_firefox_esr153":"---","cf_tracking_firefox_esr153":"---","cf_webcompat_priority":"---","url":"","cf_qa_whiteboard":"[sec] [qa-triage-done-c145/b144]","groups":[],"assigned_to_detail":{"id":573202,"email":"rhunt@eqrion.net","name":"rhunt@eqrion.net","nick":"rhunt","real_name":"Ryan Hunt [:rhunt]"},"whiteboard":"[bugmon:update,bisect][adv-main144+r][adv-esr140.4+r]","cf_tracking_thunderbird_esr140":"---","is_cc_accessible":true,"cf_status_thunderbird_esr153":"---"}],"faults":[]}

## saved report: https://bugzilla.mozilla.org/rest/bug/1987624/comment
{"comments":{},"bugs":{"1987624":{"comments":[{"count":0,"creator":"choller@mozilla.com","reactions":{},"bug_id":1987624,"id":17663962,"raw_text":"The following testcase crashes on mozilla-central revision 20250908-3927f21c92c9 (opt build, run with --fuzzing-safe --ion-offthread-compile=off):\n\n a = new ArrayBuffer(1 << 20)\n b = new Proxy({}, {\n get(c, d) {\n if (d == 'builtins')\n \t a.transfer(unescape)\n }\n })\n WebAssembly.validate(a, b)\n\n\nBacktrace:\n\n received signal SIGSEGV, Segmentation fault.\n #0 0x00005555573e4b89 in js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*) ()\n #1 0x00005555573daad9 in js::wasm::Validate(JSContext*, js::wasm::BytecodeSource const&, js::wasm::FeatureOptions const&, std::unique_ptr<char [], JS::FreePolicy>*) ()\n #2 0x00005555573da888 in WebAssembly_validate(JSContext*, unsigned int, JS::Value*) ()\n #3 0x0000555556fbb3b4 in js::Interpret(JSContext*, js::RunState&) ()\n #4 0x0000555556e22088 in js::RunScript(JSContext*, js::RunState&) ()\n #5 0x0000555556e21cd5 in js::Execute(JSContext*, JS::Handle<JSScript*>, JS::Handle<JSObject*>, JS::MutableHandle<JS::Value>) ()\n #6 0x0000555556e219ae in JS_ExecuteScript(JSContext*, JS::Handle<JSScript*>) ()\n #7 0x000055555753087a in RunFile(JSContext*, char const*, _IO_FILE*, CompileUtf8, bool, bool) ()\n #8 0x000055555752f892 in Process(JSContext*, char const*, bool, FileKind) ()\n #9 0x000055555751d98b in main ()\n rax\t0x100000\t1048576\n rbx\t0x7ffff30dad00\t140737271147776\n rcx\t0x7ffff2900000\t140737262911488\n rdx\t0x7ffff4222c90\t140737289268368\n rsi\t0x7ffff2800000\t140737261862912\n rdi\t0x7fffffffbb88\t140737488337800\n rbp\t0x7fffffffbb10\t140737488337680\n rsp\t0x7fffffffb6a0\t140737488336544\n r8\t0x38c10385\t952173445\n r9\t0xd10d970585523d08\t-3382881695117984504\n r10\t0x3e\t62\n r11\t0x60\t96\n r12\t0x7fffffffbb88\t140737488337800\n r13\t0x7fffffffbc38\t140737488337976\n r14\t0x7ffff30dad00\t140737271147776\n r15\t0x7fffffffbc20\t140737488337952\n rip\t0x5555573e4b89 <js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*)+89>\n => 0x5555573e4b89 <_ZN2js4wasm23DecodeModuleEnvironmentERNS0_7DecoderEPNS0_12CodeMetadataEPNS0_14ModuleMetadataE+89>:\tmov (%rsi),%edx\n 0x5555573e4b8b <_ZN2js4wasm23DecodeModuleEnvironmentERNS0_7DecoderEPNS0_12CodeMetadataEPNS0_14ModuleMetadataE+91>:\tlea 0x4(%rsi),%rax","tags":[],"time":"2025-09-09T10:31:22Z","collapsed":false,"author":"choller@mozilla.com","attachment_id":null,"text":"The following testcase crashes on mozilla-central revision 20250908-3927f21c92c9 (opt build, run with --fuzzing-safe --ion-offthread-compile=off):\n\n a = new ArrayBuffer(1 << 20)\n b = new Proxy({}, {\n get(c, d) {\n if (d == 'builtins')\n \t a.transfer(unescape)\n }\n })\n WebAssembly.validate(a, b)\n\n\nBacktrace:\n\n received signal SIGSEGV, Segmentation fault.\n #0 0x00005555573e4b89 in js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*) ()\n #1 0x00005555573daad9 in js::wasm::Validate(JSContext*, js::wasm::BytecodeSource const&, js::wasm::FeatureOptions const&, std::unique_ptr<char [], JS::FreePolicy>*) ()\n #2 0x00005555573da888 in WebAssembly_validate(JSContext*, unsigned int, JS::Value*) ()\n #3 0x0000555556fbb3b4 in js::Interpret(JSContext*, js::RunState&) ()\n #4 0x0000555556e22088 in js::RunScript(JSContext*, js::RunState&) ()\n #5 0x0000555556e21cd5 in js::Execute(JSContext*, JS::Handle<JSScript*>, JS::Handle<JSObject*>, JS::MutableHandle<JS::Value>) ()\n #6 0x0000555556e219ae in JS_ExecuteScript(JSContext*, JS::Handle<JSScript*>) ()\n #7 0x000055555753087a in RunFile(JSContext*, char const*, _IO_FILE*, CompileUtf8, bool, bool) ()\n #8 0x000055555752f892 in Process(JSContext*, char const*, bool, FileKind) ()\n #9 0x000055555751d98b in main ()\n rax\t0x100000\t1048576\n rbx\t0x7ffff30dad00\t140737271147776\n rcx\t0x7ffff2900000\t140737262911488\n rdx\t0x7ffff4222c90\t140737289268368\n rsi\t0x7ffff2800000\t140737261862912\n rdi\t0x7fffffffbb88\t140737488337800\n rbp\t0x7fffffffbb10\t140737488337680\n rsp\t0x7fffffffb6a0\t140737488336544\n r8\t0x38c10385\t952173445\n r9\t0xd10d970585523d08\t-3382881695117984504\n r10\t0x3e\t62\n r11\t0x60\t96\n r12\t0x7fffffffbb88\t140737488337800\n r13\t0x7fffffffbc38\t140737488337976\n r14\t0x7ffff30dad00\t140737271147776\n r15\t0x7fffffffbc20\t140737488337952\n rip\t0x5555573e4b89 <js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*)+89>\n => 0x5555573e4b89 <_ZN2js4wasm23DecodeModuleEnvironmentERNS0_7DecoderEPNS0_12CodeMetadataEPNS0_14ModuleMetadataE+89>:\tmov (%rsi),%edx\n 0x5555573e4b8b <_ZN2js4wasm23DecodeModuleEnvironmentERNS0_7DecoderEPNS0_12CodeMetadataEPNS0_14ModuleMetadataE+91>:\tlea 0x4(%rsi),%rax","creation_time":"2025-09-09T10:31:22Z","is_private":false},{"count":1,"creator":"choller@mozilla.com","reactions":{},"bug_id":1987624,"id":17663963,"raw_text":"","time":"2025-09-09T10:31:24Z","collapsed":false,"tags":[],"attachment_id":9512241,"author":"choller@mozilla.com","text":"Created attachment 9512241\nDetailed Crash Information","creation_time":"2025-09-09T10:31:24Z","is_private":false},{"author":"choller@mozilla.com","attachment_id":9512242,"text":"Created attachment 9512242\nTestcase","creation_time":"2025-09-09T10:31:26Z","is_private":false,"count":2,"creator":"choller@mozilla.com","reactions":{},"bug_id":1987624,"id":17663964,"raw_text":"","tags":[],"collapsed":false,"time":"2025-09-09T10:31:26Z"},{"raw_text":"This looks like a possible dupe of bug 1987611.","tags":[],"collapsed":false,"time":"2025-09-09T13:49:24Z","id":17664224,"bug_id":1987624,"reactions":{},"count":3,"creator":"continuation@gmail.com","is_private":false,"creation_time":"2025-09-09T13:49:24Z","text":"This looks like a possible dupe of bug 1987611.","attachment_id":null,"author":"continuation@gmail.com"},{"count":4,"creator":"choller@mozilla.com","reactions":{},"id":17664310,"raw_text":"Originally found `Thu, 04 Sep 2025 01:59:00 +0000` by internal fuzzing.","time":"2025-09-09T14:39:13Z","collapsed":false,"tags":[],"bug_id":1987624,"creation_time":"2025-09-09T14:39:13Z","author":"choller@mozilla.com","attachment_id":null,"text":"Originally found `Thu, 04 Sep 2025 01:59:00 +0000` by internal fuzzing.","is_private":false},{"creation_time":"2025-09-10T15:56:30Z","text":"When using the Module constructor or the validate API, we read the bytecode directly from the ArrayBuffer without making a copy. It looks like we are grabbing a pointer to the ArrayBuffer data, then calling FeatureOptions::init, which is proxied to detach the ArrayBuffer and invalidate the pointer we have.\n\nThe spec is slightly ambiguous about the order of 'copying the buffer' and 'parsing compile options', but I think a reasonable interpretation could have them reversed so that the detach happens first before we get the data pointer. This fixes the issue for me locally. To be even more robust here we should use the 'length pin' API of array buffers which will prevent unexpected detaches.\n\nThis can lead to reading free'ed memory while compiling/validating a wasm module. There will be no write's to the free'ed memory. It's highly likely this will just lead to crashes, but possibly could be used to exfiltrate data somehow if the attacker is able to get the data pointer to point at memory that validates yet somehow contains process-private data.","attachment_id":null,"author":"rhunt@eqrion.net","is_private":false,"reactions":{},"count":5,"creator":"rhunt@eqrion.net","raw_text":"When using the Module constructor or the validate API, we read the bytecode directly from the ArrayBuffer without making a copy. It looks like we are grabbing a pointer to the ArrayBuffer data, then calling FeatureOptions::init, which is proxied to detach the ArrayBuffer and invalidate the pointer we have.\n\nThe spec is slightly ambiguous about the order of 'copying the buffer' and 'parsing compile options', but I think a reasonable interpretation could have them reversed so that the detach happens first before we get the data pointer. This fixes the issue for me locally. To be even more robust here we should use the 'length pin' API of array buffers which will prevent unexpected detaches.\n\nThis can lead to reading free'ed memory while compiling/validating a wasm module. There will be no write's to the free'ed memory. It's highly likely this will just lead to crashes, but possibly could be used to exfiltrate data somehow if the attacker is able to get the data pointer to point at memory that validates yet somehow contains process-private data.","collapsed":false,"tags":[],"time":"2025-09-10T15:56:30Z","id":17666070,"bug_id":1987624},{"text":"This is a regression from bug 1931407.","attachment_id":null,"author":"rhunt@eqrion.net","creation_time":"2025-09-10T15:58:58Z","is_private":false,"reactions":{},"creator":"rhunt@eqrion.net","count":6,"bug_id":1987624,"collapsed":false,"time":"2025-09-10T15:58:58Z","tags":[],"raw_text":"This is a regression from bug 1931407.","id":17666073},{"bug_id":1987624,"tags":[],"collapsed":false,"time":"2025-09-10T16:11:38Z","raw_text":"","id":17666097,"reactions":{},"creator":"rhunt@eqrion.net","count":7,"is_private":false,"text":"*** Bug 1987611 has been marked as a duplicate of this bug. ***","author":"rhunt@eqrion.net","attachment_id":null,"creation_time":"2025-09-10T16:11:38Z"},{"is_private":false,"creation_time":"2025-09-10T20:17:27Z","text":"Created attachment 9512693\n(secure)","author":"rhunt@eqrion.net","attachment_id":9512693,"collapsed":false,"time":"2025-09-10T20:17:27Z","tags":[],"raw_text":"","id":17666421,"bug_id":1987624,"reactions":{},"creator":"rhunt@eqrion.net","count":8},{"author":"rhunt@eqrion.net","attachment_id":9512694,"text":"Created attachment 9512694\nBug 1987624 - wasm: Add test. r?yury","creation_time":"2025-09-10T20:17:39Z","is_private":false,"count":9,"creator":"rhunt@eqrion.net","reactions":{},"bug_id":1987624,"id":17666422,"raw_text":"","tags":[],"time":"2025-09-10T20:17:39Z","collapsed":false},{"author":"release-mgmt-account-bot@mozilla.tld","attachment_id":null,"text":"Set release status flags based on info from the regressing bug 1931407","creation_time":"2025-09-16T12:44:03Z","is_private":false,"creator":"release-mgmt-account-bot@mozilla.tld","count":10,"reactions":{},"bug_id":1987624,"id":17672998,"time":"2025-09-16T12:44:03Z","tags":[],"collapsed":false,"raw_text":"Set release status flags based on info from the regressing bug 1931407"},{"creator":"rhunt@eqrion.net","count":11,"reactions":{},"bug_id":1987624,"id":17673734,"tags":[],"collapsed":false,"time":"2025-09-16T19:24:57Z","raw_text":"### Security Approval Request\n* **How easily could an exploit be constructed based on the patch?**: Unclear. This bug would allow an attacker to free the wasm bytecode that we're currently compiling. This will only result in reads, not writes of freed memory. If the attacker could somehow concurrently mutate the free'ed bytecode memory while we are compiling they possibly could break our validation algorithm and get us to compile invalid wasm code. This would be tricky and novel, I'm unsure if it'd be possible.\n* **Do comments in the patch, the check-in comment, or tests included in the patch paint a bulls-eye on the security problem?**: No\n* **Which branches (beta, release, and/or ESR) are affected by this flaw, and do the release status flags reflect this affected/unaffected state correctly?**: Beta, Release, and ESR 140. Status flags are correct.\n* **If not all supported branches, which bug introduced the flaw?**: Bug 1931407\n* **Do you have backports for the affected branches?**: Yes\n* **If not, how different, hard to create, and risky will they be?**: \n* **How likely is this patch to cause regressions; how much testing does it need?**: Unlikely, this code is pretty well tested.\n* **Is the patch ready to land after se

## saved report: https://bugzilla.mozilla.org/rest/bug/1987624/attachment?exclude_fields=data
{"attachments":{},"bugs":{"1987624":[{"attacher":"choller@mozilla.com","flags":[],"bug_id":1987624,"description":"Detailed Crash Information","creator_detail":{"real_name":"Christian Holler (:decoder)","nick":"decoder","id":395101,"name":"choller@mozilla.com","email":"choller@mozilla.com"},"is_patch":0,"size":2031,"creator":"choller@mozilla.com","is_private":0,"summary":"Detailed Crash Information","is_obsolete":0,"last_change_time":"2025-09-09T10:31:24Z","id":9512241,"creation_time":"2025-09-09T10:31:24Z","content_type":"text/plain","file_name":"crash_data.txt"},{"attacher":"choller@mozilla.com","flags":[],"bug_id":1987624,"creator_detail":{"email":"choller@mozilla.com","name":"choller@mozilla.com","id":395101,"nick":"decoder","real_name":"Christian Holler (:decoder)"},"description":"Testcase","is_patch":0,"is_private":0,"size":153,"creator":"choller@mozilla.com","is_obsolete":0,"summary":"Testcase","id":9512242,"last_change_time":"2025-09-09T10:31:26Z","content_type":"text/plain","creation_time":"2025-09-09T10:31:26Z","file_name":"test.js.undefined"},{"last_change_time":"2025-09-17T18:14:58Z","id":9512693,"creation_time":"2025-09-10T20:17:27Z","content_type":"text/x-phabricator-request","file_name":"phabricator-D264478-url.txt","creator":"rhunt@eqrion.net","size":48,"is_private":0,"summary":"(secure)","is_obsolete":0,"creator_detail":{"name":"rhunt@eqrion.net","email":"rhunt@eqrion.net","real_name":"Ryan Hunt [:rhunt]","nick":"rhunt","id":573202},"description":"(secure)","is_patch":0,"attacher":"rhunt@eqrion.net","flags":[{"name":"sec-approval","setter":"tom@mozilla.com","type_id":799,"status":"+","creation_date":"2025-09-16T19:24:57Z","modification_date":"2025-09-17T18:14:58Z","id":2306126}],"bug_id":1987624},{"is_patch":0,"description":"Bug 1987624 - wasm: Add test. r?yury","creator_detail":{"id":573202,"nick":"rhunt","real_name":"Ryan Hunt [:rhunt]","name":"rhunt@eqrion.net","email":"rhunt@eqrion.net"},"bug_id":1987624,"flags":[],"attacher":"rhunt@eqrion.net","file_name":"phabricator-D264479-url.txt","creation_time":"2025-09-10T20:17:39Z","content_type":"text/x-phabricator-request","last_change_time":"2026-08-18T15:20:54Z","id":9512694,"summary":"Bug 1987624 - wasm: Add test. r?yury","is_obsolete":0,"creator":"rhunt@eqrion.net","size":48,"is_private":0},{"description":"(secure)","creator_detail":{"nick":"rhunt","real_name":"Ryan Hunt [:rhunt]","id":573202,"name":"rhunt@eqrion.net","email":"rhunt@eqrion.net"},"is_patch":0,"attacher":"rhunt@eqrion.net","bug_id":1987624,"flags":[{"id":2306846,"modification_date":"2025-09-20T14:12:04Z","setter":"phab-bot@bmo.tld","type_id":721,"name":"approval-mozilla-beta","creation_date":"2025-09-19T19:13:16Z","status":"+"}],"id":9514402,"last_change_time":"2025-09-20T14:12:04Z","file_name":"phabricator-D265496-url.txt","content_type":"text/x-phabricator-request","creation_time":"2025-09-19T19:13:16Z","is_private":0,"creator":"rhunt@eqrion.net","size":48,"summary":"(secure)","is_obsolete":0},{"creator_detail":{"real_name":"Ryan Hunt [:rhunt]","nick":"rhunt","id":573202,"email":"rhunt@eqrion.net","name":"rhunt@eqrion.net"},"description":"(secure)","is_patch":0,"attacher":"rhunt@eqrion.net","bug_id":1987624,"flags":[{"creation_date":"2025-09-19T19:13:50Z","status":"+","type_id":968,"setter":"phab-bot@bmo.tld","name":"approval-mozilla-esr140","id":2306847,"modification_date":"2025-09-22T14:01:25Z"}],"id":9514403,"last_change_time":"2025-09-22T14:01:25Z","file_name":"phabricator-D265497-url.txt","creation_time":"2025-09-19T19:13:50Z","content_type":"text/x-phabricator-request","is_private":0,"size":48,"creator":"rhunt@eqrion.net","is_obsolete":0,"summary":"(secure)"}]}}

## Saved test and candidate files
- evidence/candidate_01_c001_crash_data.txt: https://bugzilla.mozilla.org/rest/bug/attachment/9512241
