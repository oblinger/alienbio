 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio.lookup()

Internal name resolution used by [fetch()](ABIO Fetch.md).

---

## Overview

`lookup()` resolves dotted names (no slashes) through Python modules and configured roots. It is called internally by `fetch()` when the specifier contains no slashes.

**Most users should use `fetch()` directly** — it handles all specifier types and calls `lookup()` automatically when needed.

See [fetch() → Resolution Order](ABIO Fetch.md#resolution-order) for the complete resolution rules.

---

## When lookup() is Used

```python
# fetch() calls lookup() for dotted names (no slashes)
bio.fetch("scenarios.mutualism")
# → internally calls lookup("scenarios.mutualism")

# fetch() does NOT call lookup() for paths (has slashes)
bio.fetch("catalog/scenarios/mutualism")
# → direct DAT load, no lookup
```

---

## Resolution Order

When `lookup(name)` is called:

1. **Python modules** — check `sys.modules` for first segment, then navigate with getattr
2. **Configured roots** — scan mounts and sync_folders, convert dots to path separators
3. **Dereference** — after finding root, remaining dots dereference into content via `gets()`

---

## See Also

- [fetch()](ABIO Fetch.md) — Main entry point (calls lookup internally)
- [DAT](../classes/infra/DAT.md) — DAT configuration
- [Scope](../modules/Scope.md) — Scope.lookup() for scope-tree resolution
