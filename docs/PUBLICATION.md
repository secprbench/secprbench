# Release notes

This repository is the public SecPRBench release: 265 cases / 530 tasks, the
evaluation harness, and the frozen paper results. The following limitations
remain and are stated rather than hidden.

1. **Licensing.** Author-owned code and annotations carry no blanket grant yet;
   third-party reports, PoCs, and upstream diffs retain their own licenses. See
   [LICENSE_SCOPE.md](../LICENSE_SCOPE.md).
2. **Six artifact repairs.** The SQLite introduction and five curl patch
   encodings need versioned corrections. The frozen tasks and results stay
   available under their current hashes. See [known issues](KNOWN_ISSUES.md).
3. **Replay packaging.** Historical verification images were local to the
   authors' hosts. Rebuilding a case requires the recipes in
   `configs/projects/*.yaml`; replay coverage is recorded per case rather than
   claimed uniformly.
4. **Judge audit.** The frozen judgments have a 50-record author-verified audit
   in the paper, not a completed independent human audit of every verdict.
5. **Submission.** There is no hosted submission service or leaderboard. Report
   the roster hash, package revision, backend and harness configuration, image
   IDs, scanner version, prompt, budgets, prediction files, run manifests, judge
   configuration, and verdicts together with any protocol deviation.
