function recur(x) {
  let self = recur;
  function helper() {
    return self(x - 1) + 1;
  }
  if (x <= 0) return 0;
  return helper();
}
%PrepareFunctionForOptimization(recur);
for (let i = 0; i < 20000; i++) { recur(5); }
%OptimizeMaglevOnNextCall(recur);
recur(5);
print("done");
