[[ABIO docs]] → [[Alienbio User Guide]] 

# ABIO Expr Spec

The specification of **Expr**, the language every alienbio spec file is written in — by example: each section opens with the smallest file that shows the feature, then states the rules.

| Table of Contents |  |
|---|---|
| **[[#A whole file, first]]** |  |
| **[[#Data and forms]]** |  |
| **[[#Names and scope]]** |  |
| **[[#The YAML tags — complete]]** |  |
| **[[#Inline expressions — `!x`]]** |  |
| **[[#Calls]]** |  |
| **[[#Quoted forms — `!q`]]** |  |
| **[[#Special forms]]** |  |
|    [[#`let` — local bindings]] |  |
|    [[#`each` — a loop]] |  |
|    [[#`if` — a conditional]] |  |
|    [[#`quote` and `run`]] |  |
|    [[#`template` — define a function]] |  |
|    [[#`seed` — an explicit stream]] |  |
| **[[#Templates]]** |  |
| **[[#Guards]]** |  |
| **[[#Constructors]]** |  |
| **[[#Evaluation]]** |  |
| **[[#Builtins]]** |  |
| **[[#Files, includes and trust]]** |  |
| **[[#Migration from the old tags]]** |  |

> **Status.** Documents Expr as designed in [[ABIO Expr]] (F007 G4); the evaluator lands with G4. Until then the files on disk use the older tags (`!ev`, `!_`) — see § Migration from the old tags.


## A whole file, first

```yaml
# a spec file is a scope: every top-level key is a name
_includes_: [helpers.py]            # trusted: registers Python heads

k_on:  !x lognormal(1.0, 0.3)       # executed here, once; a number
k_hop: !q lognormal(0.1, 0.3)       # not executed; a form (a Dist)

chain: !template                    # a function you can call
  positional: [src, dst]
  params: {length: 3, rate: !x k_hop}
  body:
    reactions: !each
      over: !x range(length)
      as: i
      key: !x f"hop{i}"
      body: {reactants: [!x src], products: [!x dst], rate: !x rate}

world: !world
  skeleton: !skeleton
    root: !block
      name: root
      role: supply
      children:
        feed:  !source {pool: A, rate: !x k_on}
        route: !chain [A, B]        # a call: positional args
        drain: !sink {pool: B}      # a call: keyword args
```

Three kinds of line: **data** (untagged YAML — it is what it says), **forms** (tagged — something is computed), and **definitions** (`!template`, a form whose value is a function). Everything else in this document elaborates those three.

## Data and forms

```yaml
n: 3                                # data: the number 3
pools: [A, B, C]                    # data: a list of strings
rate: !x 2 * n                      # a form: evaluates to 6
site: {name: cell, volume: 1.0}     # data, with no forms inside
site2: {name: cell, volume: !x n}   # data, with a form inside → volume 3
```

- **Untagged YAML is data.** A scalar, list or mapping without a tag evaluates to itself, element by element. `A` in a `reactants:` list is the string `"A"` — a pool name — not a variable.
- **A tagged node is a form.** Evaluating it produces a value that replaces it. Forms nest inside data freely; data nests inside forms (a call's arguments are data or forms).
- There are exactly five form shapes: a **literal**, a **name**, **data** containing forms, a **call**, and a **quoted** form. Nothing else exists in the language.

## Names and scope

```yaml
K: 0.5                              # bound in the file scope
half: !x K / 2                      # a name, looked up: 0.25
same: !ref K                        # the structural spelling of a lookup
site: {cell: {volume: 2.0}}
vol: !x site.cell.volume            # a dotted path into data: 2.0
```

- **A file is a scope.** Every top-level key binds a name for the whole file. A `!template` body is a child scope holding its parameters; `!let` opens a child scope; lookup climbs outward.
- **A name in an inline expression is a lookup**; an unbound name is an error — there is no default and no silent `None`.
- **Dotted paths** step into data by key (`site.cell.volume`) or into an object's fields.
- `!ref K` is `!x K` for a YAML scalar position; it does *not* copy anything at load time — it is the same lookup, at evaluation.

## The YAML tags — complete

```yaml
a: !x lognormal(1.0, 0.3)           # inline expression, executed here
b: !q k * S / (Km + S)              # quoted expression, held as a form
c: !ref K                           # name lookup (structural spelling)
d: !source {pool: A, rate: 2.0}     # call of the head `source`, keywords
e: !chain [A, B]                    # call of the head `chain`, positionals
f: !upper krel                      # call with one positional argument
g: !template {positional: [x], body: {v: !x x}}   # a function
h: !each {over: [1, 2], as: i, body: !x i * 10}   # a special form
i: !include shared/defaults.yaml    # load-time file merge
j: !py helpers.score                # load-time Python reference (trusted)
```

| Tag | On | Means | When |
|---|---|---|---|
| `!x <text>` | a string | evaluate the Python-syntax expression; the node becomes its value | evaluation |
| `!q <text>` or `!q <node>` | a string or any node | hold the form unevaluated; the node becomes the *form* | evaluation (produces a `Form` value) |
| `!ref <name>` | a scalar | look the name up | evaluation |
| `!<head> <mapping>` | a mapping | call `head` with keyword arguments (positionals under `args:`) | evaluation |
| `!<head> [..]` | a sequence | call `head` with positional arguments | evaluation |
| `!<head> <scalar>` | a scalar | call `head` with one positional argument | evaluation |
| `!let` `!each` `!if` `!run` `!template` `!seed` | a mapping | the special forms (§ Special forms) — spelled like any call | evaluation, with their own rules |
| `!include <path>` | a scalar | merge a YAML file / read a text file / execute a `.py` file | load (hydration) |
| `!py <module.attr>` | a scalar | a Python object from a file beside the spec, as a value | load (hydration), trusted only |

Reserved: `!x`, `!q`, `!ref`, `!include`, `!py` cannot be head names. Every other `!name` is a call of a registered head; an unregistered head is an error at evaluation, naming the node's path.

## Inline expressions — `!x`

```yaml
n: 4
rate: !x 0.5 * n ** 2               # arithmetic
kind: !x "fast" if rate > 4 else "slow"     # conditional
label: !x f"world-{n:02d}-{kind}"   # f-string
mols: !x [f"M{i}" for i in range(n) if i != 2]   # comprehension
top: !x max(rate, 1.0)              # builtin
draw: !x lognormal(rate, 0.3)       # registered function
first: !x state.get("A", 0.0)       # method call on a value
```

An `!x` string is a **Python expression** — never a statement — parsed and checked against the sandbox allowlist, then evaluated with the current scope as its only namespace.

**Allowed:** literals, names and dotted paths, arithmetic and comparison operators, `and` / `or` / `not`, the conditional expression, f-strings, list / dict / set displays, subscripts and slices, comprehensions, calls of registered heads by name, method calls on values (`x.get(...)`).

**Forbidden, always:** `import`, assignment, `lambda`, `*args` / `**kwargs` unpacking, dunder attributes (`__class__`), interpreter internals (`gi_frame`, `f_back`, …), `getattr` / `eval` / `open` / `format` and the rest of the denied-builtin list, and any name not bound in scope. A forbidden construct fails at load with the node's path.

## Calls

```yaml
# the same call, three ways
a: !x source(pool="A", rate=2.0)                # inline
b: !source {pool: A, rate: 2.0}                 # structural, keywords
c: !chain [A, B]                                # structural, positionals
d: !chain {args: [A, B], length: 5}             # structural, both
e: !upper krel                                  # structural, one positional
```

- A call is **a head plus positional arguments plus keyword arguments**, exactly as a Python call — but it is data until evaluated.
- In a **mapping** call the keys are keyword arguments; the reserved key **`args:`** carries the positional values. In a **sequence** call every element is positional. A **scalar** is one positional.
- Arguments are forms: `rate: !x k * 2` computes, `rate: 2.0` is a literal, `rate: !q lognormal(0, 1)` passes a Dist.
- Heads come from the registry (§ Files, includes and trust): Python functions, Python expanders, YAML templates, constructors, and the special forms. A caller cannot tell which kind it is calling.
- **Function heads evaluate their arguments first**, left to right, then run. **Expander heads receive the argument forms** and decide what to evaluate. A template is an expander.

## Quoted forms — `!q`

```yaml
k_hop: !q lognormal(0.1, 0.3)       # a Dist: drawn once per use, by the user
first: !x run(k_hop)                # ...or drawn right here, once
r1:
  reactants: [S]
  products: [P]
  rate: !q Vmax * S / (Km + S)      # a rate law: S, P bound by the simulator
task: !q brief(task=t, max_turns=turns)   # `turns` bound per condition
```

A quoted form is **the form itself, as a value** — closed over the scope it was written in, with its free names left free. Three consumers use it:

| Consumer | How it evaluates the form |
|---|---|
| a block or template that takes a `Dist` | `sample(seed)`: the form is evaluated under that seed, once per use, so every hop / trial gets its own draw |
| the simulator (rate laws) and the grader (scores) | with the state or the timeline bound; compiled once for the hot path |
| the experiment runner | `run(form, condition)`: the swept axes bound per condition |

`run(form)` evaluates a quoted form now, in the current scope (optionally with extra bindings: `run(form, {"turns": 8})`). Think of `!q` as a lambda whose parameters are its free names.

## Special forms

Special forms are heads the interpreter implements itself, because each must control *how* its arguments are evaluated — `if` may not evaluate both branches, `each` must bind the loop variable before its body runs, `template` must keep its body unevaluated. They are spelled like any call; there are seven.

### `let` — local bindings

```yaml
w: !let
  bindings:                         # evaluated in order; later may use earlier
    n: 3
    k: !x n * 0.5
  body: {count: !x n, rate: !x k}   # → {count: 3, rate: 1.5}
```

### `each` — a loop

```yaml
mols: !each                         # a list
  over: !x range(1, 4)
  as: i
  body: !x f"M{i}"                  # → [M1, M2, M3]

mols: !each                         # a mapping, when `key` is given
  over: [a, b]
  as: x
  key: !x f"pool_{x}"
  body: {role: energy}              # → {pool_a: {...}, pool_b: {...}}
```

| Keyword | Meaning |
|---|---|
| `over` | a list (or a form producing one) |
| `as` | the loop variable's name |
| `body` | evaluated once per element with `as` bound |
| `key` | optional; when present the result is a mapping keyed by this form |
| `where` | optional filter form; elements for which it is false are skipped |

Each iteration evaluates under its own child seed (`ctx.seed.child(f"{key}")`), so inserting an element never re-rolls the others.

### `if` — a conditional

```yaml
products: !if
  cond: !x waste
  then: !x ["ME3", waste]
  else: [ME3]
```

Only the taken branch is evaluated. `else` is optional (defaults to `null`).

### `quote` and `run`

```yaml
d: !q lognormal(0, 1)               # !q is `quote` spelled as a tag
v: !x run(d)                        # evaluate it now
v2: !x run(d, {"seed_label": "again"})
```

### `template` — define a function

```yaml
sink_pair: !template
  positional: [pool]                # names of positional parameters
  params: {rate: 1.0, fast: false}  # keyword parameters with defaults
  body:
    slow: !sink {pool: !x pool, rate: !x rate}
    fast: !if {cond: !x fast, then: !sink {pool: !x pool, rate: !x rate * 10}}

drains: !sink_pair {args: [B], fast: true}
```

The value is a function (an expander head), bound to the key. See § Templates.

### `seed` — an explicit stream

```yaml
k: !x seed("kinetics")              # a Seed independent of the node's own
world: !world {seed: !x seed("world"), ...}
```

`seed(label)` is `ctx.seed.child(label)`. Needed only when one node wants several independent streams; ordinary draws are already keyed by their node.

## Templates

```yaml
energy_cycle: !template
  positional: [waste]
  params:
    carrier_count: 3
    rate: !x base_rate              # a form default; evaluated per call
  body:
    molecules: !each
      over: !x range(1, carrier_count + 1)
      as: i
      key: !x f"ME{i}"
      body: {role: energy}
    reactions:
      work:
        reactants: [ME2]
        products: !if
          cond: !x waste
          then: !x ["ME3", waste]
          else: [ME3]

krel: !energy_cycle [shared.waste]
vash: !energy_cycle {args: [null], carrier_count: 5}
```

- **Defining** a template evaluates nothing. **Calling** it evaluates `body` in a child scope where the parameters are bound to the call's arguments (defaults filled in), under the *call's* child seed. Two calls are two independent instances.
- `positional:` lists parameter **names**; `params:` lists keyword parameter names with **default forms**. (In a *call*, `args:` carries positional **values** — the two words are kept distinct on purpose.)
- A template body may contain calls of other templates, Python expanders, constructors and special forms — composition nests without limit. What a body may *not* contain is logic beyond `let` / `each` / `if`: a search, a rejection loop or a graph check is a Python expander ([[ABIO Expr Python API]]).
- Pool names inside a body are namespaced by the instance (`krel.ME1`) unless they arrived as arguments — that is how a parent wires its children: pass the pool's name in.
- A template defined in YAML and an expander defined in Python are indistinguishable to a caller.

## Guards

```yaml
route: !chain
  args: [A, B]
  length: !x poisson(4)
  guards: [no_new_cycles, !x max_pathway_length(max_length=6)]
  on_fail: retry                    # retry | prune | reject
```

A guard is a registered predicate run over what a call *produced*. A bare name is a guard with defaults; a call supplies parameters. On failure, `on_fail` decides: **retry** re-evaluates the call under the next child seed (up to `ctx.limits.attempts`), **prune** drops the offending elements, **reject** fails the whole evaluation with the guard's message. Guards are written in Python only.

## Constructors

```yaml
leak: !Reaction {name: leak, reactants: [A], products: [], rate: 0.01}
site: !Compartment {id: cell, kind: cell, volume: 1.0}
```

Every `Entity` subclass is a head under its class name; the mapping is its constructor's keywords. The older `_type:` key inside a mapping (`{_type: Reaction, ...}`) is the untagged spelling of the same call and is kept for saved worlds.

## Evaluation

```yaml
a: !x lognormal(0, 1)               # drawn under seed.child("a")
b: !x lognormal(0, 1)               # under seed.child("b"): independent of a
c: !x a + b                         # a and b are values by now
```

- **Order.** A document is evaluated top-down and inside-out: data element by element, a function call's arguments before the call, an expander's result after the expander returns it. A name may refer to any binding in scope regardless of position, but a cycle is an error.
- **Seeds.** The run has one root seed. Every named node evaluates under `parent_seed.child(key)`; every call under the call's node seed; every `each` iteration under its element key. Consequence: editing or inserting one node never changes another node's draws, and the same file with the same root seed is the same world, always.
- **Errors** carry the node's path: `world.skeleton.root.children.route: unknown head 'chian'`. An unbound name, an unknown head, an argument a head does not accept, a forbidden construct in `!x`, a failed `reject` guard — all fail loudly; nothing is defaulted.
- **Limits.** The interpreter caps the entity count, the expansion depth and the guard retry count (`ctx.limits`); exceeding one is an error, not a truncation.

## Builtins

Available in every `!x` / `!q` expression and as structural heads:

| Kind | Heads |
|---|---|
| distributions | `normal(mean, std)`, `lognormal(mean, sigma)`, `uniform(low, high)`, `poisson(lam)`, `exponential(scale)`, `choice(options)`, `discrete(weights)`, `constant(v)` |
| math | `abs`, `min`, `max`, `sum`, `round`, `pow`, `sqrt`, `exp`, `log`, `range`, `len` |
| conversion | `int`, `float`, `str`, `bool`, `list`, `dict`, `sorted`, `zip` |

Distribution heads **draw** when evaluated; quote them to pass a `Dist`. Rate laws see the same table (a rate law may call `sqrt` or `hill`), but not the world-building heads.

## Files, includes and trust

```yaml
_includes_: [helpers.py, ../shared/blocks.yaml]
defaults: !include shared/defaults.yaml
notes: !include brief.md
scorer: !py helpers.health_score
```

- `!include x.yaml` merges a YAML file into place; `!include x.md` reads text; `!include x.py` **executes** the file so its decorators register heads. `_includes_:` at the top of a file is the list form.
- `!py module.attr` yields a Python object as a value (a callable to pass to a head that takes one). It is *not* a head: to call it from `!x`, bind it first (`let`).
- **Trust.** A spec is loaded *untrusted* by default: it may call any registered head with any arguments, define templates, and use every tag except `!py` and `.py` includes, which raise `UnsafeSpecError`. Only a trusted load (`trusted=True`: the framework's own catalog, local development) executes Python. Registration is the only way new heads exist, and it never happens from an untrusted file.

## Migration from the old tags

The evaluator on `main` today ([[Spec Language Reference]]) uses different spellings for the same three ideas:

| Old | New | Note |
|---|---|---|
| `!ev expr` | `!x expr` | identical semantics and sandbox |
| `!_ expr`, `!quote expr` | `!q expr` | a quoted form is now a first-class value (a `Dist`, a rate law) |
| `!ref name` | `!ref name` | now a lookup at evaluation, not a copy at load |
| `template.name:` + `_params_` / `_ports_` / `_instantiate_` / `_as_ x{i in 1..n}` | `name: !template` + `params` / pool-name arguments / a call in the body / `!each` | the M1 generator DSL ([[Generator Spec]]) |
| `_guards_:` | `guards:` on the call | |
| `extends: base` | `!merge [!x base, {...}]` | |
| `type.name:` typed keys | `!Type {...}` constructors | |

The rename is mechanical and lands at the close of G4; no aliases survive it.
