 [[Architecture Docs]]

# Commands

Bio class methods and CLI commands.

All operations are methods on the `Bio` class. Those marked with CLI are also available as `bio <command>` at the command line.

| Method                                       | CLI | Description                                 |
| -------------------------------------------- |:---:| ------------------------------------------- |
| [[commands/ABIO Run\|Bio.run()]]             |  ✓  | Execute a scenario or experiment            |
| [[commands/ABIO Build\|Bio.build()]]         |  ✓  | Build a spec into a DAT or in-memory object |
| [[commands/ABIO Fetch\|Bio.fetch()]]         |  ✓  | Retrieve a spec or DAT by name              |
| [[commands/ABIO Store\|Bio.store()]]         |  ✓  | Sync a DAT to remote storage                |
| [[commands/ABIO Report\|Bio.report()]]       |  ✓  | Generate reports from results               |
| [[commands/ABIO Cd\|Bio.cd()]]               |  ✓  | Get/set current DAT                         |
| [[commands/ABIO Agent\|Bio.agent]]           |  ✓  | Agent management (list, add, test, remove)  |
| [[commands/ABIO Sim\|Bio.sim()]]             |     | Create a simulator from a scenario          |
| [[commands/ABIO Hydrate\|Bio.hydrate()]]     |     | Convert parsed YAML to typed Entity         |
| [[commands/ABIO Dehydrate\|Bio.dehydrate()]] |     | Convert Entity back to serializable dict    |

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
