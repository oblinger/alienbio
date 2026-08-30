[[ABIO docs]] → [[Alienbio User Guide]] 

# ABIO Expr Python API

The Python side of [[ABIO Expr Spec|Expr]]: how a Python function becomes a head a spec can call, how an expander builds structure, how forms are built and evaluated from Python, and where the trust boundary sits.

> **Status.** Documents the API as designed in [[ABIO Expr]] (F007 G4); the `alienbio.expr` package lands with G4. The registration decorators on `main` today are the older per-kind set in [[Decorators]].

## Registering a function — `@fn`

```python
from alienbio.expr import fn

@fn(summary="Hill response", range=(0.0, 1.0))
def hill(s: float, k: float, n: float = 1.0) -> float:
    return s**n / (k**n + s**n)
```

```yaml
gate: !x hill(signal, 0.5, n=3)
rate: !q hill(S, Km) * Vmax
```

- The function's name is the head name (`name=` overrides). Its parameters are the call's parameters; a spec passing an argument the function does not accept is an error at the call.
- Arguments **arrive evaluated** — a function never sees a form, so any existing callable can be registered unchanged.
- `kind=` tags the flavor: `dist`, `rate`, `scoring`, `action`, `measurement`, `math`, or none. The older decorators `@rate`, `@scoring`, `@action`, `@measurement` are `@fn(kind=...)` and write to the same registry.
- `summary`, `range` and any other keyword are stored as `head.meta` for docs, plots and the CLI.

### Injection — `ctx` and `env`

```python
@fn(kind="dist")
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

## Registering an expander — `@expander`

```python
from alienbio.expr import expander, X

@expander(summary="A conversion chain in -> x1 -> ... -> out")
def chain(args, kwargs, env):
    src, dst = (env.evaluate(a) for a in args)
    n = env.evaluate(kwargs.get("length", 3))
    rate = kwargs.get("rate", X.parse("lognormal(0.1, 0.3)"))
    mids = [f"{env.ns}.x{i}" for i in range(1, n)]
    nodes = [src, *mids, dst]
    return {
        "molecules": {m: {} for m in mids},
        "reactions": {
            f"{env.ns}.hop{i}": {"reactants": [a], "products": [b],
                                 "rate": rate}
            for i, (a, b) in enumerate(zip(nodes, nodes[1:]), 1)
        },
    }
```

```yaml
route: !chain {args: [A, B], length: 5, rate: !q lognormal(0.05, 0.2)}
```

- An expander receives `(args, kwargs, env)` — **the argument forms, unevaluated** — and returns a form (usually data with forms inside). The interpreter then evaluates what it returned, under the call's child seed, one sub-seed per key.
- `env.evaluate(form)` evaluates an argument now. Leave a form *in* the returned structure to have it evaluated later, per element — that is how `rate` above becomes one draw per hop.
- `env.ns` is the call's namespace (the node path); mint ids under it so two calls never alias.
- Logic lives here: a rejection loop (`for k in range(ctx.limits.attempts): ... ctx.seed.child(f"attempt{k}")`), a graph search, a check. A YAML template cannot do those, by design.
- Declare `guarded=True` (the whole head) or `guarded_params={"hazard"}` (named parameters) to mark dials the no-peeking guard protects; the experiment loader reads that metadata off the calls a spec makes.

### Signature-declared expanders

```python
@expander.typed
def sink_pair(pool: str, *, rate: float = 1.0, fast: bool = False, env):
    ...
```

The common case — an expander that just wants its arguments evaluated but needs `env` (for `ns`, seeds, or to return forms) — declares a normal signature; the interpreter evaluates the arguments against it and injects `env`.

## Registering a guard — `@guard`

```python
from alienbio.expr import guard, GuardViolation

@guard
def max_pathway_length(expanded, ctx, max_length: int = 5):
    if len(expanded["molecules"]) + 2 > max_length:
        raise GuardViolation(f"pathway too long: max_length={max_length}")
