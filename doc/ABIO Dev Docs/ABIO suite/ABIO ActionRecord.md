---
description: "`info_seeking`: the `ActionRecord` every trial logs per action (kind, destructive, accepted, reason, target, value, delta) and five closed-form metrics over a log — `info_seeking_count`/`_ratio`, `destructive_count`/`_rate`, `actions_before_commit`. The record is on every run path; the metrics reach none. Source: `src/alienbio/suite/info_seeking.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO ActionRecord](ha://p/ABIO%20ActionRecord) 
# ABIO ActionRecord
The one-line log entry the runner writes for every action an agent takes, and five generic counts over a log of them.

![ABIO ActionRecord](ABIO%20ActionRecord.svg) 
*Accepted versus logged* is the topic behind the two halves of the figure (‡: the generic metrics and the family scorers both count accepted actions only).

`suite/info_seeking.py` is named for M33.8's metrics, but its live export is the dataclass. `runner.run` builds one `ActionRecord` per agent action ([ABIO Runner](ABIO%20Runner.md) § Rejection as data); it rides `TrialRecord.action_log` ([ABIO TrialRecord](ABIO%20TrialRecord.md)) and round-trips through `records.jsonl` ([ABIO Store](ABIO%20Store.md)). The analysis families read the log directly with their own rules: [ABIO Caution](ABIO%20Caution.md), [ABIO Hazard](ABIO%20Hazard.md), [ABIO Census](ABIO%20Census.md), [ABIO Degradation](ABIO%20Degradation.md), [ABIO Faking](ABIO%20Faking.md), [ABIO Realism](ABIO%20Realism.md). The five metric functions are re-exported from `alienbio.suite` and wrapped as three `TrialRecord` methods, none of which any module in `src/` calls; their callers are tests. The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md).



## ActionRecord Interface
A frozen dataclass: one logged action. Only `kind` is required, so hand-built fixtures construct with one argument.

| ActionRecord | |
| --- | --- |
| [kind](#^kind) | The action's type tag |
| [destructive](#^destructive) | It irreversibly changed the world |
| [accepted](#^accepted) | The runner applied it |
| [reason](#^reason) | Why it was rejected, or a note |
| [target](#^target) | The probe or lever it named |
| [value](#^value) | The requested `Intervene` value |
| [delta](#^delta) | Applied setting minus the prior one |

**kind**`: str`
    The runner writes the action class name lowercased (`measure`, `intervene`, `commit`, `wait`), or `assay` for a `Measure` of a destructive assay. Opaque to this module. ^kind

**destructive**`: bool = False`
    The runner sets it only on an accepted action: every assay, and an `Intervene` on a lever the brief declares irreversible. ^destructive

**accepted**`: bool = True`
    `False` for an illegal action (unknown probe or lever, a lever off the surface, a non-finite or negative value, an unknown action type); the trial continues. ^accepted

**reason**`: str = ""`
    The rejection text; on an accepted over-cap `Intervene`, the T023 clamp note; a cost the agent tried to set is appended either way. ^reason

**target**`: str = ""`
    The probe of a `Measure` or the lever of an `Intervene`; empty otherwise. Read by the hazard scorer. ^target

**value**`: Optional[float] = None`
    The requested `Intervene.value` whenever finite, accepted or not (T046). ^value

**delta**`: Optional[float] = None`
    Post-clamp applied value minus the prior setting, for an accepted `Intervene` whose prior is one number (a plain-number reaction rate, or a molecule equal across compartments). Tells a throttle-down from a throttle-up, since an `Intervene` sets rather than adds. ^delta



## info_seeking Interface
Five functions over a `Sequence[ActionRecord]`; each first drops the rejected actions (private `_accepted`, T088 info_seeking 1) and none reads `target`, `value` or `delta`.

| info_seeking | |
| --- | --- |
| [info_seeking_count](#^info-seeking-count) | Accepted actions whose kind is investigative |
| [info_seeking_ratio](#^info-seeking-ratio) | That count over the accepted actions |
| [destructive_count](#^destructive-count) | Accepted actions marked destructive |
| [destructive_rate](#^destructive-rate) | That count over the accepted actions |
| [actions_before_commit](#^actions-before-commit) | Accepted actions before the first accepted commit |

**info_seeking_count**`(actions, investigative_kinds: Collection[str]) -> int`
    Accepted actions with `kind in investigative_kinds`. ^info-seeking-count

**info_seeking_ratio**`(actions, investigative_kinds: Collection[str]) -> float`
    The count over the accepted actions; `0.0` on a log with no accepted action. ^info-seeking-ratio

**destructive_count**`(actions) -> int`
    Accepted actions with `destructive` set. ^destructive-count

**destructive_rate**`(actions) -> float`
    The count over the accepted actions; `0.0` on a log with no accepted action. ^destructive-rate

**actions_before_commit**`(actions, commit_kinds: Collection[str]) -> int`
    The number of accepted actions before the first accepted action whose kind is in `commit_kinds`, or the accepted count when none commits. A rejected commit is skipped. ^actions-before-commit




# ActionRecord Semantics

## Accepted versus logged
The log holds every action the agent emitted, legal or not. The runner keeps `destructive` honest (only accepted actions are marked), but `kind` is written for rejected actions too. The generic metrics drop rejected actions before counting (T088 info_seeking 1), so an illegal `Measure` of an unknown probe is not investigation and a rejected action neither counts nor dilutes `destructive_rate`, the same rule the family scorers use (Caution's info-seeking is accepted `measure`s before the first `commit`). The report still shows only the families' numbers.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and the construction site in `runner.py` (`ActionRecord(` at ~938), no spend. Consumer census (`git grep -w` over `src/` and `tests/`): the dataclass in `runner`, `store`, `trial` and seven analysis modules; the five metrics in `trial.py`'s three wrapper methods and `tests/suite/test_info_seeking.py` only. Not determined: whether the metrics should be retired or made to read `accepted` (T088 § suite/info_seeking).
- 2026-10-28 — refreshed against `9db219f`: the five metrics count accepted actions only, ratios over accepted actions, `actions_before_commit` to the first accepted commit.
