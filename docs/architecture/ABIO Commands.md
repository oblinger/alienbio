[[Architecture Docs]]

# Commands

Each command is available as both a CLI command (`bio <command>`) and a Python method (`bio.<command>()`).

| Command | CLI | Description |
| ------- |:---:| ----------- |
| [[ABIO Run\|run]] | ✓ | Execute a scenario or experiment |
| [[ABIO Build\|build]] | ✓ | Build a spec into a DAT or in-memory object |
| [[ABIO Fetch\|fetch]] | ✓ | Retrieve a spec or DAT by name |
| [[ABIO Store\|store]] | ✓ | Sync a DAT to remote storage |
| [[ABIO Report\|report]] | ✓ | Generate reports from results |
| [[ABIO Cd\|cd]] | ✓ | Get/set current DAT |
| [[ABIO Agent\|agent]] | ✓ | Agent management (list, add, test, remove) |
| [[ABIO Sim\|sim]] |   | Create a simulator from a scenario |
| [[ABIO Hydrate\|hydrate]] |   | Convert parsed YAML to typed Entity |
| [[ABIO Dehydrate\|dehydrate]] |   | Convert Entity back to serializable dict |

---

## Quick Reference

```bash
bio cd                                   # print current DAT
bio cd <dat>                             # change current DAT
bio fetch scenarios.baseline             # fetch spec
bio build scenarios.baseline --seed 42   # build spec → DAT
bio run scenarios.baseline --agent claude  # run scenario
bio report                               # generate reports
bio agent list                           # list registered agents
```

---

## See Also

- [[Execution Guide]] — Execution model overview
- [[Agent Interface]] — Agent protocol details
- [[Spec Language Reference]] — Spec language and evaluation pipeline