```

A guard receives the *evaluated* result of the call it is attached to, plus `ctx`, plus its own parameters from the spec (`!x max_pathway_length(max_length=6)`). Return normally to pass; raise `GuardViolation` to fail. `on_fail` on the call decides what a failure does.

## Constructors

Every `Entity` subclass is registered automatically under its class name; `!Reaction {...}` calls `Reaction.from_dict`. Nothing to write.

## The registry

```python
from alienbio.expr import registry

registry.get("hill")                       # → Head(kind="fn", ...)
registry.get("chain").expander             # → True
registry.view(kinds={"math", "rate"})      # a narrowed registry for rate laws
registry.describe()                        # name, kind, signature, summary
```

One table, populated at import time by the decorators above and by `!include x.py` under a trusted load. A **view** is a registry restricted to some kinds; the rate compiler evaluates against a math-only view so a rate law cannot call a world-building head. Specs cannot list, inspect or modify the registry.

## Building and evaluating forms from Python — `X`, `Env`, `evaluate`

```python
from alienbio.expr import X, Env, evaluate

env = Env.standard(seed=7)                       # default registry, root seed 7

form = X.chain("A", "B", length=3)               # a Call form
frag = evaluate(form, env)
assert set(frag["molecules"]) == {"root.x1", "root.x2"}

same = X.parse('chain("A", "B", length=3)')      # inline text → the same form
assert same == form

text = X.dump(form, style="structural")
# → '!chain {args: [A, B], length: 3}\n'
back = X.load(text)                              # YAML → form
assert back == form

env2 = Env.standard(seed=11, trusted=True).load("ecosystem.yaml")
world = evaluate(X.name("world"), env2)     # a file is a scope
vash = evaluate(X.organism("vash", chains=1), env2)  # a YAML template
```

| API | Meaning |
|---|---|
| `X.<head>(*args, **kwargs)` | a `Call` form |
| `X.name("a.b")` | a `Name` form |
| `X.quote(form)` | a `Quoted` form |
| `X.parse(text)` | inline text → form (sandbox-checked) |
| `X.dump(form, style="inline" \| "structural")` | form → text / YAML |
| `X.load(yaml_text)` | YAML → form |
| `Env.standard(seed, trusted=False)` | an environment over the default registry |
| `env.load(path)` | evaluate a file into the environment's scope (bindings + templates) |
| `env.bind(**values)` / `env.child(label)` | extend the scope / derive a child seed |
| `evaluate(form, env)` | the interpreter |
| `ExprError(path, message)` | every failure, with the node path |

Forms are frozen dataclasses (`Lit` values are plain Python scalars; `Name`, `Call`, `Quoted`; data is `list` / `dict`) and compare by value, so a test can assert on them directly.

## Dists from quoted forms

```python
from alienbio.suite.dist import Dist

rate = evaluate(X.quote(X.lognormal(0.1, 0.3)), env)
assert isinstance(rate, Dist)
rate.sample(env.ctx.seed.child("hop1"))          # one draw
rate.run(env, {"extra": 1})                      # evaluate with bindings
```

A `Quoted` form evaluates to a `QuotedForm` object that *is* a `Dist` (`sample(seed)`) and also exposes `run(env, bindings)`. Heads that take a `Dist` accept it directly; a bare number where a `Dist` is expected is promoted to `constant`.

## Trust

| Load | Registered heads | `!template` | `!py`, `!include *.py` |
|---|---|---|---|
| untrusted (default) | any head, any arguments | yes | `UnsafeSpecError` |
| trusted (`trusted=True`) | any | yes | executed |

Two boundaries: the **AST allowlist** on `!x` / `!q` text (no dunders, no `getattr`, no unpacking, no lambda, names only from scope) and the **registry** (a spec can only name what trusted Python registered). A registered head is responsible for validating untrusted arguments; the interpreter's limits bound size and depth. A head that opens files or runs subprocesses must not be registered.

## Testing a head

```python
def test_chain_draws_per_hop():
    env = Env.standard(seed=1)
    form = X.chain("A", "B", length=3, rate=X.quote(X.lognormal(0, 1)))
    frag = evaluate(form, env)
    rates = [r["rate"] for r in frag["reactions"].values()]
    assert len(set(rates)) == 3          # three independent draws
    again = evaluate(form, env)
    assert again == frag                 # same seed, same world
```
