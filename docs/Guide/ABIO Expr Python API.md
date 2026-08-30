[[ABIO docs]] → [[Alienbio User Guide]] 

# ABIO Expr Python API

The Python side of [[ABIO Expr Spec|Expr]]: how a Python function becomes a head a spec can call, how an expander builds structure, how forms are built and evaluated from Python, how the drafters and the experiment file are reached from Python, and where the trust boundary sits.

> **Status.** Documents the API **as shipped** in `alienbio.expr` (roadmap M47, 2026-08-30). Every ```python fence on this page is executed, in order, by `tests/expr/test_spec_examples.py`.

## Registering a function — `@fn`

```python
from alienbio.expr import fn

@fn(summary="a gated response", range=(0.0, 1.0))
def gate(s: float, k: float, n: float = 1.0) -> float:
    return s**n / (k**n + s**n)
```

```yaml
opening: !x gate(0.8, 0.5, n=3)
```

- The function's name is the head name (`name=` overrides). Its parameters are the call's parameters; a spec passing an argument the function does not accept is an error at the call, naming the node.
- Arguments **arrive evaluated** — a function never sees a form, so any existing callable can be registered unchanged.
- `kind=` tags the flavor: `fn` (default), `dist`, `math`, `rate`, `scoring`, `action`, `measurement`, `guard`, `constructor`, `drafter`, `agent`, `experiment`. The old per-kind decorators (`@rate`, `@scoring`, …) are gone; there is one registry and one decorator.
- `summary`, `range` and any other keyword are stored as `head.meta` for docs and the CLI.
- `guarded=True` (the whole head) or `guarded_params={"hazard"}` marks what the no-peeking guard protects; the experiment loader reads that metadata off the calls a spec makes.

### Injection — `ctx` and `env`

```python
import math
from alienbio.expr import fn

@fn(kind="dist", summary="log-uniform draw")
def loguniform(low: float, high: float, *, ctx) -> float:
    lo, hi = math.log(low), math.log(high)
    return float(math.exp(ctx.rng.uniform(lo, hi)))
```

A keyword-only parameter named `ctx` receives the evaluation context; one named `env` receives the environment. Neither appears in the spec's call.

| `ctx` field | Meaning |
|---|---|
| `seed` | the node's `Seed` (`child(label)` derives a sub-stream) |
| `rng` | a numpy `Generator` from that seed |
| `path` | the node's path in the document, for messages |
| `trusted` | whether the load was trusted |
| `limits` | `entities`, `depth`, `attempts` caps |

`env` adds the scope (`env.lookup`, `env.bind`), the registry (`env.head(name)`), the namespace (`env.ns`), `env.pool(name)` (a pool name as the current template instance spells it) and `env.error(message)` (an `ExprError` carrying the node's path). The common case — a head that wants its arguments evaluated *and* the environment — is just `@fn` with a keyword-only `env`.

## Registering an expander — `@expander`

```python
from alienbio.expr import expander, evaluate, X

@expander(summary="a conversion chain in -> x1 -> ... -> out, as data")
def chain(args, kwargs, env):
    src, dst = (evaluate(a, env) for a in args)
    n = evaluate(kwargs.get("length", 3), env)
    rate = kwargs.get("rate", X.parse("lognormal(0.1, 0.3)"))
    mids = [f"{env.ns}.x{i}" for i in range(1, n)]
    nodes = [src, *mids, dst]
    return {
        "molecules": {m: {} for m in mids},
        "reactions": {
            f"{env.ns}.hop{i}": {"reactants": [a], "products": [b], "rate": rate}
            for i, (a, b) in enumerate(zip(nodes, nodes[1:]), 1)
        },
    }
```

```yaml
route: !chain {args: [A, B], length: 5, rate: !x "lognormal(0.05, 0.2)"}
```

- An expander receives `(args, kwargs, env)` — **the argument forms, unevaluated** — and returns a form (usually data with forms inside). The interpreter then evaluates what it returned, under the call's child seed, one sub-seed per key.
- `evaluate(form, env)` evaluates an argument now. Leave a form *in* the returned structure to have it evaluated later, per element — that is how `rate` above (an unevaluated `lognormal(...)` call) becomes one draw per hop; a `!q` rate would stay one `Dist` object shared by every hop.
- `env.ns` is the call's namespace (the node path); mint ids under it so two calls never alias.
- Logic lives here: a rejection loop, a graph search, a check. A YAML template cannot do those, by design.

## Registering a guard — `@guard`

```python
from alienbio.expr import guard, GuardViolation

