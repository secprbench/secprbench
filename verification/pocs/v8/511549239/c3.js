function other(x) { return x * 2; }
function recur(x, useRecur) {
  let f = useRecur ? recur : other;
  if (x <= 0) return 0;
  return f(x - 1, useRecur) + 1;
}
%PrepareFunctionForOptimization(recur);
%PrepareFunctionForOptimization(other);
for (let i = 0; i < 20000; i++) { recur(5, true); recur(5, false); }
%OptimizeMaglevOnNextCall(recur);
recur(5, true);
print("done");
