function callee(x) { return x + 1; }
function caller(n) {
  let f = callee;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    if (i % 2 === 0) { f = callee; } else { f = callee; }
    sum += f(i);
  }
  return sum;
}
%PrepareFunctionForOptimization(caller);
for (let i = 0; i < 20000; i++) { caller(10); }
%OptimizeMaglevOnNextCall(caller);
caller(10);
print("done");
