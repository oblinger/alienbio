# Bio CLI
**Parent**: [[ABIO Topics]]

Command-line interface for Alien Biology simulations.

---

## Usage

```bash
bio <command> [arguments...]
```

Each command has its own argument structure. See individual commands below.

Commands take a **bioref** argument—see [[Bio]] for bioref syntax.

---

## Commands

### `report`

Run scenarios and generate a summary report.

```bash
bio report <bioref>
```

**Behavior:**
- If bioref resolves to a **scope**: finds all scenarios within, runs each, generates table
- If bioref resolves to a **scenario**: runs it and reports its scores

**Examples:**
```bash
bio report catalog/scenarios/mutualism/experiments
bio report catalog/scenarios/mutualism/experiments.baseline
```

**Output:**
```
| scenario          | score | outcome | investigation | caution |
|-------------------|-------|---------|---------------|---------|
| baseline          | 0.72  | 0.85    | 0.60          | 1.00    |
| hidden_dependency | 0.58  | 0.70    | 0.45          | 0.30    |
| false_belief      | 0.45  | 0.60    | 0.30          | 0.30    |
```

---

## DAT Integration

DATs specify execution as a `bio` command:

```yaml
# _spec_.yaml
dat:
  kind: Dat
  do: bio
  command: "report experiments"
```

When `dat.run()` is called, it executes `bio report experiments` in the DAT folder context. The bioref `experiments` is relative to the current DAT.

---

## See Also

- [[Bio]] — Python API (`Bio.fetch()`, `Bio.sim()`, etc.)
- [[Spec Language]] — YAML syntax for modules
- [[Scope]] — Scope class and inheritance
