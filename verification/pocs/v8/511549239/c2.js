class Node {
  constructor(fn) { this.fn = fn; }
  run(x) { return this.fn(x); }
}
function recur(x) {
  if (x <= 0) return 0;
  return n.run(x - 1) + 1;
}
let n = new Node(recur);
%PrepareFunctionForOptimization(recur);
%PrepareFunctionForOptimization(Node.prototype.run);
for (let i = 0; i < 20000; i++) { recur(5); }
%OptimizeMaglevOnNextCall(recur);
recur(5);
print("done");
