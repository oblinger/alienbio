 [[Architecture Docs]]

# Builtins

Built-in functions available for use in specs and Python code.

---

## Usage

These functions are available in multiple contexts:

```yaml
# In !ev expressions
count: !ev normal(50, 10)

# In !_ (quoted) expressions
rate: !_ uniform(0.1, 0.5)
```

```python
# In Python code
from alienbio.builtins import normal, uniform

value = normal(50, 10)
```

---

## Distribution Functions

| Function | Description |
|----------|-------------|
| `normal(mean, std)` | Normal distribution sample |
| `uniform(low, high)` | Uniform distribution sample |
| `lognormal(mean, sigma)` | Log-normal distribution |
| `poisson(lam)` | Poisson distribution |
| `exponential(scale)` | Exponential distribution |
| `choice(options)` | Random choice from list |
| `discrete(weights)` | Weighted random index |

---

## Safe Python Builtins

These Python builtins are available in expressions:

`abs`, `min`, `max`, `sum`, `len`, `range`, `int`, `float`, `str`, `list`, `dict`, `True`, `False`, `None`

---

## See Also

- [[Spec Language Reference]] — YAML syntax and evaluation
- [Scope](modules/Scope.md) — Scope and evaluation context
