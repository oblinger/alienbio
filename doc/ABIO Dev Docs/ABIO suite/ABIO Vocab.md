---
description: "`vocab`: M27.2's vocabulary builder — `build_vocabulary` gives every molecule, reaction and extra answer token of a world a seed-deterministic alien phrase from `generate_alien_name` (prefix, connector, suffix: 1024 names), re-deriving on collision, for the render round-trip guard. Source: `src/alienbio/suite/vocab.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Vocab](ha://p/ABIO%20Vocab) 
# ABIO Vocab
The builder of the per-world alien vocabulary that `build_suite` renders each task through to check it, drawn from a fixed pool of 1024 three-part names.

![ABIO Vocab](ABIO%20Vocab.svg) 
*Collisions* is the topic behind the bump loop (64 re-derivations, then an index suffix; ‡ the pool is 16 × 4 × 16 names).

`suite/vocab.py` authors phrases; [ABIO Render](ABIO%20Render.md) owns the `Vocabulary` type and its bijection check. Its one run-path caller is `pipeline.build_suite`, which builds a vocabulary per task (`seed.child(f"vocab/{i}")`, with the archetype's `extra_answer_tokens` such as `up`/`down`/`same`) and passes it only to the round-trip guard. The vocabulary is then discarded; the names an agent sees come from [ABIO NameMap](ABIO%20NameMap.md). The alien syllables moved here from the M1 `bio.skinning` module (T056). `build_vocabulary` is re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## vocab Interface
Two functions and one constant.

| vocab | |
| --- | --- |
| [generate_alien_name](#^generate-alien-name) | One three-part name |
| [build_vocabulary](#^build-vocabulary) | An injective map for a world |
| [_MAX_RESEED](#^max-reseed) | Re-derivations before the suffix |

**generate_alien_name**`(base: str, *, seed: Optional[int] = None) -> str`
    `prefix + connector + suffix` from `random.Random(seed)` over 16 prefixes, 4 connectors (`-`, `'`, `.`, none) and 16 suffixes; with no seed, the first 8 hex digits of `md5(base)`. Without a seed the name depends on `base` alone (`"m1"` is `"cri-el"` everywhere). ^generate-alien-name

**build_vocabulary**`(world: WorldImpl, seed: Seed = Seed(0), *, extra_tokens: Iterable[str] = ()) -> Vocabulary`
    Sorts the union of molecule ids, reaction ids and `extra_tokens`; gives each a name from `seed.child(token)`; on a collision with an earlier name re-derives from `seed.child(f"{token}#{bump}")` up to 64 times, then appends `-{index}`. Returns `Vocabulary(phrases)`, whose constructor re-checks injectivity. ^build-vocabulary

**_MAX_RESEED**` = 64`
    Bumped re-derivations per token before the index suffix. ^max-reseed




# Vocab Semantics

## Collisions
The pool holds 1024 names, so in a world of a few dozen nodes collisions are likely and the bump loop resolves them; a 900-node world from the HEAD export needed no suffix. Past 1024 tokens the suffix is the only way out and names gain a digit, which no generated name otherwise contains, so the result stays injective. Rendering only proves the structure survives the template; it never reaches an agent.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and `pipeline.build_suite`; the 1024-name pool (20 000 seeds) and the suffix-free 900-node vocabulary measured on the HEAD export, no spend. Consumer census: `pipeline.py` and the re-export.