@guard(summary="the produced pathway is short enough")
def max_pathway_length(value, ctx, max_length: int = 5):
    if len(value["molecules"]) + 2 > max_length:
        raise GuardViolation(f"pathway too long: max_length={max_length}")
    return True
```

```yaml
route: !chain {args: [A, B], length: 4, guards: [!x max_pathway_length(max_length=8)], on_fail: retry}
```

A guard receives the *evaluated* result of the call it is attached to, plus `ctx`, plus its own parameters from the spec. Return `True` to pass; return `False` or raise `GuardViolation(message, offenders=[...])` to fail — `offenders` names the keys (dotted for depth) that `on_fail: prune` may drop. `on_fail` on the call decides what a failure does ([[ABIO Expr Spec#Guards]]).

## Constructors

Every registered `Entity` head is a constructor head under its head name — `!Molecule`, `!Reaction`, `!Chemistry` call the class's `hydrate`; `!Compartment` and `!World` build the world records. Nothing to write; a mapping with `_type: X` is the untagged spelling.

## The registry

```python
from alienbio.expr import Env, registry

Env.standard()                                   # registers the suite heads
head = registry.get("hill")
assert head.kind == "rate"
assert registry.get("chain").is_expander
view = registry.view({"math", "rate"})           # a narrowed registry for rate laws
assert "hill" in view and "source" not in view
rows = registry.describe()                       # name, kind, signature, summary
assert any(r["name"] == "diagnose" and r["kind"] == "drafter" for r in rows)
```

One table, populated at import time by the decorators above and by `!include x.py` under a trusted load. A **view** is a registry restricted to some kinds (special forms always show); the rate compiler evaluates against the rate view so a rate law cannot call a world-building head. Specs cannot list, inspect or modify the registry.

## Building and evaluating forms from Python — `X`, `Env`, `evaluate`

```python
from alienbio.expr import X, Env, evaluate, ExprError

env = Env.standard(seed=7)                       # default registry, root seed 7

form = X.chain("A", "B", length=3)               # a Call form
frag = evaluate({"route": form}, env)["route"]
assert set(frag["molecules"]) == {"route.x1", "route.x2"}

same = X.parse('chain("A", "B", length=3)')      # inline text → the same form
assert same == form

text = X.dump(form, style="structural")
assert text.strip() == "!chain {args: [A, B], length: 3}"
back = X.load(text)                              # YAML → form
assert back == form

scope = Env.standard(seed=11, trusted=True).load(
    "spec.yaml",
    text="n: 3\nmols: !x '[f\"M{i}\" for i in range(n)]'\nk: !x lognormal(0, 1)\n",
)
assert evaluate(X.name("mols"), scope) == ["M0", "M1", "M2"]  # a file is a scope
values = scope.force_all()                       # every top-level binding, evaluated
assert values["mols"] == ["M0", "M1", "M2"]

try:
    evaluate(X.chian("A", "B"), env)
except ExprError as exc:
    assert isinstance(exc, ValueError) and "unknown head 'chian'" in str(exc)
```

| API | Meaning |
|---|---|
| `X.<head>(*args, **kwargs)` | a `Call` form |
| `X.name("a.b")` | a `Name` form |
| `X.quote(form)` | a `Quoted` form |
| `X.parse(text)` | inline text → form (sandbox-checked) |
| `X.dump(form, style="inline" \| "structural")` | form → text / YAML |
| `X.load(yaml_text)` | YAML → form |
| `Env.standard(seed, trusted=False, registry=None, limits=None, bindings=None)` | an environment over the default registry |
| `env.load(path, text=None, base=None)` | load a file into a child scope (includes resolved relative to `base`, the file's directory by default); `env.force_all()` evaluates every binding |
| `env.bind(**values)` / `env.child(label)` / `env.scope(data)` | extend the scope / derive a child seed / open a child scope |
| `env.hydrate(data, base=)` | resolve `!include` / `!py` inside already-loaded forms |
| `evaluate(form, env)` | the interpreter |
| `ExprError(message, path)` | every failure, with the node path — a `ValueError` |

Forms are frozen dataclasses (`Name`, `Call`, `Quoted`, plus the load-time `Include` / `PyRef`; literals are plain Python scalars; data is `list` / `dict`) and compare by value, so a test can assert on them directly.

## Dists from quoted forms

```python
from alienbio.suite.dist import Dist

