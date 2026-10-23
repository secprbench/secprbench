function recur(x) {
  if (x <= 0) return 0;
  return arguments.callee(x - 1) + 1;
}

%PrepareFunctionForOptimization(recur);
for (let i = 0; i < 20000; i++) {
  recur(5);
}

%OptimizeMaglevOnNextCall(recur);
recur(5);
print("done");
