"""build command: Build a spec into a DAT folder or expand in-memory.

Usage:
    bio build <spec_path>                    # Expand spec to stdout
    bio build <spec_path> --seed 42          # Build DAT folder with seed
    bio build <spec_path> --output ./mydat   # Custom output path
    bio build <spec_path> --json             # Output as JSON instead of YAML

DAT Build:
    When the spec contains a `dat:` section with `path:` and `build:` fields,
    `bio build` creates a complete DAT folder using dvc_dat's create mechanism:

    1. Creates the target folder from the path template (via DatManager)
    2. Writes _spec_.yaml with metadata
    3. Processes build: section - calls generators, writes output files
    4. Returns the path to the created DAT folder

Path Templates:
    The `dat.path` field supports variable substitution via dvc_dat:
    - {seed} - the random seed used for generation
    - {YYYY}, {YY}, {MM}, {DD}, {HH}, {mm}, {SS} - date/time components
    - {unique} - auto-incrementing counter for uniqueness
    - {cwd} - current working directory

Example _spec_.yaml:
    dat:
      kind: Dat
      path: data/scenarios/mutualism_{seed}
    build:
      index.yaml: .           # Build current spec, write to index.yaml
      config.yaml: config     # Build 'config' generator, write to config.yaml
    run:
      - run . --agent claude
      - report -t tabular
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


def _is_dat_spec(spec: dict[str, Any]) -> bool:
    """Check if a spec is a buildable DAT spec.

    A buildable DAT spec has:
    - A 'dat' section (standard dvc_dat requirement)
    - A 'build' section (alienbio extension for generating content)
    - A path template in dat.path or dat.name

    Args:
        spec: Parsed spec dict

    Returns:
        True if this is a DAT spec that should create a folder
    """
    if "dat" not in spec or "build" not in spec:
        return False
    dat = spec.get("dat", {})
    if not isinstance(dat, dict):
        return False
    # Path can be in dat.path (alienbio convention) or dat.name (dvc_dat convention)
    return "path" in dat or "name" in dat


def _build_dat_folder(
    spec: dict[str, Any],
    source_path: Path,
    seed: int,
    output_path: Optional[Path] = None,
    verbose: bool = False,
) -> Path:
    """Build a DAT folder from a DAT spec using dvc_dat.

    Args:
        spec: The parsed DAT spec
        source_path: Path to the source spec file/folder
        seed: Random seed for generation
        output_path: Override the output path (optional)
        verbose: Print progress

    Returns:
        Path to the created DAT folder
    """
    from dvc_dat import Dat
    from alienbio import bio

    # Prepare the path using dvc_dat's path expansion
    # Support both dat.path (alienbio) and dat.name (dvc_dat) conventions
    dat_section = spec.get("dat", {})
    path_template = dat_section.get("path") or dat_section.get("name") or "data/builds/{seed}"

    if output_path:
        # User provided explicit output path
        dat_path = Path(output_path)
    else:
        # Use dvc_dat's prepare_dat_path with seed as a variable
        expanded_path, _ = Dat.manager.prepare_dat_path(
            path_template,
            variables={"seed": str(seed)},
            target_exists="overwrite",  # Allow rebuilding
        )
        dat_path = Path(expanded_path)

    if verbose:
        print(f"  Creating DAT folder: {dat_path}")

    # Create the folder
    dat_path.mkdir(parents=True, exist_ok=True)

    # Build _spec_.yaml with _built_with metadata
    spec_with_metadata = dict(spec)
    spec_with_metadata["_built_with"] = {
        "seed": seed,
        "timestamp": datetime.now().isoformat(),
        "source": str(source_path),
    }

    spec_file = dat_path / "_spec_.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec_with_metadata, f, default_flow_style=False, sort_keys=False)

    if verbose:
        print(f"  Wrote: {spec_file}")

    # Process build: section
    build_section = spec.get("build", {})
    for output_filename, generator_ref in build_section.items():
        if verbose:
            print(f"  Building: {output_filename} from {generator_ref}")

        if generator_ref == ".":
            # Special case: build the current spec (minus dat/build sections)
            content_spec = {k: v for k, v in spec.items() if k not in ("dat", "build", "run")}
            built_content = bio.build(content_spec, seed=seed)
        else:
            # Build from a named generator
            built_content = bio.build(generator_ref, seed=seed)

        # Write the output file
        output_file = dat_path / output_filename
        if isinstance(built_content, dict):
            with open(output_file, "w") as f:
                yaml.dump(built_content, f, default_flow_style=False, sort_keys=False)
        else:
            # If it's a typed object, convert to dict
            if hasattr(built_content, "to_dict"):
                content_dict = built_content.to_dict()
            elif hasattr(built_content, "__dict__"):
                content_dict = {k: v for k, v in vars(built_content).items() if not k.startswith("_")}
            else:
                content_dict = built_content

            with open(output_file, "w") as f:
                yaml.dump(content_dict, f, default_flow_style=False, sort_keys=False)

        if verbose:
            print(f"  Wrote: {output_file}")

    return dat_path


def build_command(args: list[str], verbose: bool = False) -> int:
    """Build a spec: create DAT folder or expand to stdout.

    If the spec is a DAT spec (has dat.path and build sections),
    creates a complete DAT folder. Otherwise, expands and prints.

    Args:
        args: Command arguments [spec_path] [--seed N] [--output PATH] [--json]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio

    # Parse arguments
    spec_path = None
    seed: Optional[int] = None
    output_path: Optional[Path] = None
    json_output = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        elif arg == "--output" and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        elif arg == "--json":
            json_output = True
            i += 1
        elif not arg.startswith("--"):
            if spec_path is None:
                spec_path = arg
            i += 1
        else:
            i += 1

    if not spec_path:
        print("Error: build command requires a spec path", file=sys.stderr)
        print("Usage: bio build <spec_path> [--seed N] [--output PATH] [--json]", file=sys.stderr)
        return 1

    path = Path(spec_path)

    # Handle relative paths - look in catalog/ if not found directly
    if not path.exists():
        catalog_path = Path("catalog") / path
        if catalog_path.exists():
            path = catalog_path
        else:
            print(f"Error: Spec path not found: {spec_path}", file=sys.stderr)
            print(f"  Tried: {spec_path}", file=sys.stderr)
            print(f"  Tried: {catalog_path}", file=sys.stderr)
            return 1

    if verbose:
        print(f"Building: {path}")

    try:
        # Load and expand the spec
        result = bio.expand(str(path))

        # Check if this is a DAT spec
        if _is_dat_spec(result):
            # Use seed 0 if not provided
            effective_seed = seed if seed is not None else 0

            if verbose:
                print(f"  Detected DAT spec, seed={effective_seed}")

            dat_path = _build_dat_folder(
                result,
                source_path=path,
                seed=effective_seed,
                output_path=output_path,
                verbose=verbose,
            )

            print(f"Created: {dat_path}")
            return 0

        else:
            # Not a DAT spec - just expand and print
            if json_output:
                import json
                print(json.dumps(result, indent=2, default=str))
            else:
                print(yaml.dump(result, default_flow_style=False))
            return 0

    except Exception as e:
        print(f"Error building spec: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1
