# DAT - Data Management

How alienbio uses the DAT system for data management.

**Parent**: [[topics]]

## Overview

All folders in `data/` are DAT entries. A DAT is a folder containing a `_spec.yaml` file that describes its contents, provenance, and configuration.

## Commitments

1. **Every data folder is a DAT** - All folders under `data/` have a `_spec.yaml` at their root
2. **Recursive DATs** - DATs can contain child DATs, each with their own `_spec.yaml`
3. **Provenance tracking** - `_spec.yaml` records where data came from and how it was generated
4. **Immutable upstream** - Data in `upstream/` is never modified after download

## _spec.yaml

Each DAT has a `_spec.yaml` file containing:
- Type/kind of data
- Provenance (source, generation method)
- Version information
- Any parameters used in generation

Details of the `_spec.yaml` format are defined in the [dvc_dat repository](https://github.com/oblinger/dvc_dat).

## Cloud Storage

*Future*: Configuration for offloaded or cached cloud sources will be specified here. This enables large datasets to be stored remotely while maintaining local references.

## Cleanup Policies

*Future*: Different data types may have different retention policies:
- `upstream/` - Long-term retention (immutable reference data)
- `derived/` - Regenerable, can be cleaned up if upstream + catalog exist
- `runs/` - Policy varies by experiment type

## See Also

- [[ABIO Files]] - Data folder organization
- [dvc_dat](https://github.com/oblinger/dvc_dat) - Full DAT specification
