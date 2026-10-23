function f0(x){return x+0;}
function f1(x){return x+1;}
function f2(x){return x+2;}
function f3(x){return x+3;}
function f4(x){return x+4;}
function f5(x){return x+5;}
function f6(x){return x+6;}

function caller(x, fns, idx) {
  if (x <= 0) return 0;
  let f = fns[idx % fns.length];
  return f(x, fns, idx + 1);
}

let fns = [f0, f1, f2, f3, f4, f5, f6, caller];

%PrepareFunctionForOptimization(caller);
for (let i = 0; i < 20000; i++) {
  caller(3, fns, i % fns.length);
}

%OptimizeMaglevOnNextCall(caller);
caller(3, fns, 7); // calls caller itself indirectly via array of funcs
print("done");
