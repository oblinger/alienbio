[[Architecture Docs]]

# Commands

Bio class methods and CLI commands.

All operations are methods on the `Bio` class. Those marked with CLI are also available as `bio <command>` at the command line.

| Method | CLI | Description |
| ------ |:---:| ----------- |
| [[ABIO Run\|bio.run()]] | ✓ | Execute a scenario or experiment |
| [[ABIO Build\|bio.build()]] | ✓ | Build a spec into a DAT or in-memory object |
| [[ABIO Fetch\|bio.fetch()]] | ✓ | Retrieve a spec or DAT by name |
| [[ABIO Store\|bio.store()]] | ✓ | Sync a DAT to remote storage |
| [[ABIO Report\|bio.report()]] | ✓ | Generate reports from results |
| [[ABIO Cd\|bio.cd()]] | ✓ | Get/set current DAT |
| [[ABIO Agent\|bio.agent]] | ✓ | Agent management (list, add, test, remove) |
| [[ABIO Sim\|bio.sim()]] |   | Create a simulator from a scenario |
| [[ABIO Hydrate\|bio.hydrate()]] |   | Convert parsed YAML to typed Entity |
| [[ABIO Dehydrate\|bio.dehydrate()]] |   | Convert Entity back to serializable dict |

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
