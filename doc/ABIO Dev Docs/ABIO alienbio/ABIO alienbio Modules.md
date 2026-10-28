---
description: "module docs for the src/alienbio/ package root and commands/: the bio CLI and its verbs, configuration and API keys, the capability matrix, and the one-page test report"
---

| -[ABIO alienbio Modules](ABIO%20alienbio%20Modules.md)- | : module docs for the src/alienbio/ package root and commands/: the bio CLI and its verbs, configuration and API keys, the capability matrix, and the one-page test report |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Front door                                              | [CLI](ABIO%20CLI.md),  [SuiteCmd](ABIO%20SuiteCmd.md),                                                                                                                     |
| Settings                                                | [Config](ABIO%20Config.md),                                                                                                                                                |
| Test surface                                            | [Capabilities](ABIO%20Capabilities.md), |
| ...                                                     |                                                                                                                                                                            |

# ABIO alienbio Modules
Module docs for the modules at the root of `src/alienbio/` and under `src/alienbio/commands/`: the operator surface, everything a person types or reads to drive the instrument.

Named with the `Modules` qualifier because the plain [ABIO alienbio](../../ABIO%20Architecture/ABIO%20alienbio.md) is a published page. The package root holds four modules with public surface: `cli.py`, the `bio` front door, whose verb table `commands/__init__.py` shares its page; `config.py`, API keys and defaults; `capabilities.py`, the capability matrix; `report.py`, the one-page test report. Each verb module under `commands/` is documented with the module it fronts rather than in a mirrored `commands/` folder of four short pages: `suite_cmd.py`, the only verb with logic of its own, has a page; `config_cmd.py` is on the config page, `test_matrix_cmd.py` on the capabilities page, `report_cmd.py` on the report page. The experiment machinery the `suite` verb drives is under [ABIO suite](../ABIO%20suite/ABIO%20suite.md); the subsystem map with its seams is [ABIO-Operator-Surface](../../ABIO%20Architecture/ABIO-Operator-Surface.md).
