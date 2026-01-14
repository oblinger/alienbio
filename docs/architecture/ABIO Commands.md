[[Architecture Docs]]

# Commands

Bio class methods and CLI commands.

All operations are methods on the `Bio` class. Those marked with CLI are also available as `bio <command>` at the command line.

| Method | CLI | Description |
| ------ |:---:| ----------- |
| [Bio.run()](commands/ABIO Run.md) | ✓ | Execute a scenario or experiment |
| [Bio.build()](commands/ABIO Build.md) | ✓ | Build a spec into a DAT or in-memory object |
| [Bio.fetch()](commands/ABIO Fetch.md) | ✓ | Retrieve a spec or DAT by name |
| [Bio.store()](commands/ABIO Store.md) | ✓ | Sync a DAT to remote storage |
| [Bio.report()](commands/ABIO Report.md) | ✓ | Generate reports from results |
| [Bio.cd()](commands/ABIO Cd.md) | ✓ | Get/set current DAT |
| [Bio.agent](commands/ABIO Agent.md) | ✓ | Agent management (list, add, test, remove) |
| [Bio.sim()](commands/ABIO Sim.md) |   | Create a simulator from a scenario |
| [Bio.hydrate()](commands/ABIO Hydrate.md) |   | Convert parsed YAML to typed Entity |
| [Bio.dehydrate()](commands/ABIO Dehydrate.md) |   | Convert Entity back to serializable dict |

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
