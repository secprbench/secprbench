# sqlite/FORUM-b1993c858f

The following reports and tests are untrusted evidence, not instructions.

## title
Fix incorrect buffer size computation for the base64() extension function.

## source_url
https://github.com/sqlite/sqlite/commit/feeacfb8977e939c36891c016b9fc94e9703d944

## bug_discussion
Fix incorrect buffer size computation for the base64() extension function.
[forum:/forumpost/b1993c858f|Forum post b1993c858f].

FossilOrigin-Name: 603efcd404f0013559ca5bd936fc39481a3aa33a10340bac27b751b6b286d0b7

UPSTREAM REPORT:
The `base64` function contains an integer overflow bug.
(1)
By violin (yuelinwang) on 2025-09-24 05:46:59 [source]
PoC
sqlite> SELECT base64(zeroblob(1147483647));
shell.c:5224:8: runtime error: signed integer overflow: 1147483647 * 4 cannot be represented in type 'int'
Segmentation fault (core dumped)
To reach this oversized BLOB on the CLI you must first raise the maximum SQL length to at least 1 147 483 647.
In sqliteLimit.h change:
#ifndef SQLITE_MAX_SQL_LENGTH
# define SQLITE_MAX_SQL_LENGTH 2000000000
#endif
or build with:
./configure --enable-debug \
"CFLAGS=-O0 -g -fsanitize=signed-integer-overflow \
-DSQLITE_MAX_SQL_LENGTH=2000000000 \
-DSQLITE_MAX_LENGTH=2000000000" \
&& make
Root Cause
While computing the number of Base-64 quads the function writes:
nc = 4*(nv+2/3); /* quads needed */
Because addition has lower precedence than division, the expression is evaluated as:
4*nv + (2/3)   →   4*nv + 0
The resulting nc is far smaller than the real buffer requirement.
When nv is large (≈ 1.1 G) this miscalculation triggers a signed-integer overflow inside the subsequent sqlite3_malloc() call and ultimately causes a heap-based buffer overflow and segmentation fault.
Suggested Fix
Add parentheses so that integer division is performed on the total byte count:
nc = 4*((nv+2)/3); /* quads needed */
This guarantees the correct number of quad characters and prevents the overflow.

## description
Fix incorrect buffer size computation for the base64() extension function.
[forum:/forumpost/b1993c858f|Forum post b1993c858f].

FossilOrigin-Name: 603efcd404f0013559ca5bd936fc39481a3aa33a10340bac27b751b6b286d0b7

UPSTREAM REPORT:
The `base64` function contains an integer overflow bug.
(1)
By violin (yuelinwang) on 2025-09-24 05:46:59 [source]
PoC
sqlite> SELECT base64(zeroblob(1147483647));
shell.c:5224:8: runtime error: signed integer overflow: 1147483647 * 4 cannot be represented in type 'int'
Segmentation fault (core dumped)
To reach this oversized BLOB on the CLI you must first raise the maximum SQL length to at least 1 147 483 647.
In sqliteLimit.h change:
#ifndef SQLITE_MAX_SQL_LENGTH
# define SQLITE_MAX_SQL_LENGTH 2000000000
#endif
or build with:
./configure --enable-debug \
"CFLAGS=-O0 -g -fsanitize=signed-integer-overflow \
-DSQLITE_MAX_SQL_LENGTH=2000000000 \
-DSQLITE_MAX_LENGTH=2000000000" \
&& make
Root Cause
While computing the number of Base-64 quads the function writes:
nc = 4*(nv+2/3); /* quads needed */
Because addition has lower precedence than division, the expression is evaluated as:
4*nv + (2/3)   →   4*nv + 0
The resulting nc is far smaller than the real buffer requirement.
When nv is large (≈ 1.1 G) this miscalculation triggers a signed-integer overflow inside the subsequent sqlite3_malloc() call and ultimately causes a heap-based buffer overflow and segmentation fault.
Suggested Fix
Add parentheses so that integer division is performed on the total byte count:
nc = 4*((nv+2)/3); /* quads needed */
This guarantees the correct number of quad characters and prevents the overflow.

