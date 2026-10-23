const v = new FinalizationRegistry(() => {});
v.unregister();
