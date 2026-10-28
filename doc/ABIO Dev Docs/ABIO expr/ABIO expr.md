---
description: "module docs for src/alienbio/expr/: the Expr language's forms, interpreter, environment, head registry, inline and structural spellings, and load-time includes"
---

| -[ABIO expr](ABIO%20expr.md)- | : module docs for src/alienbio/expr/: the Expr language's forms, interpreter, environment, head registry, inline and structural spellings, and load-time includes |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language                      | [Interp](ABIO%20Interp.md),  [Env](ABIO%20Env.md),                                                                                                                |
| Spellings                     | [Parse](ABIO%20Parse.md),  |
| ...                           |                                                                                                                                     |

# ABIO expr
Module docs for `src/alienbio/expr/`: the forms a spec is made of, the interpreter that gives them meaning, the environment it runs in, the registry that is the only door into Python, the two text spellings, and the includes resolved before anything evaluates.

A spec travels through the band in one order: YAML text is read by the structural loader ([ABIO YamlTags](ABIO%20YamlTags.md)), whose `!x` scalars go through the inline parser ([ABIO Parse](ABIO%20Parse.md)), into the five forms ([ABIO Form](ABIO%20Form.md)); `Env.load` resolves includes and `!py` under trust ([ABIO Include](ABIO%20Include.md)) and binds each top-level key lazily ([ABIO Env](ABIO%20Env.md)); `evaluate` dispatches every call by its head's kind ([ABIO Interp](ABIO%20Interp.md)) through the head table ([ABIO Registry](ABIO%20Registry.md)), whose builtin distributions, math and operators are [ABIO Heads](ABIO%20Heads.md). Two small modules have no page of their own: `x.py`, the Python spelling `X.<head>(...)`, is covered in [ABIO Form](ABIO%20Form.md), and `__init__.py`, the package's export list, in [ABIO Interp](ABIO%20Interp.md). The suite-side heads that build blocks, worlds, tasks and experiments live under [ABIO suite](../ABIO%20suite/ABIO%20suite.md); the subsystem map with its sandbox seams is [ABIO-Expr](../../ABIO%20Architecture/ABIO-Expr.md), the design is [ABIO Expr](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr.md), and the user's guide is [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md).
