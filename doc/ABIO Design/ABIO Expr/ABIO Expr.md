---
description: "the generative expression language — G4 design note"
---

| -[ABIO Expr](ABIO%20Expr.md)-                                                               | : the generative expression language — G4 design note<br>→ [ABIO](../../ABIO.md) → [ABIO Design](../ABIO%20Design.md) → [ABIO Expr](ha://p/ABIO%20Expr)                                                                                                                   |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Related                                                                                     | [ABIO Unified Protocol Model](../ABIO%20Unified%20Protocol%20Model.md),  [Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md),  [Python API](../../ABIO%20Guides/ABIO%20Expr%20Python%20API.md),  [ABIO Skeleton Arch](../ABIO%20Skeleton%20Arch/ABIO%20Skeleton%20Arch.md), |
| [[ABIO Expr Templates\| every head, layer 0–6, with a worked example each                   |                                                                                                                                                                                                                                                                           |
| [[ABIO Expr Python Escapes\| where `!py` and `!x` reach into Python, and the trust boundary |                                                                                                                                                                                                                                                                           |
| ...                                                                                         | [ABIO Expr Python Escapes](ABIO%20Expr%20Python%20Escapes.md),  [ABIO Expr Templates](ABIO%20Expr%20Templates.md),                                                                                                                                                        |

# ABIO Expr
The generative expression language of the Alien Biology Framework — the G4 design note: one call-shaped form over YAML data, evaluated against Python-registered functions and expanders.

| Table of Contents |  |
|---|---|
| **[[#The design stance]]** |  |
| **[[#Where Expr sits]]** |  |
| **[[#Grammar]]** |  |
|    [[#Inline spelling — `!x`]] |  |
|    [[#Structural spelling — `!head`]] |  |
|    [[#Python spelling — `X.head(…)`]] |  |
| **[[#Evaluation model]]** |  |
|    [[#The environment]] |  |
|    [[#Special forms]] |  |
| **[[#Registration — how Python enters the environment]]** |  |
|    [[#Templates in YAML]] |  |
| **[[#A complete example]]** |  |
|    [[#Legend — where each construct appears]] |  |
| **[[#The Group 4 collapse, in this language]]** |  |
| **[[#Decisions]]** |  |
| **[[#Open questions]]** |  |
| **[[#History]]** |  |

**Expr** is the generative expression language of the Alien Biology Framework — the one declarative form in which everything that *describes how to build* a world, a task, an objective or a suite is written. [[ABIO Unified Protocol Model]] § Group 4 locked the decision that those descriptions are **not classes**: they are spec-expressions an `Interpreter` evaluates into their concrete counterparts. This folder is the design note that decision asked for ([F007](../../ABIO%20Track/ABIO%20Features/ABIO007%20-%20Retire%20shadow%20types%20-%20protocol-ize%20suite%20over%20biology%20classes.md) G4): it fixes the language before any code, because the language is the surface every generator, template and experiment is authored against.

| Page | What it holds |
|---|---|
| **[[ABIO Expr]]** (this page) | The language: the grammar, the evaluation model, the environment, how functions and expanders are registered, and the decisions taken. |
| ~~[[ABIO Expr Templates]]~~ | The template catalog — every generative form that will exist, with a worked example of each, showing what a generator looks like written in Expr. |
| ~~[[ABIO Expr Python Escapes]]~~ | The Python side — registering functions and expanders, `!py` references, inline formulas, deferred rate laws, guards — with an example of each escape. |

## The design stance

The language is built on one rule about **where each kind of thing is written**, stated by the owner on 2026-08-28 and adopted here as the governing principle:

- **Logic is written in Python.** Anything that branches, searches, iterates over a graph, verifies, samples with rejection, or reads a simulation belongs in a Python function. Expr never grows control flow beyond what a template needs to lay out structure.
- **Structure is written as template structure.** The shape of a world — its molecules, reactions, compartments, pools, wiring — is plain YAML data with parameter holes. It reads like the thing it produces.
- **Simple formulas may be written either way.** A rate law, a polynomial, an additive score, a distribution draw: these are pleasant to write inline (`!x Vmax * S / (Km + S)`) and equally legal as a registered Python function. Expr carries the *parameter structure* of a thing; it is not where reasoning lives.

From this follows the shape of the language: **Expr is a language of calls.** Every generative form looks like a Python function call — a head, fixed positional arguments, keyword arguments — but is data, not code. The heads are Python callables registered into the interpreter's environment, so a template author reaches for full Python by registering a function, never by extending the language. The environment is Python's: bindings are a scope chain, heads are a registry, sampling is a seeded `numpy` generator — sandboxed only at the boundary an untrusted spec can touch.

## Where Expr sits

Expr is not a second language beside the spec DSL — it is the spec DSL's expression layer, promoted to carry generation. The existing pipeline (~~[[Spec Language Reference]]~~ § Execution Pipeline) stays:

`fetch` (specifier → YAML) → `hydrate` (`!include`, `!py`; trust-gated) → **`evaluate` (Expr)** → typed objects

Three generative surfaces exist in the code today and Expr replaces all three with one:

| Surface today | Where | Becomes |
|---|---|---|
| `!ev` inline expressions + the builtin distribution functions | `spec_lang/eval.py`, `builtins.py` | the **inline form** of Expr — same syntax, same AST sandbox, heads now resolved through the one registry |
| the M1 generator DSL — `template.name:`, `_params_`, `_ports_`, `_instantiate_`, `_as_ x{i in 1..n}`, `_guards_` | `build/` (~~[[Generator Spec]]~~) | **YAML-defined templates** (`!template`) + the `each` special form; the underscore directives retire |
| the five suite template dataclasses `Motif` / `WorldEnvelope` / `ObjectiveRecipe` / `TaskArchetype` / `SuiteSpec`, the `DRAFTERS` registry keyed by name in `suite/experiment.py`, and `experiment.load_spec` — a second YAML loader (plain `safe_load` + a key allowlist) that shares nothing with the spec DSL's | `suite/` | **registered expanders** — a drafter *is already* a registered Python callable invoked by name with keyword dials; Expr makes that the language instead of a private registry |

The last row is the observation that makes G4 cheap (ten drafters are registered today, not the eight F007 counted): an experiment file such as `catalog/experiments/exp04.yaml` already says `drafter: diagnose` and `fixed_dials: {max_turns: 6}` — that is the call `diagnose(max_turns=6)` spelled as two YAML keys. Expr is that call, written as a call.

## Grammar

Expr has one abstract syntax and three concrete spellings (inline text, structural YAML, Python constructors) that denote the same tree. The abstract grammar:

```
form      ::= literal | name | data | call | quoted
literal   ::= number | string | bool | null
name      ::= ident ( "." ident )*     ; env lookup; dotted = path
data      ::= "[" form* "]"            ; a list of forms
            | "{" ( key ":" form )* "}" ; a mapping of forms
call      ::= head "(" arg* kwarg* ")" ; positional, then keyword
; registered fn / expander / special
head      ::= ident
arg       ::= form
kwarg     ::= ident "=" form
quoted    ::= "quote" "(" form ")"     ; a form held as a value
```

Five things, and only five: literals, names, data, calls, quoted forms. There are no operators, no lambdas, no loops and no conditionals in the abstract syntax — the inline spelling borrows Python's infix operators as sugar, and iteration and binding are *special forms* (calls with reserved heads), so the tree stays uniform and every node is either data or a call something in Python can answer for.

### Inline spelling — `!x`

A YAML string tagged `!x` holds a form in Python expression syntax. It is exactly today's `!ev` (renamed; see § Decisions D6), parsed by the AST allowlist in `spec_lang/safe_eval.py` and evaluated against the environment:

```yaml
Vmax: !x lognormal(1.0, 0.3)
rate: !x Vmax * S / (Km + S)
label: !x f"Chain molecule {i}"
world: !x pressure(pi=0.5, complexity=3, seed=seed.child("world"))
```

The inline spelling admits, beyond the abstract grammar: arithmetic and comparison operators, boolean `and`/`or`/`not`, the conditional expression `a if c else b`, f-strings, list/dict displays, subscripts, and method calls on values (`state.get("A", 0)`). All of these are evaluated by the sandbox as they are today; conceptually each is a call on a builtin head. What the sandbox forbids stays forbidden: dunder attributes, interpreter internals, `*`/`**` unpacking, calls on anything but a name or a method, the denied builtins (`getattr`, `eval`, `open`, `__import__`, …). Names resolve only in the environment; there are no Python globals.

### Structural spelling — `!head`

A YAML node tagged with a head name is a call of that head. A **mapping** supplies keyword arguments, a **sequence** supplies positional arguments, a **scalar** supplies one positional argument:

```yaml
world: !pressure
  pi: 0.5
  complexity: 3
  seed: !x seed.child("world")

pools: !bind [precursor, energy.reactions.work]

length: !normal [3, 1]
tag: !upper krel
```

A **mapping** call that also needs positional arguments gives them under the reserved key `args:` — `!chain {args: [precursor, prodA], length: 5}` is `chain(precursor, prodA, length=5)`.

The structural spelling is how a large template body is written — a drafter with six dials, a block with a nested list of blocks — where an inline string would be unreadable. Any structural call can be written inline and vice versa; `X.dump(form)` round-trips both. The reserved tags (`!x`, `!q`, `!ref`, `!include`, `!py`) cannot be head names.

Plain YAML that carries no tag is **data**, evaluated element-wise: a mapping of forms evaluates to a mapping of values. So a template body is mostly untagged YAML — the structure — with tagged holes where a value is computed.

### Python spelling — `X.head(…)`

The same trees are built in Python through a pegboard in the style of `mk` ([[ABIO Factory Pegboard API]]):

```python
from alienbio.expr import X

form = X.pressure(pi=0.5, complexity=3,
                  seed=X.name("seed").child("world"))
# inline text → form
form = X.parse('pressure(pi=0.5, complexity=3)')
X.dump(form, style="structural")                     # form → YAML
```

`X.<head>(…)` builds a `Call`; `X.name("a.b")` a `Name`; `X.quote(form)` a `Quoted`; literals and Python lists/dicts are data. Tests and Python-side generators author forms this way and never touch YAML.

## Evaluation model

`evaluate(form, env) -> value`, structurally recursive:

| Form | Evaluates to |
|---|---|
| literal | itself |
| name | `env.lookup(path)` — the first segment in the scope chain, the rest as key/attribute steps. An unbound name is an error; there is no default. |
| data (list / mapping) | the list / mapping of its evaluated elements, keys kept |
| `quote(f)` | the form `f` itself, as a `Form` value (not evaluated) |
| call, head is a **function** | evaluate every argument (left to right, positional then keyword), then call the Python function with the values — *applicative order* |
| call, head is an **expander** | hand the *unevaluated* argument forms and the environment to the Python expander; it returns a new form (optionally with a child environment); evaluate that — *normal order, one step* |
| call, head is a **special form** | as an expander, but built into the interpreter (below) |

Two consequences worth stating plainly. First, **a function never sees a form** — it sees values, so any existing Python function can be registered without knowing Expr exists. Second, **an expander never evaluates anything itself** — it rewrites, and the interpreter evaluates the rewrite. A template that loops is an expander that returns the unrolled data; a drafter that needs a seed asks the environment for it. This keeps expanders composable: the result of one expansion can be the argument of another.

### The environment

`Env` is a Python object with three parts:

- **Bindings** — a scope chain (the existing `spec_lang.scope.Scope`: lookup climbs parents). A YAML file is a scope; `let` opens a child; a template body sees its parameters as bindings; a YAML-defined template closes over the scope it was defined in.
- **Heads** — the registry (§ Registration), plus any heads bound locally (a `!template` defined in this file). Head lookup is by name; a locally defined head shadows a registered one only inside its scope.
- **Context** (`ctx`) — the run's seed, the path of the node being evaluated (for error messages), the trust flag, and the limits. `ctx.seed` is a `suite.dist.Seed`; every named expansion evaluates its body under `ctx.seed.child(name)`, so adding a sibling never re-rolls another sibling's draws — the same stable-under-edit rule the skeleton blocks already follow.

Functions receive `ctx` or `env` by declaring a keyword-only parameter of that name — the injection convention `spec_lang/eval.py` already implements for `normal(mean, std, *, ctx)`. Expanders always receive `(args, kwargs, env)`.

### Special forms

The fixed heads the interpreter implements itself. They are the whole control surface of the language; if a template needs more than these, the missing piece is a Python expander, not a new special form.

| Special form | Meaning |
|---|---|
| `let(bindings, body)` | evaluate `body` in a child scope holding `bindings` (a mapping of forms, evaluated in order, later entries may use earlier ones) |
| `each(over, as, body)` | evaluate `body` once per element of `over` with `as` bound; returns the list. With `key=` returns a mapping keyed by the evaluated `key` form — the loop-in-key construct `MS{i in 1..n}` of the M1 DSL is `each` with `key: !x f"MS{i}"` |
| `if(cond, then, else)` | evaluate `then` or `else` only |
| `quote(f)` / `!q` | hold `f` as a form value. The deferred rate law `rate: !q k * S / (Km + S)` is a quoted form the simulator later evaluates with the state bound. A quoted distribution draw (`!q lognormal(0.1, 0.3)`) is how a `Dist` is passed unsampled: Python receives it as a `suite.dist.Dist` whose `sample(seed)` evaluates the form under that seed |
| `run(f, bindings)` | evaluate a quoted form now, in a child scope — the other half of `quote` |
| `template(params, body)` | make an expander from a YAML body (§ Templates in YAML) |
| `seed(label)` | `ctx.seed.child(label)` — explicit re-keying when a template needs several independent streams |
| `py(path)` / `!py` | a hydration-time reference to a Python object (`module.attr`), trusted specs only — the escape hatch, documented in ~~[[ABIO Expr Python Escapes]]~~ |

`!ref name` is retained as the structural spelling of a bare **name** (a YAML scalar cannot otherwise say "look this up"); it no longer copies structure at hydration — it is a lookup at evaluation like any name (§ Decisions D7). `!include` stays a hydration-time file merge, outside the language.

## Registration — how Python enters the environment

The registry is one table, `alienbio.expr.registry`, mapping a head name to a `Head(kind, callable, meta)`. It is populated at import time by decorators, exactly as the `@fn` family in `spec_lang/decorators.py` populates its per-kind registries today — those registries fold into this one, distinguished by `kind` (the *flavored factories by convention* pattern of [[ABIO Unified Protocol Model]]).

```python
from alienbio.expr import fn, expander

# a function head; args arrive evaluated
@fn
def hill(s: float, k: float, n: float = 1.0) -> float:
    return s**n / (k**n + s**n)

@fn(kind="dist", summary="Log-normal draw")
def lognormal(mean: float, sigma: float, *, ctx) -> float:
    return float(ctx.rng.lognormal(mean, sigma))

# an expander head; args arrive as forms
@expander
def energy_cycle(args, kwargs, env):
    n = env.evaluate(kwargs.get("carrier_count", 3))
    mols = {f"ME{i}": {"role": "energy"} for i in range(1, n + 1)}
    return {"molecules": mols, "reactions": {...}}
```

Three head kinds and where they come from:

| Kind | Registered by | Receives | Examples |
|---|---|---|---|
| **function** | `@fn` (and its flavors `@rate`, `@scoring`, `@action`, `@measurement`, `@guard`, `@dist`) | values | `hill`, `lognormal`, `mass_action`, `population_health` |
| **constructor** | every `Entity` subclass, by class name — automatic, as `@biotype` is today | values, as keyword fields | `Molecule(name=…)`, `Reaction(reactants=…)`, `World(…)` |
| **expander** | `@expander` in Python; `!template` in YAML | forms + env | the blocks (`source`, `sink`, `conflict_crux`, …), the drafters (`pressure`, `diagnose`, …), the M27 archetypes |

A registered name is the *only* way a spec reaches Python. That is the sandbox: an untrusted spec can call any registered head with any arguments, and nothing else — no imports, no attribute walks, no globals. Registration itself is a trusted act: it happens in framework modules, in a catalog's `functions.py` loaded through a source root on the import allowlist (`spec_lang/resolve.py`), or through `!py` under `trusted=True`. The registry exposes **views** — `registry.view(kinds={"rate"})` — so a narrower evaluator (the rate compiler, which today bakes a seven-entry math table) sees only the heads it should.

### Templates in YAML

A template written as structure is a `!template` form bound to a name; evaluating it yields an expander, and the binding installs that expander as a head in the file's scope:

```yaml
energy_cycle: !template
  params:
    carrier_count: 3
    base_rate: !x lognormal(0.1, 0.3)
  body:
    molecules: !each
      over: !x range(1, carrier_count + 1)
      as: i
      key: !x f"ME{i}"
      body: {role: energy, description: !x f"Carrier state {i}"}
    reactions:
      activation: {reactants: [ME1, ME1], products: [ME2],
                   rate: !x base_rate}
      work:       {reactants: [ME2], products: [ME3]}
      regeneration: {reactants: [ME3], products: [ME1]}

krel_energy: !energy_cycle {carrier_count: 5}
```

`params` are the template's keyword parameters with defaults (themselves forms, evaluated per instantiation under the instantiation's child seed); `body` is evaluated in a scope where the parameters are bound. Positional parameter *names* are declared with `positional: [precursor, product]` — distinct from `args:`, which in a *call* supplies positional *values*. A YAML template and a Python expander are interchangeable to a caller — the catalog in ~~[[ABIO Expr Templates]]~~ shows the same block written both ways.

## A complete example

One document that uses every construct in the language, so the pieces can be seen together. It builds a two-organism ecosystem — each organism an energy cycle feeding some conversion chains, the two coupled through a shared waste pool that one organism's enzyme consumes — then a task on it and a small experiment. Each construct is named in the comment line above the code that shows it; the legend after the listing indexes them.

```yaml
# ecosystem.yaml

# ESCAPE 9: execute helpers.py under a trusted load; it registers
# the heads chain / hill / max_pathway_length used below.
_includes_: [helpers.py]

# ---- bindings ---------------------------------------------------
# Untagged YAML is DATA; every tagged node is a FORM. A file is a
# scope, so each key here is a NAME the rest of the document can use.

site_K: 0.5                         # literal
n_species: 2                        # literal

# INLINE call: executed once, right here, under this node's seed;
# base_rate is bound to the RESULT (a number).
base_rate: !x lognormal(1.0, 0.3)

# QUOTED call: NOT executed. hop_rate is bound to the FORM itself --
# in effect a lambda over this file's scope. Whoever receives it
# evaluates it: as a Dist, once per use, under the user's own seed.
hop_rate: !q lognormal(0.1, 0.3)

# INLINE with an f-string, a comparison and a conditional.
label: !x f"eco-{n_species}sp-{'fast' if base_rate > 1 else 'slow'}"

# SPECIAL FORM run: evaluate a quoted form now, here. first_hop is
# bound to one draw. (Special form = a head the interpreter itself
# implements, because it must control HOW its arguments evaluate.)
first_hop: !x run(hop_rate)

# INLINE: sandboxed Python expression, executed here; tags is bound
# to the resulting list.
tags: !x ["waste", "energy"] + (["fast"] if base_rate > 1 else [])

# ---- a template written as structure ----------------------------
# SPECIAL FORM template: makes a FUNCTION (an expander head) and
# binds it to the name. Nothing is generated here; each later call
# `!energy_cycle ...` evaluates the body afresh, under that call's
# own child seed, with the parameters bound to that call's arguments.
energy_cycle: !template
  # the NAME of one positional parameter: a pool name (or null)
  positional: [waste]
  # KEYWORD parameter names with defaults; defaults are forms,
  # evaluated per call
  params:
    carrier_count: 3
    rate: !x base_rate                # a NAME from the enclosing scope
  body:
    # SPECIAL FORM each: a loop with a computed key
    molecules: !each
      over: !x range(1, carrier_count + 1)
      as: i
      key: !x f"ME{i}"
      body: {role: energy, weight: !x 100 + 10 * i}
    reactions:
      activation:
        reactants: [ME1, ME1]
        products: [ME2]
        rate: !x rate
      work:
        reactants: [ME2]
        # SPECIAL FORM if, structural spelling, keyword arguments
        products: !if
          cond: !x waste
          then: !x ["ME3", waste]
          else: [ME3]
      regeneration:
        reactants: [ME3]
        products: [ME1]
        # QUOTED rate law: ME3 is bound by the simulator later;
        # hill is a Python @fn (helpers.py); site_K a file binding.
        rate: !q hill(ME3, site_K, n=2) * rate

organism: !template
  positional: [name]
  params: {chains: 2, waste: null}
  # SPECIAL FORM let: bindings visible in the body
  body: !let
    bindings:
      route_len: !x max(2, poisson(3))    # builtin + dist in one expr
      k: !x seed("kinetics")              # SPECIAL FORM seed
    body:
      # STRUCTURAL call, SEQUENCE = positional args
      energy: !energy_cycle [!x waste]
      routes: !each
        over: !x range(chains)
        as: i
        key: !x f"chain{i}"
        # PYTHON EXPANDER (helpers.py): receives forms, returns a form.
        # Positional args under the reserved key, mixed with keywords.
        body: !chain
          args: [energy.ME2, !x f"{name}.S{i}"]
          length: !x route_len
          # the Dist passes through unsampled; chain draws per hop
          rate: !x hop_rate
          # GUARDS: a bare name, and a call with a keyword argument
          guards: [no_new_cycles, !x max_pathway_length(max_length=6)]
          on_fail: retry
      # CONSTRUCTOR: an Entity subclass as a head
      leak: !Reaction
        name: leak
        reactants: [energy.ME2]
        products: []
        rate: 0.01

# ---- the world ---------------------------------------------------
world: !world
  seed: !x seed("world")
  # a dotted POOL NAME as data (a string), not a lookup
  initial: {shared.waste: 0.0}
  skeleton: !skeleton
    crux: feed
    control_surface: [krel.energy.rate]
    root: !block
      name: root
      role: supply
      children:
        # positional + keyword together
        krel: !organism {args: [krel], chains: 2, waste: shared.waste}
        # positional only; every keyword takes its default
        vash: !organism [vash]
        # a library block: a Python expander from suite/blocks.py
        feed: !enzyme
          substrate: shared.waste
          product: vash.energy.ME1
          enzyme: vash.energy.ME2
          Vmax: !q constant(2.0)
          K: !ref site_K              # !ref: structural NAME lookup

# ---- a task on it, and an experiment ----------------------------
task: !task
  world: !x world                     # the World built above
  # a value-type constructor (OutcomeObjective)
  objective: !outcome
    # ESCAPE 8: a trusted local Python reference, passed as a value
    scorer: !py helpers.health_score
    target: 4.0

experiment: !experiment
  name: !x label
  # QUOTED: `turns` is free, bound per condition from the axes
  task: !q brief(task=task, max_turns=turns)
  agent: act_commit
  axes: {turns: [4, 8, 16]}
  trials_per_condition: 3
  base_seed: 11
```

The Python the document leans on — three registered heads and one plain function:

```python
# helpers.py -- executed by `_includes_` under a trusted load.
# Nothing here knows about YAML.
from alienbio.expr import fn, expander, guard, GuardViolation, X


# FUNCTION head: arguments arrive evaluated.
@fn(summary="Hill response", range=(0.0, 1.0))
def hill(s: float, k: float, n: float = 1.0) -> float:
    return s**n / (k**n + s**n)


# EXPANDER head: arguments arrive as forms, plus the environment.
@expander(summary="A conversion chain in -> x1 -> ... -> out")
def chain(args, kwargs, env):
    # evaluate what is needed now ...
    src, dst = (env.evaluate(a) for a in args)
    n = env.evaluate(kwargs.get("length", 3))
    # ... pass through what should be drawn per hop
    rate = kwargs.get("rate", X.parse("lognormal(0.1, 0.3)"))
    mids = [f"{env.ns}.x{i}" for i in range(1, n)]
    nodes = [src, *mids, dst]
    hops = zip(nodes, nodes[1:])
    # returns DATA with forms inside; the interpreter evaluates it,
    # one child seed per key
    return {
        "molecules": {m: {} for m in mids},
        "reactions": {
            f"{env.ns}.hop{i}": {"reactants": [a], "products": [b],
                                 "rate": rate}
            for i, (a, b) in enumerate(hops, 1)
        },
    }


# GUARD: a predicate over the expanded fragment.
@guard
def max_pathway_length(expanded, ctx, max_length=5):
    if len(expanded["molecules"]) + 2 > max_length:
        raise GuardViolation(
            f"pathway too long: max_length={max_length}"
        )


# Not registered: reached only through !py.
def health_score(record) -> float:
    level = record.final_state.get("vash.energy.ME2", 0.0)
    return min(1.0, level / 4.0)
```

What evaluating `world` produces, in outline: `krel.energy.ME1…ME3` and `vash.energy.ME1…ME3` with their three reactions each (krel's `work` also emits `shared.waste`; vash's does not, because its `waste` was `null`), `krel.chain0` and `krel.chain1` each a run of `hop` reactions from `krel.energy.ME2` to `krel.S0` / `krel.S1` with interior `x` molecules and per-hop rates drawn from `hop_rate` under that hop's seed, `vash.chain0`, two `leak` reactions, and the `feed` enzyme block's fragment — all in one `World`, seeded so that editing `vash` re-rolls nothing under `krel`.

The same trees from Python, for a test or a Python-side generator:

```python
from alienbio.expr import X, Env, evaluate

# a file is a scope
env = Env.standard(seed=11, trusted=True).load("ecosystem.yaml")

# a head, positional + keyword
vash = evaluate(X.organism("vash", chains=1), env)

# the inline text, parsed to the same form
same = evaluate(X.parse('organism("vash", chains=1)'), env)

form = X.organism("vash", chains=1)
assert X.dump(form, style="structural") == \
    "!organism {args: [vash], chains: 1}\n"
```

### Legend — where each construct appears

| Construct | In the example |
|---|---|
| literal · data (untagged YAML) | `site_K: 0.5`; every `reactants:` list; `initial: {shared.waste: 0.0}` |
| name (lookup) · dotted path | `rate: !x base_rate`; `world: !x world`; `energy.reactions.work`-style paths in `control_surface` |
| `!ref` (structural name) | `K: !ref site_K` |
| inline call `!x` — operators, f-string, conditional, list display, builtins | `label`, `tags`, `weight: !x 100 + 10 * i`, `route_len` |
| structural call — mapping = keywords | `!enzyme {…}`, `!Reaction`, `!world`, `!experiment` |
| structural call — sequence = positional | `!energy_cycle [!x waste]`, `!organism [vash]` |
| structural call — `args:` + keywords together | `!organism {args: [krel], chains: 2, …}`, `!chain {args: […], length: …}` |
| quoted `!q` — deferred rate law | `regeneration.rate` (`ME3` bound by the simulator) |
| quoted `!q` — a `Dist` passed unsampled | `hop_rate`, `Vmax: !q constant(2.0)` |
| quoted `!q` — free names bound per condition | `experiment.task` (`turns`) |
| `let` · `each` (with `key`) · `if` · `run` · `seed` · `template` | `organism.body`; `molecules:` and `routes:`; `work.products`; `first_hop`; `k` / `world.seed`; `energy_cycle`, `organism` |
| YAML template — `positional` parameter names + keyword `params` with form defaults | `energy_cycle`, `organism` |
| Python function head `@fn` | `hill` (called from a quoted rate law) |
| Python expander head `@expander` | `chain` (forms in, data out; `env.ns` namespacing; pass-through of the `rate` form) |
| guard `@guard` — bare name and parameterised call, `on_fail` | `routes.body.guards` |
| constructor (`Entity` subclass) | `!Reaction` |
| library block (an expander shipped in `suite/blocks.py`) | `!enzyme`, `!block`, `!skeleton`, `!world` |
| `!py` local reference (trusted) | `scorer: !py helpers.health_score` |
| `!include` of Python (trusted) | `_includes_: [helpers.py]` |
| Python spelling `X.…` · `X.parse` · `X.dump` | the last listing |
| seeding — per-instance child seeds | `vash` re-rolls nothing under `krel`; each `hop` draws under its own key |

## The Group 4 collapse, in this language

The five template classes become five *kinds of form*, and the interpreter is the only "method" they have:

| Was (class) | Is (form) | Evaluates to |
|---|---|---|
| `Motif` | a **block** expander call — `!conflict_crux {…}`, `!source {…}` — or a `!template` over blocks | `Skeleton` (the bound pattern), when passed to `skeleton(...)` |
| `WorldEnvelope` | a **world** call — a drafter such as `!pressure {…}`, or `!world {skeleton: …, dists: …, features: …}` | `World` |
| `ObjectiveRecipe` | an **objective** call — `!objective {kind: answer, key: …, grader: …}` | `Objective` (+ `Question`) |
| `TaskArchetype` | a **task** call — `!task {world: …, objective: …, brief: …}`; the M27 archetype catalog becomes named expanders (`identify_pathway`, `diagnose`, …) that return such a form | `TaskInstance` |
| `SuiteSpec` | a **suite** call — `!suite {tasks: …, grid: …}`; an experiment file is one | `Suite` |

The build order F007 prescribes holds: the interpreter and the forms land *behind* the existing dataclasses first (each dataclass gains a `to_form()` / `from_form()` pair and `build_suite` is unchanged), the catalog and the drafters are re-expressed as expanders, and only then are the dataclasses deleted. ~~[[ABIO Expr Templates]]~~ walks each form.

## Decisions

Recorded here so they are not re-litigated; each names the alternative that lost.

- **D1 — Calls, not S-expressions or a custom syntax.** The abstract form is `head(args, kwargs)` and the inline spelling is Python call syntax. *Alternative:* Lisp-style lists `[head, arg, arg]`. Lost because keyword arguments are what make a six-dial drafter readable, and because the inline parser and sandbox already exist for Python syntax.
  *As built (M47.1):* `Call(head, args, kwargs)` in `expr/form.py`; `expr/parse.py` turns Python call syntax into it, `expr/x.py` builds it from Python.
- **D2 — Two head kinds, function and expander, with a fixed set of special forms.** *Alternative:* one kind (everything an expander). Lost because it would force every registered helper to learn `Form`; applicative functions let any existing Python callable register unchanged.
  *As built (M47.1):* `@fn` / `@expander` in `expr/registry.py`; seven special forms in `expr/interp.py` (`let` `each` `if` `quote` `run` `template` `seed`). Any callable registers unchanged.
- **D3 — Structure stays plain YAML; only holes are tagged.** *Alternative:* everything a call (`!molecules […]`). Lost on the owner's rule that structure is written as structure.
  *As built (M47.1):* untagged YAML is data through `expr/yaml_tags.py`; only tagged nodes become forms.
- **D4 — Structural calls are spelled with per-head YAML tags (`!pressure {…}`).** *Alternative A:* `!x` on a mapping with a reserved `fn:` key. *Alternative B:* the M1 key conventions (`_template_:`, `_as_ name:`). Both lost on readability: the tag puts the head where a reader looks for it, and the mapping under it is exactly the keyword list. Cost: five reserved tags and a YAML multi-constructor.
  *As built (M47.1):* the `!` multi-constructor on `ExprLoader`; reserved `!x !q !ref !include !py`; the old `!ev !_ !quote` are load errors naming the replacement (M47.7).
- **D5 — One registry, kind-tagged; views scope it.** *Alternative:* keep the per-kind registries (`rate_registry`, `scoring_registry`, …) and a separate Expr one. Lost on single-source-of-truth; the existing `get_rate` / `get_scoring` accessors become `registry.get(name, kind=…)`.
  *As built (M47.1/M47.7):* one `Registry` with `view(kinds)`; the per-kind registries and `get_rate` / `get_scoring` accessors were deleted with the M1 spec language, not aliased.
- **D6 — `!ev` becomes `!x`, `!_`/`!quote` become `!q`.** A mechanical rename, done at G4 close across the catalog and tests; no aliases survive (no legacy accumulation). *Alternative:* keep the old names. Lost because the old names describe a mechanism (`ev`aluate, `_` "later") rather than the thing, and this is the one moment the rename is free.
  *As built (M47.7):* the rename landed as removal — the catalog was rewritten in M47.4 and the M1 loader deleted, so there was nothing left to alias.
- **D7 — `!ref` is a lookup, not a hydration-time copy.** Lookup at evaluation gives the same value where it used to copy, and lets a reference see `let` bindings. The M1 parameter-copy semantics had no user that needed a *copy*.
  *As built (M47.1):* `!ref` constructs a `Name`; `Env.lookup` resolves it at evaluation.
- **D8 — Seeds re-key per named expansion** (`ctx.seed.child(name)`), never a shared stream. *Alternative:* one global `rng` advanced in evaluation order (what `EvalContext.rng` does today). Lost because it makes every draw depend on document order — editing one template re-rolls the whole world.
  *As built (M47.1):* `Ctx.child(label)` per named node, argument, `each` element, template call and guard retry (`retry{n}`).
- **D9 — Templates can be defined in YAML, but logic cannot.** `!template` bodies get `each`, `if`, `let` and calls, nothing more. When a template wants a search, a check, or a rejection loop, the answer is a Python expander or a `@guard`, never a richer special form.
  *As built (M47.1/M47.5):* `TemplateHead` bodies evaluate with the special forms only; logic is `@expander` / `@guard`. Template instances namespace their pools (`Env.pool`, M47.5).
- **D10 — Untrusted specs never register.** Registration is a Python-module or trusted-load act; `!py` keeps its `trusted=True` gate. The registry boundary is the whole security model, on top of the existing AST allowlist for inline text.
  *As built (M47.5):* `expr/include.py` — an untrusted load gets relative, contained, non-Python includes; `.py` includes and `!py` raise `UnsafeSpecError`; registration happens only from Python or a trusted load.

## Open questions

**Ratified 2026-08-29** — the owner adopted the design as written, including both leans below (per-head tags; the `!ev`→`!x` / `!_`→`!q` rename at G4 close), and additionally retired the `type.name:` typed-key convention and dropped `extends:`. Build: roadmap **M47**; testing: **M48**. The two entries stay as the record of the forks considered.

1. **Should structural calls use per-head tags (`!pressure {…}`, D4) or a single `!x` tag with the head as the mapping's first key?** Per-head tags read best and are adopted; the cost is that YAML tooling (linters, Obsidian's YAML view) treats unknown tags as opaque. **(A)** per-head tags, as written — *recommended*. **(B)** `!x {pressure: {pi: 0.5}}` — one tag, one constructor, but a reader must know the first key is the head.
2. **Do the rename D6 (`!ev`→`!x`, `!_`→`!q`) now, or keep the old tags forever?** *Lean: now.* It touches every catalog file and test once; leaving it makes the language read as two eras.

## History

- 2026-08-30 — **built**: M47.1–M47.8 landed (`ccb4a25` … `e8d1258`); an *as built* line under each decision; [[ABIO Expr Spec]] and [[ABIO Expr Python API]] are the reference for shipped code with every example executed in CI.

- 2026-08-29 — **ratified by the owner**; roadmap M47 (build) + M48 (capability test matrix) added; user docs [[ABIO Expr Spec]] + [[ABIO Expr Python API]] written; § A complete example added; `extends:` dropped, `type.name:` retired.
- 2026-08-28 — folder created; language, template catalog and Python-escape pages drafted as the G4 design note (owner's direction the same day: logic in Python, structure as templates, formulas either way; the format is Python-call-shaped; register functions and expanders into a Python-backed environment).
