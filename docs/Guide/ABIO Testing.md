# Testing
**Topic**: [[ABIO Topics]]
Testing tiers (smoke, commit, release) and test organization.

## Overview

Testing is organized by both *type* (what's being tested) and *tier* (when tests run).

## Test Tiers

| Tier | Command | Duration | When |
|------|---------|----------|------|
| Smoke | `just smoke` | < 1 sec | Every execution (auto) |
| Commit | `just test` | < 10 sec | Every commit |
| Release | `just test-all` | minutes | Version bump, manual |

Smoke tests also run automatically on import (disable with `ALIENBIO_SMOKE=0`).

## Test Types

| Type | Directory | Purpose |
|------|-----------|---------|
| Unit | `tests/unit/` | Isolated function/class tests |
| Integration | `tests/integration/` | Components working together |
| Property | `tests/property/` | Invariants via random inputs (hypothesis) |
| Parity | `tests/parity/` | Python == Rust verification |
| Benchmarks | `tests/benchmarks/` | Performance characteristics |

Unit tests are further organized by subsystem:
```
tests/unit/
├─infra/
├─biology/
└─execution/
```

## Just Commands

```just
# Quick sanity check
just smoke

# Standard test suite (commit-level)
just test

# Full test suite (release)
just test-all

# Targeted
just test-unit
just test-integration
just test-property
just test-parity

# Rust
just test-rust
just bench-rust

# Combined workflows
just check          # lint + test
just release-check  # lint + test-all + bench
```

## Smoke Tests

Smoke tests run automatically on import and serve two purposes:
1. **Sanity checks** - system can start, basic invariants hold
2. **Decision reminders** - print messages about architectural decisions

```python
# Example smoke test with reminder
def check_context_uses_contextvar():
    from alienbio.context import _context
    import contextvars
    if not isinstance(_context, contextvars.ContextVar):
        print("⚠️  REMINDER: Context must use ContextVar, not plain global")
        return False
    return True
```

## Fixtures

Shared test data in YAML format, readable by both Python and Rust:
```
tests/fixtures/
├─molecules/
├─reactions/
└─systems/
```

## Pytest Markers

```python
@pytest.mark.smoke       # tier 1 - run on every execution
@pytest.mark.slow        # tier 3 - release only
@pytest.mark.rust        # requires rust build
@pytest.mark.interactive # requires user input (avoid)
```

Default (unmarked) tests run at commit tier.
