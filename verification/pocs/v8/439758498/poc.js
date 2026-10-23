function tryLen(n) {
  var s = "b".repeat(n);
  try {
    s = createExternalizableString(s);
    externalizeString(s);
  } catch (e) {
    print("len=" + n + " externalize failed: " + e);
    return;
  }
  var re = /a/g;
  var res = s.match(re);
  print("len=" + n + " match result=" + res);
}
for (var n of [1,2,3,4,5,6,7,8,9,10,15,17,20,30,33,49,50,63,65,70,100,127,129,200,255,257]) {
  tryLen(n);
}
