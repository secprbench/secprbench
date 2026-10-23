var x = newGlobal({ newCompartment: true });
var y = Debugger(x);
y.x = y;
y.onDebuggerStatement = function(w) {
  nukeAllCCWs();
  try {
    w.environment.getVariable("x");
    print("NO_EXCEPTION");
  } catch (e) {
    print("CAUGHT: " + e);
  }
}
x.eval('function f(z) { with(z) { debugger } }');
x.f(y);
print("DONE");
