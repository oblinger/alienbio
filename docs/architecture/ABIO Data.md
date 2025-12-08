# ABIO Data
**Parent**: [[ABIO infra]]
Organization of the `data/` folder and intent-based categories.

- The `data/` folder contains all persistent data managed by the [[DAT]] system. 
- Every folder containing a `_spec_.yaml` file is a self-describing DAT object with contents and provenance.
- Top-level categories represent **intent** - each is an intrinsic type:
- Each top-level category contains items of that intrinsic type. 
- The **top-level item** determines the category  - it's the "primary" type. Nested DATs inside can be any type.
- **Placement answers:** "What is this thing's primary purpose?"
	- `chem/kegg1/` = "I built this chemistry to be shared/reused"
	- `world/simple1/chem/` = "I built this chemistry for this specific world"
	- `test/T1/world/chem/` = "I built this chemistry for this specific test"
- This allows **cohesion** when things are built together, while still enabling **sharing** when components are used across multiple contexts.

## See Also
- [[DAT]] - The DAT system mechanics (`_spec.yaml` format, commitments)
- [[ABIO Files]] - Full project directory layout
