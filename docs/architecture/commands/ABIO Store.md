 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio.store()

Sync a DAT to remote storage.

---

## CLI

```bash
bio store                    # store current DAT to remote
bio store <path>             # store specified DAT to remote
```

---

## Python API

```python
from alienbio import bio

# Store a DAT to remote
bio.store("data/experiments/run1")
```

---

## Behavior

During a run, results and reports are written directly to the local DAT folder. When you call `store()`:

1. Any cached in-memory data associated with the DAT is flushed to the filesystem
2. The DAT is synced to remote cloud storage

This is the inverse of [fetch()](ABIO Fetch.md) — fetch pulls from remote to local, store pushes from local to remote.

---

## Status

*Remote sync is planned for later. Currently, DATs exist only in the local filesystem.*

---

## See Also

- [fetch()](ABIO Fetch.md) — Load DATs (pulls from remote if not local)
- [DAT](../classes/infra/DAT.md) — DAT folder structure
- [Bio](../classes/infra/Bio.md) — Bio class overview
