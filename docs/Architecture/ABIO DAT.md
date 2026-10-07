:>> [[ABIO]] → [[ABIO Docs]] → [ABIO DAT](ha://p/ABIO%20DAT) 
# ABIO DAT
**Topic**: ~~[[ABIO Topics]]~~ 
What alienbio actually uses [dvc_dat](https://github.com/oblinger/dvc-dat) for.

## Overview

Rewritten 2026-10-07 (T067). dvc-dat moved to `~/ob/grove/dvc-dat` and went
to **3.0**, which retired the module-level `do()` function, the `Dat.spec`
attribute, the runnable-spec surface and `DatManager.sync_folder`. The page
below describes the surface alienbio depends on, which is much smaller than
the one it used to document.

**What the package uses.** `alienbio` imports exactly one name from the
library — `Dat` — and uses it as a *duck-typed anchor*: the thing an
`Entity` carries so it has an identity and a place on disk. Every synthetic
object carries a `MockDat(f"{prefix}/{name}")` instead (`infra/mk.py`,
`bio/molecule.py`, `bio/reaction.py`, `bio/chemistry.py`,
`suite/runner.py`), so the overwhelming majority of a run never touches the
store at all. `infra/io.py` is the only module that reads the live manager.

**What it does not use.** The do-system (dotted names resolved through
`do()` / `Dat.do`), runnable specs (`dat.run()`), the ledger, and the
artifact store. The do-system left alienbio with the M1 scenario runtime in
M47.7; a spec is an [[ABIO Expr Spec|Expr]] document now, loaded by
`suite/spec.py`, and an experiment is run by `bio suite run`.

## Configuration

**There is none, deliberately.** The repo carried a `.dataconfig.yaml`
(`sync_folder:` + three `mount_commands:`) until 2026-10-07; 3.0 reads
`.datconfig.yaml` and accepts only `dat_folders` / `art_folder` / `index` /
`manager` / `verify`, so that file had been **silently ignored** — and the
mounts it declared were do-namespaces nothing resolves any more. It was
deleted rather than translated, because the translation is exactly 3.0's
default:

- dat folders — `data/` beside the config root.
- artifact folder — `art/` beside it (gitignored; any test that touches a
  real `Dat` creates it).

A later need for a non-default location is a `.datconfig.yaml` with
`dat_folders:`, not a revival of the old keys.

## The surface, as the package sees it

| Call | What alienbio does with it |
|---|---|
| `Dat` | the anchor type an `Entity` carries; also a `TYPE_CHECKING`-only import in the bio classes |
| `Dat.create(path=…, spec=…)` | writes a dat folder; `infra/io.py` persistence and the unit round-trip |
| `Dat.load(path)` | reads one back |
| `dat.get_spec()` | the spec dict (3.0's accessor; 2.x exposed a `spec` attribute) |
| `Dat.manager` | the world; `infra/io.py` reads its first dat folder for the `D:` prefix root |
| `MockDat` | alienbio's own stand-in, used everywhere a real folder is not wanted |

## Development setup

`src/dvc_dat` is a **gitignored dev symlink** into the live repo:

```
src/dvc_dat -> /Users/oblinger/ob/grove/dvc-dat/dvc_dat
```

So alienbio tracks dvc-dat's `main` rather than a pinned release, and a
breaking change there lands here on the next test run. That is how 3.0
arrived: the symlink dangled after the repo moved and every test failed to
collect until it was repointed (alienbio `80c6bef`). `pandas` is declared in
the `dev` extra for the same reason — 3.0's `dat_tools` imports it at module
scope.

## See Also

- [dvc_dat concepts](https://github.com/oblinger/dvc-dat/blob/main/docs/concepts.md) — the library's own mental model
- [[ABIO Expr Spec]] — what a spec is in this package now
- ~~[[ABIO Files]]~~ — where everything lives
- [[ABIO Data]] — the `data/` folder
- [[ABIO alienbio]] — the package's top-level exports
