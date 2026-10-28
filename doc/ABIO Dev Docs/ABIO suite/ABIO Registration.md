---
description: "`registration`: the T030 registry side of the registration gate — `load_registry` parses and validates `catalog/registrations.yaml`, `resolve_registration` returns the `Registration` a spec's `registration:` claims or refuses, `Registration.to_dict` is the manifest stamp. Source: `src/alienbio/suite/registration.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Registration](ha://p/ABIO%20Registration) 
# ABIO Registration
The parser and resolver for the commit-tracked registry of filed pre-registrations, whose entries license a live model to run otherwise-guarded dials on named drafters.

![ABIO Registration](ABIO%20Registration.svg) 
*The entry contract* is the topic behind `_parse_entry` (exactly four keys; ‡ what the parse does not check).

`suite/registration.py` holds the registry side only. The guard side is [ABIO Guards](ABIO%20Guards.md): `registration_admission` calls `resolve_registration` with `REPO_ROOT / REGISTRY_RELPATH`, then refuses a drafter the build does not register or the spec's drafter outside the entry, and `no_peeking_violation` admits exactly the entry's dials. The claim is `ExperimentSpec.registration` ([ABIO ExperimentSpec](ABIO%20ExperimentSpec.md)); the stamps are the id on every record line (`experiment.py`) and `to_dict()` on the manifest ([ABIO Store](ABIO%20Store.md)). The registry file is `catalog/registrations.yaml`, three AUP entries at HEAD (`aup-awareness`, `aup-pressure`, `aup-exploration`). Nothing here is re-exported from `alienbio.suite`. The subsystem view is [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md).



## registration Interface
One constant and two functions.

| registration | |
| --- | --- |
| [REGISTRY_RELPATH](#^registry-relpath) | Where the registry lives in the repo |
| [load_registry](#^load-registry) | Parse and validate the whole file |
| [resolve_registration](#^resolve-registration) | The entry one id claims |

**REGISTRY_RELPATH**` = Path("catalog") / "registrations.yaml"`
    Relative to the repository root, which the caller resolves (`guards` uses `spec.REPO_ROOT`; tests monkeypatch it in `suite/guards.py`). ^registry-relpath

**load_registry**`(path: Path) -> dict[str, Registration]`
    A `SafeLoader` subclass that refuses a repeated mapping key (T088); an empty or comments-only file is an empty registry. Raises `ValueError` on a repeated id or field (`registration registry <path>: duplicate key 'a' at line N`), when the top level is not a mapping, an id is not a non-empty string, or any entry breaks the contract (§ [The entry contract](#the-entry-contract)). A missing file raises `FileNotFoundError`; callers reach it through `resolve_registration`, which checks first. ^load-registry

**resolve_registration**`(reg_id: str, path: Path) -> Registration`
    Raises `ValueError` when `path` does not exist ("file the entry first"), when the file fails to load, or when `reg_id` is not an id in it (the message lists the ids it has). Otherwise the entry. Parses the whole file on every call, so one malformed entry refuses every claim. ^resolve-registration



## Registration Interface
A frozen dataclass: one resolved entry.

| Registration | |
| --- | --- |
| [id](#^id) | The registry key a spec claims |
| [osf](#^osf) | The OSF registration id or URL |
| [filed](#^filed) | The filing date, `YYYY-MM-DD` |
| [dials](#^dials) | The admitted dial names |
| [drafters](#^drafters) | The admitted drafter names |
| [to_dict](#^to-dict) | The manifest's stamp |

**id**`: str`
    The key under which the entry sits. ^id

**osf**`: str`
    Non-empty after stripping. ^osf

**filed**`: str`
    A YAML date is turned into its ISO string; a string must match `^\d{4}-\d{2}-\d{2}$`. ^filed

**dials**`: frozenset[str]`
    Non-empty; names only, values are never licensed (an admitted `pi` admits every `pi`). ^dials

**drafters**`: frozenset[str]`
    Non-empty; checked against the built `DRAFTERS` by `guards.registration_admission`, not here. ^drafters

**to_dict**`() -> dict[str, Any]`
    `{id, osf, filed, dials, drafters}` with the two sets as sorted lists; written to `manifest.json` as `registration`. ^to-dict




# Registration Semantics

## The entry contract
An entry carries exactly `osf`, `filed`, `dials` and `drafters`; an unknown key, a missing key and a key given twice each raise, so the file cannot grow a side channel; the same id twice raises too (T088). `dials` and `drafters` must be non-empty lists of non-empty strings. What the parse leaves unchecked:

| Shape | What happens |
| --- | --- |
| Quoted impossible date `'2026-99-99'` | Accepted; only the shape is matched |
| Unquoted impossible date `2026-13-45` | `ValueError` naming the file, not the entry |
| A dial the build does not know | Accepted; it admits nothing |
| A repeated name in `dials` | Collapsed by the set |



## Provenance
The design's audit trail is that the file only changes by commit. The record line carries the id; the manifest carries the whole resolved entry, so a published run proves the license it ran under even if the registry is later edited. Unregistered runs carry no `registration` key on their lines, so the golden hashes do not move.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the duplicate-id last-wins, the quoted impossible date and the unattributed unquoted-date error confirmed by `load_registry` on scratch files from the HEAD export, no spend. Consumer census: `suite/guards.py` only in `src/`. Left out: how the guard combines the license with the no-peeking rule ([ABIO Guards](ABIO%20Guards.md)).
- 2026-10-28 — refreshed against `9db219f`: `load_registry` refuses a repeated id or field; an unquoted impossible date now raises a `ValueError` naming the file.
