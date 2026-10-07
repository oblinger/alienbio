:>> [[ABIO]] → [[ABIO Docs]] → [ABIO Data](ha://p/ABIO%20Data) 
 [[ABIO Architecture Docs]] → [[ABIO infra]] 
# ABIO Data
What the `data/` folder actually holds, and why nothing is filed there on purpose.

Rewritten 2026-10-07 (T067). The page used to describe an intent-based tree
— `chem/kegg1/` for a reusable chemistry, `world/simple1/chem/` for a
world's own, `test/T1/world/chem/` for a test's — with the rule that a
top-level category names the thing's primary purpose. **None of it was ever
built**, and the design it belonged to (the M1 scenario runtime, its spec
language and the do-system that resolved those names) was deleted in M47.7
and T056.

## What is there now

`data/` is **gitignored scratch**: the default dat folder
[dvc_dat](https://github.com/oblinger/dvc-dat) writes into when something
creates a real `Dat` rather than a `MockDat` ([[ABIO DAT]]). On this machine
it is ~10 MB of `data/anonymous/Dat_<n>/` folders — 2,662 of them, each a
`_spec_.yaml` left by a test that did not name its dat. Nothing reads them
back, nothing is durable, and deleting the folder costs nothing.

The outputs that *are* meant to be read each have their own place, all
gitignored:

- **`runs/<name>/`** — one experiment run: `records.jsonl`, `manifest.json`,
  `report.txt`, `key.png` / `key.json`. Written by `bio suite run`, read
  back by `bio suite resume|aggregate|report`.
- **`reports/`** — `bio report`'s page: `report.md`, `report.html`,
  `junit.xml`.
- **`art/`** — dvc-dat 3.0's artifact store, beside the dat folder.

## Where the durable things live instead

Nothing a later run depends on is in `data/`. The inputs are checked in:
`catalog/experiments/*.yaml` (the thirteen zeros), `catalog/examples/*/`
(the nine coverage worlds), `catalog/registrations.yaml` (the licences), and
the goldens pinned in `tests/suite/test_golden_experiments.py`. That is the
whole contract — a clone with an empty `data/` reproduces every zero.

## See Also
- [[ABIO DAT]] — the dvc-dat surface alienbio actually uses
- ~~[[ABIO Files]]~~ — the full repository layout
