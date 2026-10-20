---
description: "The Python side of Expr — every way a spec reaches Python, from an inline formula to a registered expander to a trusted !py reference — with an example of each, the injection convention, and the trust model that keeps untrusted specs inside the registry."
---
:>> [[ABIO]] → [[ABIO Design]] → [[ABIO Expr]] → [ABIO Expr Python Escapes](ha://p/ABIO%20Expr%20Python%20Escapes) 
# ABIO Expr Python Escapes
How a spec written in [[ABIO Expr]] reaches Python — the escapes, ordered from the smallest (a formula on one line) to the largest (a module the spec loads), with an example of each.

| Table of Contents |  |
|---|---|
| **[[#The ladder]]** |  |
| **[[#1. Inline formula — `!x`]]** |  |
| **[[#2. Deferred formula — `!q`]]** |  |
| **[[#3. Registered function — `@fn`]]** |  |
| **[[#4. Registered expander — `@expander`]]** |  |
| **[[#5. YAML template — `!template`]]** |  |
| **[[#6. Guard — `@guard`]]** |  |
| **[[#7. Constructor — an `Entity` subclass]]** |  |
| **[[#8. Local Python reference — `!py`]]** |  |
| **[[#9. Python include — `!include helpers.py`]]** |  |
| **[[#The trust model, in one table]]** |  |
| **[[#Testing an escape]]** |  |
| **[[#What is not an escape]]** |  |
| **[[#History]]** |  |

The governing rule ([[ABIO Expr]] § The design stance) is that **logic lives in Python**. So the escapes are not a back door — they are the front door, and the language is designed so that reaching for Python is the ordinary move whenever a template needs to *decide* something rather than *lay out* something. This page is the catalog of those moves. Each escape names what the spec author writes, what the Python author writes, and what the interpreter does between them.

## The ladder

| Escape | Spec side | Python side | Trust |
|---|---|---|---|
| **1. Inline formula** | `!x Vmax * S / (Km + S)` | nothing — the sandbox evaluates it | untrusted OK |
| **2. Deferred formula** | `!q k * S / (Km + S)` | the consumer (simulator, grader) runs it later with its own bindings | untrusted OK |
| **3. Registered function** | `!x hill(S, K, n=2)` | `@fn def hill(...)` | registration is trusted; the call is not |
| **4. Registered expander** | `!conflict_crux {precursor: P}` | `@expander def conflict_crux(args, kwargs, env)` | same |
| **5. YAML template** | `!template {params: …, body: …}` | none — but its body may call 3 and 4 | untrusted OK |
| **6. Guard** | `guards: [no_new_cycles, max_pathway_length(4)]` | `@guard def no_new_cycles(expanded, ctx)` | registration trusted |
| **7. Constructor** | `!Reaction {reactants: [A, B], products: [C]}` | an `Entity` subclass — automatic | untrusted OK |
| **8. Local Python reference** | `!py helpers.compute` | a `.py` file beside the spec | **trusted only** |
| **9. Python include** | `!include helpers.py` | a `.py` file whose decorators register heads | **trusted only** |

Escapes 1–7 are available to an agent-authored spec; they can only *name* what Python has already registered. Escapes 8–9 execute code the spec points at, and stay behind the `trusted=True` gate the loader already enforces (`spec_lang/tags.py` `PyRef.resolve`, `process.resolve_includes`). Nothing in this design loosens that gate.

## 1. Inline formula — `!x`

The smallest escape: a Python *expression* (never a statement) inside a YAML string, parsed by the AST allowlist in `spec_lang/safe_eval.py` and evaluated against the environment. Arithmetic, comparisons, conditionals, f-strings, calls of registered heads, method calls on values.

```yaml
params:
  Vmax: !x lognormal(1.0, 0.3)
  Km: 10
  n: !x 2 if cooperative else 1
kinetics:
  vmax_per_enzyme: !x Vmax / max(enzyme_count, 1)
  label: !x f"{species}-{i:02d}"
```

What it cannot do: import, define, loop (use `each`), assign (use `let`), reach any name not bound in the environment, touch a dunder. A formula that wants any of those is escape 3.

## 2. Deferred formula — `!q`

A quoted form is a *value* — the form itself — handed to whoever evaluates it later with the bindings only they have. The two consumers today are the simulator (rate laws, evaluated per step with concentrations bound) and the grader (scores, evaluated with the `Timeline` bound).

```yaml
reactions:
  r1: {reactants: [S], products: [P], rate: !q Vmax * S / (Km + S)}
scoring:
  health: !q 0.4 * population_health(timeline) + 0.6 * caution(timeline)
```

The consumer evaluates it with `run(form, bindings)` — the same interpreter, a child scope holding the state — or, on the hot path, compiles it once: `spec_lang/rate_compiler.py` validates the form against the allowlist, bakes the constants in, and returns a `(state) -> float` callable. The compiler sees a registry **view** (`registry.view(kinds={"rate", "math"})`), so a rate law can call `hill` or `exp` but not `diagnose`.

## 3. Registered function — `@fn`

The ordinary escape. A Python function decorated `@fn` becomes a head; a spec calls it by name with evaluated arguments. The function knows nothing about Expr.

```python
from alienbio.expr import fn

@fn(summary="Hill response", range=(0.0, 1.0))
def hill(s: float, k: float, n: float = 1.0) -> float:
    return s**n / (k**n + s**n)

@fn(kind="dist", summary="Log-uniform draw")
def loguniform(low: float, high: float, *, ctx) -> float:
    lo, hi = math.log(low), math.log(high)
    return float(math.exp(ctx.rng.uniform(lo, hi)))
```

```yaml
k_fast: !x loguniform(0.1, 10.0)
gate:   !x hill(signal, 0.5, n=3)
```

`kind` is the flavor tag (`dist`, `rate`, `scoring`, `action`, `measurement`, `math`, or none) that the existing decorator family expresses as separate decorators — `@rate`, `@scoring`, `@action`, `@measurement` remain as one-line aliases of `@fn(kind=…)` and write to the same registry. `summary` / `range` / the other metadata are the `FnMeta` fields the docs and plots already read (~~[[Decorators]]~~).

**Injection.** A function that declares a keyword-only parameter named `ctx` receives the evaluation context (seed-derived `rng`, node path, trust flag, limits); one that declares `env` receives the environment (bindings + heads) — the convention `spec_lang/eval.py` already implements as `_wrap_function`. Neither appears in the spec's call.

## 4. Registered expander — `@expander`

The escape for anything that *builds structure* by reasoning — a block that lays out a chain of length `n`, a drafter that plants a hidden catalyst on the rate-limiting step, an archetype that picks a pathway and writes the question. An expander receives its arguments **as forms**, plus the environment, and returns a form; the interpreter evaluates what it returns.

```python
from alienbio.expr import expander, X

@expander(summary="A conversion chain in → x1 → … → out")
def chain(args, kwargs, env):
    # positional pools
    src, dst = (env.evaluate(a) for a in args)
    n = env.evaluate(kwargs.get("length", 3))
    # left as a form: re-drawn per hop
    rate = kwargs.get("rate", X.parse("lognormal(0.1, 0.3)"))
    mids = [f"{env.ns}.x{i}" for i in range(1, n)]
    nodes = [src, *mids, dst]
    return {
        "molecules": {m: {} for m in mids},
        "reactions": {
            f"{env.ns}.hop{i}": {
                "reactants": [a], "products": [b], "rate": rate
            }
            for i, (a, b) in enumerate(zip(nodes, nodes[1:]), 1)
        },
    }
```

```yaml
supply_to_crux: !chain [supply, precursor]
long_route:     !chain {args: [precursor, prodB], length: 5,
                        rate: !x lognormal(0.05, 0.2)}
```

Three things the example shows. An expander **evaluates what it needs now** (`env.evaluate(form)`) and **passes through what should be re-evaluated later** — `rate` is returned as a form inside each hop, so each hop draws its own rate under its own child seed. It namespaces everything it mints under `env.ns` (the node's path), the skeleton-block rule that keeps two uses from aliasing. And it returns *data*, which the interpreter then evaluates — so an expander can return calls of other expanders and the composition nests.

Expanders that need a **rejection loop** (draw, check, redraw) do it in Python with `ctx.seed.child(f"attempt{k}")` — never with a special form. The drafters in `suite/experiment.py` are exactly this shape today (`draft_pressure_world` re-draws until the passive gate holds); registering them is a decorator, not a rewrite.

## 5. YAML template — `!template`

Not strictly an escape — it stays in the language — but it is where most Python calls are *made from*: a structural body with holes filled by escapes 1, 3 and 4.

```yaml
crux_world: !template
  params:
    n_routes: 2
    supply_rate: !x lognormal(1.0, 0.2)
  body:
    blocks:
      supply: !source {pool: precursor, rate: !x supply_rate}
      crux:   !conflict_crux {precursor: precursor,
                routes: !x [f"prod{c}" for c in "AB"[:n_routes]]}
      drains: !each {over: !x range(n_routes), as: i,
                      body: !sink {pool: !x f"prod{'AB'[i]}"}}
```

The body has exactly the constructs [[ABIO Expr]] § Special forms lists; when a template author wants more, the body calls an expander (escape 4) rather than the language growing.

## 6. Guard — `@guard`

A guard is a predicate over an *expanded* fragment, run after expansion with fail-and-decide semantics (retry under a new child seed / prune / reject — the `build/guards.py` model, kept). It is registered like a function but with `kind="guard"`, and named in a template's or a call's `guards:` list. A guard with parameters is written as a call.

```python
from alienbio.expr import guard, GuardViolation

@guard
def max_pathway_length(expanded, ctx, max_length=5):
    n = len(expanded["molecules"])
    if n > max_length:
        raise GuardViolation(f"pathway too long: {n} > {max_length}")
```

```yaml
route: !chain
  args: [precursor, prodA]
  length: !x poisson(4)
  guards: [no_new_cycles, !x max_pathway_length(max_length=6)]
  # retry | prune | reject; max_attempts from ctx.limits
  on_fail: retry
```

## 7. Constructor — an `Entity` subclass

Every `Entity` subclass is a head under its class name, automatically, as `@biotype` registers types today (~~[[Decorators]]~~ § Type Registration). The mapping under the tag is the constructor's keyword arguments, so a spec can write a concrete typed object directly where a form is expected — the terminal case of "structure as structure".

```yaml
extra: !Reaction {name: leak, reactants: [prodA], products: [],
                  rate: 0.01}
```

Constructors are functions (arguments arrive evaluated); `Entity.from_dict` remains the implementation. The `_type:` key convention the loader accepts today (`{"_type": "Chemistry", …}`) is the untagged spelling of the same call and is kept for round-tripping saved worlds.

## 8. Local Python reference — `!py`

A hydration-time pointer at a Python object in a module beside the spec. Resolved by `PyRef.resolve(base_dir, trusted=…)`, which imports the file and walks the attribute path; under the default untrusted load it raises `UnsafeSpecError`. Use it when a one-off experiment wants a bespoke function without registering it framework-wide.

```yaml
# catalog/experiments/exp11.yaml — beside exp11_helpers.py
scorer: !py exp11_helpers.surfacing_score
```

```python
# exp11_helpers.py
def surfacing_score(record) -> float: ...
```

The referenced object arrives as a *value* (a Python callable), so it can be passed to a head that accepts callables — `scorer:` above — but it is **not** a head: `!x surfacing_score(r)` would not resolve, because names in an inline form come from bindings, not from files. To make it callable from forms, bind it: `let: {surf: !py exp11_helpers.surfacing_score}`, then `!x surf(r)`.

## 9. Python include — `!include helpers.py`

The heaviest escape: execute a `.py` file for its side effects — its decorators register heads. Also trusted-only (`process.resolve_includes(..., trusted=True)`). This is how a catalog directory brings its own vocabulary of blocks and scorers: the `catalog/_index.yaml` source roots and the import-root allowlist in `spec_lang/resolve.py` decide which directories may be executed at all.

```yaml
# registers @fn / @expander / @guard heads
_includes_: [blocks.py, scorers.py]
world: !my_lab_world {strain: krel}
```

## The trust model, in one table

| Loading a spec as… | may call registered heads | may define `!template` | `!py` / `!include *.py` |
|---|---|---|---|
| **untrusted** (default; every agent-written or generated spec) | yes — any head, any arguments | yes | refused (`UnsafeSpecError`) |
| **trusted** (`trusted=True`; the framework's own catalog, local dev) | yes | yes | executed |

Two boundaries do all the work. The **AST allowlist** (`safe_eval.py`) keeps an inline form from being anything but an expression over names the environment supplies — no attribute walk to `__subclasses__`, no `getattr`, no `format`. The **registry** keeps the set of names finite and Python-authored: a spec can only call what a trusted module registered, and a registry *view* narrows that further for consumers that should see less (the rate compiler's math-only view). Trusted loading is the only way new names enter, and it is never the default. A registered function that wants to be *called* with untrusted arguments is responsible for validating them — the interpreter's entity-count cap (`MAX_ENTITY_COUNT`, from `build/expand.py`) and expansion-depth limit in `ctx.limits` bound the damage a malformed argument can do, but a head that opens files or shells out must never be registered at all.

## Testing an escape

Every escape is testable without YAML, through the Python spelling:

```python
from alienbio.expr import X, Env, evaluate

# the default registry + a child seed
env = Env.standard(seed=7)
value = evaluate(X.hill(0.5, 0.5, n=2), env)     # a function head
frag = evaluate(X.chain("a", "b", length=3), env)  # an expander head
assert set(frag["molecules"]) == {"root.x1", "root.x2"}
```

`X.parse("chain('a', 'b', length=3)")` gives the same form from text, so a test can pin the inline spelling too. Round-trip: `X.dump(form)` → YAML → `X.load(yaml)` → an equal form.

## What is not an escape

- **A new special form.** The set in [[ABIO Expr]] § Special forms is closed by decision D9. A construct that feels missing (`while`, `match`, string slicing in keys) is a signal to write an expander.
- **A per-archetype class.** The M27 archetype catalog is a set of expanders (`identify_pathway`, `diagnose`, …), each a function returning a `task` form — never a subclass with methods. That is the Group 4 collapse itself.
- **Reaching the registry from a spec.** No head lists, inspects or mutates the registry; a spec cannot ask "what functions exist". Introspection is a Python-side tool (`registry.describe()`) for docs and the CLI.

## History

- 2026-08-28 — drafted with [[ABIO Expr]] as part of the G4 design note.
