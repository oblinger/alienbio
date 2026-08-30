# Documentation
**Topic**: [[ABIO Topics]]
Documentation standards and conventions.

## File Tree Notation

Three approaches for representing directory structures in documentation.

### Approach 1: Code Block (monospace)
```
alienbio/
├─src/
│ ├─alienbio/          # Python package
│ └─rust/              # Rust crate
├─tests/
│ ├─unit/              # Fast isolated tests
│ └─integration/       # Component tests
└─docs/                # Documentation
```

### Approach 2: Tabs with Tree Characters
**alienbio/** 				# Project root
├ **src/** 					# Source code
 │	├ **alienbio/** 		# Python package
 │	└ **rust/** - Rust crate
├	**tests/** - Test suite
 │	├ **unit/** - Fast isolated tests
 │	└ **integration/** - Component tests
└ **docs/** - Documentation

### Approach 3: Nested Bullets
- **alienbio/** - Project root
  - **src/** - Source code
    - **alienbio/** - Python package
    - **rust/** - Rust crate
  - **tests/** - Test suite
    - **unit/** - Fast isolated tests
    - **integration/** - Component tests
  - **docs/** - Documentation

## Conventions
- Use single-character tree connectors (├, └, │) to save horizontal space
- Keep descriptions short to fit on one line
- For deep nesting, prefer monospace code blocks