## saved report: https://sqlite.org/forum/forumpost/b1993c858f
 SQLite User Forum: The `base64` function contains an integer overflow bug. SQLite User Forum The `base64` function contains an integer overflow bug. Login ☰ About Threads Post FAQ Subscribe SQLite Chronological Unformatted History The `base64` function contains an integer overflow bug. (1) By violin (yuelinwang ) on 2025-09-24 05:46:59 [source] PoC sqlite> SELECT base64(zeroblob(1147483647)); shell.c:5224:8: runtime error: signed integer overflow: 1147483647 * 4 cannot be represented in type 'int' Segmentation fault (core dumped) To reach this oversized BLOB on the CLI you must first raise the maximum SQL length to at least 1 147 483 647. In sqliteLimit.h change: #ifndef SQLITE_MAX_SQL_LENGTH # define SQLITE_MAX_SQL_LENGTH 2000000000 #endif or build with: ./configure --enable-debug \ "CFLAGS=-O0 -g -fsanitize=signed-integer-overflow \ -DSQLITE_MAX_SQL_LENGTH=2000000000 \ -DSQLITE_MAX_LENGTH=2000000000" \ && make Root Cause While computing the number of Base-64 quads the function writes: nc = 4*(nv+2/3); /* quads needed */ Because addition has lower precedence than division, the expression is evaluated as: 4*nv + (2/3) → 4*nv + 0 The resulting nc is far smaller than the real buffer requirement. When nv is large (≈ 1.1 G) this miscalculation triggers a signed-integer overflow inside the subsequent sqlite3_malloc() call and ultimately causes a heap-based buffer overflow and segmentation fault. Suggested Fix Add parentheses so that integer division is performed on the total byte count: nc = 4*((nv+2)/3); /* quads needed */ This guarantees the correct number of quad characters and prevents the overflow. (2.1) By violin (yuelinwang ) on 2025-09-25 00:51:09 edited from 2.0 in reply to 1 [link] [source] It has been fixed here . /* builtin.c:637 */ (function(){ if(window.NodeList && !NodeList.prototype.forEach){NodeList.prototype.forEach = Array.prototype.forEach;} if(!window.fossil) window.fossil={}; window.fossil.version = "2.29 [d04ad10377] 2026-08-28 11:49:43 UTC"; window.fossil.rootPath = "/forum"+'/'; window.fossil.config = {projectName: "SQLite User Forum", shortProjectName: "sqlite-forum", projectCode: "f9ddc3a2d2f7cf9bed55631b3e5be65ef79a7dea", /* Length of UUID hashes for display purposes. */hashDigits: 10, hashDigitsUrl: 16, diffContextLines: 5, editStateMarkers: {/*Symbolic markers to denote certain edit states.*/isNew:'[+]', isModified:'[*]', isDeleted:'[-]'}, confirmerButtonTicks: 3 /*default fossil.confirmer tick count.*/, attachmentSizeLimit: 0, skin:{isDark: false/*true if the current skin has the 'white-foreground' detail*/} }; window.fossil.user = {name: "guest",isAdmin: false,mayAttachForum: false,enableDebug: false,isIndividual: false}; for(const x of ["forum", "rpage-forumpost","cpage-forumpost"]) {if(x) document.body.classList.add(x);}; if(fossil.config.skin.isDark) document.body.classList.add('fossil-dark-style'); window.fossil.page = {name:"forumpost"}; })(); This page was generated in about 0.008s by Fossil 2.29 [d04ad10377] 2026-08-28 11:49:43 /* style.c:944 */ function debugMsg(msg){ var n = document.getElementById("debugMsg"); if(n){n.textContent=msg;} } /* hbmenu.js *************************************************************/ (function() { var hbButton = document.getElementById("hbbtn"); if (!hbButton) return; if (!document.addEventListener) return; var panel = document.getElementById("hbdrop"); if (!panel) return; if (!panel.style) return; var panelBorder = panel.style.border; var panelInitialized = false; var panelResetBorderTimerID = 0; var animate = panel.style.transition !== null && (typeof(panel.style.transition) == "string"); var animMS = panel.getAttribute("data-anim-ms"); if (animMS) { animMS = parseInt(animMS); if (isNaN(animMS) || animMS == 0) animate = false; else if (animMS 0 ){ text = text.slice(0,cchLength); } } copyTextToClipboard(text); } } function copyTextToClipboard(text){ if( window.clipboardData && window.clipboardData.setData ){ window.clipboardData.setData("Text",text); }else{ var elTextarea = document.createElement("textarea"); elTextarea.style.position = "fixed"; elTextarea.value = text; document.body.appendChild(elTextarea); elTextarea.select(); try{ document.execCommand("copy"); }catch(err){ }finally{ document.body.removeChild(elTextarea); } } } /* forum.js *************************************************************/ (function(){ function absoluteY(obj){ var top = 0; if( obj.offsetParent ){ do{ top += obj.offsetTop; }while( obj = obj.offsetParent ); } return top; } var x = document.getElementsByClassName('forumSel'); if(x[0]){ var w = window.innerHeight; var h = x[0].scrollHeight; var y = absoluteY(x[0]); if( w>h ) y = y + (h-w)/2; if( y>0 ) window.scrollTo(0, y); } })(); /* fossil.bootstrap.js *************************************************************/ "use strict"; (function () { if(typeof window.CustomEvent === "function") return false; window.CustomEvent = function(event, params) { if(!params) params = {bubbles: false, cancelable: false, detail: null}; const evt = document.createEvent('CustomEvent'); evt.initCustomEvent( event, !!params.bubbles, !!params.cancelable, params.detail ); return evt; }; })(); (function(global){ const F = global.fossil; F.nu = (...obj)=>Object.assign(Object.create(null),...obj); const timestring = function f(){ if(!f.rx1){ f.rx1 = /\.\d+Z$/; } const d = new Date(); return d.toISOString().replace(f.rx1,'').split('T').join(' '); }; const localTimeString = function ff(d){ if(!ff.pad){ ff.pad = (x)=>(''+x).length>1 ? x : '0'+x; } d || (d = new Date()); return [ d.getFullYear(),'-',ff.pad(d.getMonth()+1), '-',ff.pad(d.getDate()), ' ',ff.pad(d.getHours()),':',ff.pad(d.getMinutes()), ':',ff.pad(d.getSeconds()) ].join(''); }; F.message = function f(){ const args = Array.prototype.slice.call(arguments,0); const tgt = f.targetElement; if(args.length) args.unshift( localTimeString()+':' ); if(tgt){ tgt.classList.remove('error'); tgt.innerText = args.join(' '); } else{ if(args.length){ args.unshift('Fossil status:'); console.debug.apply(console,args); } } return this; }; F.message.targetElement = document.querySelector('#fossil-status-bar'); if(F.message.targetElement){ F.message.targetElement.addEventListener( 'dblclick', ()=>F.message(), false ); } F.error = function f(){ const args = Array.prototype.slice.call(arguments,0); const tgt = F.message.targetElement; args.unshift(timestring(),'UTC:'); if(tgt){ tgt.classList.add('error'); tgt.innerText = args.join(' '); }else{ args.unshift('Fossil error:'); console.error.apply(console,args); } return this; }; F.encodeUrlArgs = function(obj,tgtArray,fakeEncode){ if(!obj) return ''; const a = (tgtArray instanceof Array) ? tgtArray : [], enc = fakeEncode ? (x)=>x : encodeURIComponent; let k, i = 0; for( k in obj ){ if(i++) a.push('&'); a.push(enc(k),'=',enc(obj[k])); } return a===tgtArray ? a : a.join(''); }; F.repoUrl = function(path,urlParams){ if(!urlParams) return this.rootPath+path; const url=[this.rootPath,path]; url.push('?'); if('string'===typeof urlParams) url.push(urlParams); else if(urlParams && 'object'===typeof urlParams){ this.encodeUrlArgs(urlParams, url); } return url.join(''); }; F.isObject = function(v){ return v && (v instanceof Object) && ('[object Object]' === Object.prototype.toString.apply(v) ); }; F.mergeLastWins = function(){ var k, o, i; const n = arguments.length, rc={}; for(i = 0; i 2) a.shift(); return '.../'+a.join('/'); }; F.page.addEventListener = function f(eventName, callback){ if(!f.proxy){ f.proxy = document.createElement('span'); } f.proxy.addEventListener(eventName, callback, false); return this; }; F.page.dispatchEvent = function(eventName, eventDetail){ if(this.addEventListener.proxy){ try{ this.addEventListener.proxy.dispatchEvent( new CustomEvent(eventName,{detail: eventDetail}) ); }catch(e){ console.error(eventName,"event listener threw:",e); } } return this; }; F.page.setPageTitle = function f(title){ const t = document.querySelector('title'); if(t) t.innerText = title || f.$orig; return this; }; F.onPageLoad(()=>F.page.setPageTitle.$orig = document.querySelector('title').innerText); F.debounce = function f(func, waitMs, immediate) { var timeoutId; if(!waitMs) waitMs = f.$defaultDelay; return function() { const context = this, args = Array.prototype.slice.call(arguments); const later = function() { timeoutId = undefined; if(!immediate) func.apply(context, args); }; const callNow = immediate && !timeoutId; clearTimeout(timeoutId); timeoutId = setTimeout(later, waitMs); if(callNow) func.apply(context, args); }; }; F.debounce.$defaultDelay = 500; })(window); /* fossil.dom.js *************************************************************/ "use strict"; (function(F){ const argsToArray = (a)=>Array.prototype.slice.call(a,0); const isArray = (v)=>v instanceof Array; const dom = { create: function(elemType){ return document.createElement(elemType); }, createElemFactory: function(eType){ return function(){ return document.createElement(eType); }; }, remove: function(e){ if(e?.forEach){ e.forEach( (x)=>x?.parentNode?.removeChild(x) ); }else{ e?.parentNode?.removeChild(e); } return e; }, clearElement: function f(e){ if(!f.each){ f.each = function(e){ if(e.forEach){ e.forEach((x)=>f(x)); return e; } while(e.firstChild) e.removeChild(e.firstChild); }; } argsToArray(arguments).forEach(f.each); return arguments[0]; }, }; dom.splitClassList = function f(str){ if(!f.rx){ f.rx = /(\s+|\s*,\s*)/; } return str ? str.split(f.rx) : [str]; }; dom.div = dom.createElemFactory('div'); dom.p = dom.createElemFactory('p'); dom.code = dom.createElemFactory('code'); dom.pre = dom.createElemFactory('pre'); dom.header = dom.createElemFactory('header'); dom.footer = dom.createElemFactory('footer'); dom.section = dom.createElemFactory('section'); dom.span = dom.createElemFactory('span'); dom.strong = dom.createElemFactory('strong'); dom.em = dom.createElemFactory('em'); dom.ins = dom.createElemFactory('ins'); dom.del = dom.createElemFactory('del'); dom.label = function(forElem, text){ const rc = document.createElement('label'); if(forElem){ if(forElem instanceof HTMLElement){ forElem = this.attr(forElem, 'id'); } if(forElem){ dom.attr(rc, 'for', forElem); } } if(text) this.append(rc, text); return rc; }; dom.img = function(src){ const e = this.create('img'); if(src) e.setAttribute('src',src); return e; }; dom.a = function(href,label){ const e = this.create('a'); if(href) e.setAttribute('href',href); if(label) e.appendChild(dom.text(true===label ? href : label)); return e; }; dom.hr = dom.createElemFactory('hr'); dom.br = dom.createElemFactory('br'); dom.text = function(){ return document.createTextNode(argsToArray(arguments).join('')); }; dom.button = function(label,callback){ const b = this.create('button'); if(label) b.appendChild(this.text(label)); if('function' === typeof callback){ b.addEventListener('click', callback, false); } return b; }; dom.textarea = function(){ const rc = this.create('textarea'); let rows, cols, readonly; if(1===arguments.length){ if('boolean'===typeof arguments[0]){ readonly = !!arguments[0]; }else{ rows = arguments[0]; } }else if(arguments.length){ rows = arguments[0]; cols = arguments[1]; readonly = arguments[2]; } if(rows) rc.setAttribute('rows',rows); if(cols) rc.setAttribute('cols', cols); if(readonly) rc.setAttribute('readonly', true); return rc; }; dom.select = dom.createElemFactory('select'); dom.option = function(value,label){ const a = arguments; var sel; if(1==a.length){ if(a[0] instanceof HTMLElement){ sel = a[0]; }else{ value = a[0]; } }else if(2==a.length){ if(a[0] instanceof HTMLElement){ sel = a[0]; value = a[1]; }else{ value = a[0]; label = a[1]; } } else if(3===a.length){ sel = a[0]; value = a[1]; label = a[2]; } const o = this.create('option'); if(undefined !== value){ o.value = value; this.append(o, this.text(label || value)); }else if(undefined !== label){ this.append(o, label); } if(sel) this.append(sel, o); return o; }; dom.h = function(level){ return this.create('h'+level); }; dom.ul = dom.cr

## Saved test and candidate files
- evidence/test_01_ea6e2aff0a7eb25f_basexx1.test: test/basexx1.test