rate = evaluate(X.quote(X.lognormal(0.1, 0.3)), env)
assert isinstance(rate, Dist)
one = rate.sample(env.ctx.seed.child("hop1"))    # one draw
again = rate.sample(env.ctx.seed.child("hop1"))
assert one == again                              # same seed, same draw
scaled = evaluate(X.quote(X.parse("k * 2")), env).run({"k": 4})
assert scaled == 8
```

A `Quoted` form evaluates to a `QuotedForm` object that *is* a `Dist` (`sample(seed)`) and also exposes `run(bindings=None, *, seed=None)`. Heads that take a `Dist` accept it directly; a bare number where a `Dist` is expected is promoted to `constant`.

## Drafters, worlds and experiments from Python

```python
from alienbio.suite.experiment import DRAFTERS, dial_params, load_spec, spec_from_dict
from alienbio.suite.expr_experiment import load_experiment, spec_to_text
from alienbio.suite.dist import Seed

draft = evaluate(X.identify_pathway(pathway_length=3), Env.standard(seed=3))
world, task = draft                                   # a Draft is (world, task)
assert draft.world is world and task.objective is not None

same_world, _ = DRAFTERS["identify_pathway"](Seed(3), {"pathway_length": 3})   # the runner's shape
assert sorted(same_world.chemistry.reactions) == sorted(world.chemistry.reactions)

assert set(dial_params(registry.get("diagnose"))) >= {"n_nodes", "hazard", "perturbation"}

spec = load_experiment("<doc>", text="""
!experiment
name: doc-small
task: !q identify_pathway(pathway_length=pathway_length)
episode: !q episode(max_turns=4, sim_steps=5)
agent: measure_commit
axes: {pathway_length: [3, 4]}
trials_per_condition: 1
base_seed: 1
""")
assert spec.drafter == "identify_pathway" and spec.axes == (("pathway_length", (3, 4)),)
assert spec.fixed_dials == {"max_turns": 4, "sim_steps": 5}
assert load_experiment("<again>", text=spec_to_text(spec)) == spec   # the inverse
```

A drafter head evaluates to a `Draft` — the world and the task instance — under the node's seed; `DRAFTERS[name]` is the same head in the runner's `(seed, dials) -> (world, task)` shape, passing only the dials the head declares. `load_spec(path)` / `load_experiment(path, text=)` read an experiment file into an `ExperimentSpec` (`run_experiment(spec)` runs it; `bio suite run` is the CLI); `spec_to_text` renders one back.

## Trust

| Load | Registered heads | `!template` | `!include *.yaml / *.md` | `!py`, `!include *.py` |
|---|---|---|---|---|
| untrusted (default) | any head, any arguments | yes | relative, inside the file's directory | `UnsafeSpecError` |
| trusted (`trusted=True`) | any | yes | any path | executed |

Two boundaries: the **AST allowlist** on `!x` / `!q` text (no dunders, no `getattr`, no unpacking, no lambda, names only from scope) and the **registry** (a spec can only name what trusted Python registered). A registered head is responsible for validating untrusted arguments; the interpreter's limits bound size and depth. A head that opens files or runs subprocesses must not be registered. `UnsafeSpecError` lives in `alienbio.expr`.

## Testing a head

```python
def test_chain_draws_per_hop():
    env = Env.standard(seed=1)
    form = X.chain("A", "B", length=3, rate=X.lognormal(0, 1))
    frag = evaluate({"route": form}, env)["route"]
    rates = [r["rate"] for r in frag["reactions"].values()]
    assert len(set(rates)) == 3          # three independent draws
    again = evaluate({"route": form}, Env.standard(seed=1))["route"]
    assert again == frag                 # same seed, same world

test_chain_draws_per_hop()
```
