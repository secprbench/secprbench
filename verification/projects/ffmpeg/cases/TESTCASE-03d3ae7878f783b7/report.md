# Verification report: pr_review_TESTCASE-03d3ae7878f783b7

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `e32264a1e17a18e8b0e8d86c2171a73b8515f1c6`
- **Intro parent**: `3cd5672bfeb796342d24228a78f2e733c0a40e7d`
- **Fix commit**: `28c330d0f3f3301128cab541774924de9ca78e5b`
- **Affected files**: ['libavformat/mov.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/612365b72a91e7dd0abd/attempts/01/pocs/ffmpeg/TESTCASE-03d3ae7878f783b7`
- input: `heif_notype.mp4` (129 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Built pre_intro (3cd5672bfeb7), post_intro (e32264a1e17a) and post_benign (companion fix applying 28c330d0f3f3's logic) with ASan in Docker and ran the identical crafted PoC (/poc/heif_overwrite.mp4) through the real target demuxer (`/work/ffmpeg -v trace -i /poc/heif_overwrite.mp4 -f null -`) in all three. Verified via source inspection that post_intro's mov_read_infe/mov_read_iloc contain the id-search loop '`for(...){ item=heif_item[j]; if(!item) allocate; else if(item->item_id!=item_id) continue; break; } if(!item) return ENOMEM;`' with no check that the loop actually found a match/free slot (matches meta.json root_cause exactly), while post_benign adds `if (j == c->nb_heif_item) return AVERROR_INVALIDDATA;` (confirmed present in post_benign's source, absent in post_intro) — this is precisely the upstream fix 28c330d0f3f3 ("abort if the queried item doesn't exist instead of overwriting it"). pre_intro predates this whole id-search refactor and instead writes items purely positionally (each iloc/infe entry indexed by its own sequential position), so it never hits this particular overwrite-without-a-found-check flaw — it produces two independently-built, fully-populated sample indices for both items (confirmed via two 'AVIndex stream N, sample 0, offset ...' trace lines, one per stream). post_intro instead shows only one AVIndex line (for the final, repurposed item); the stream created for item id=200 is left with an unbuilt/never-visited sample table (its HEIFItem slot got silently reassigned to id=300), i.e. the exact 'last item in the array being overwritten' defect described in the fix's commit message. post_benign, with the abort check restored, refuses to open this file at all ('error reading header' / 'Invalid data found when processing input'), matching the intended fixed behavior of rejecting rather than corrupting. The divergence (open+corrupt-stream in post_intro vs open+clean in pre_intro vs reject in post_benign) is fully deterministic and reproduces on every run.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "RESULT: STREAM0_ORPHANED_BUG (item 0xc8 stream opened but has no backing sample index; its HEIFItem slot was silently overwritten by a mismatched item id)"
- pre_marker: "RESULT: STREAM0_INDEXED_OK (item 0xc8 properly retained its own extent/index)"
- benign_marker: "RESULT: HEADER_REJECTED (file rejected as invalid)"
- target execution: Trace log excerpt (post_intro): only 'AVIndex stream 1, sample 0, offset 0, dts 0, size 0, distance 0, keyframe 1' is logged during header parse (no 'AVIndex stream 0' line at all), vs pre_intro logging both 'AVIndex stream 0, sample 0, offset 92, dts 0, size 4, ...' and 'AVIndex stream 1, sample 0, offset 0, ...'. post_benign logs 'error reading header' / 'Invalid data found when processing input' and never constructs any stream. Source diff confirms: post_intro's mov_read_infe/mov_read_iloc loops end with 'if (!item) return AVERROR(ENOMEM);' only, while post_benign additionally has 'if (i == c->nb_heif_item) return AVERROR_INVALIDDATA;' (mov_read_infe) and 'if (j == c->nb_heif_item) return AVERROR_INVALIDDATA;' (mov_read_iloc) right after the search loop, matching fix commit 28c330d0f3f3.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=3cd5672bfeb7  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=c710e92a43d4a647389cb7258de10adb35a94ec56fd112b7aa180a018d92df4e
  source_integrity=True
  output_tail:
    RESULT: STREAM0_INDEXED_OK (item 0xc8 properly retained its own extent/index)
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=e32264a1e17a  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=c710e92a43d4a647389cb7258de10adb35a94ec56fd112b7aa180a018d92df4e
  source_integrity=True
  output_tail:
    RESULT: STREAM0_ORPHANED_BUG (item 0xc8 stream opened but has no backing sample index; its HEIFItem slot was silently overwritten by a mismatched item id)
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=3cd5672bfeb7  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=c710e92a43d4a647389cb7258de10adb35a94ec56fd112b7aa180a018d92df4e
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    RESULT: HEADER_REJECTED (file rejected as invalid)
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
