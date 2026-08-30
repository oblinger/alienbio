# EntityName
**Subsystem**: [[Parent Subsystem]] > Category
Brief one-sentence description of what this entity is. Can be multiple lines if needed for the description, but no blank lines in this top section.

## Overview
Short paragraph (2-4 sentences) explaining the purpose and role of this entity in the system. No blank line after the H2 tag.

| Property | Type | Description |
|----------|------|-------------|
| `property_name` | Type | Brief description |
| `another_prop` | Type | Brief description |

| Method | Returns | Description |
|--------|---------|-------------|
| `method_name(args)` | ReturnType | Brief description |
| `another_method()` | ReturnType | Brief description |

NOTE: No headings above the tables - the tables already have headings in them.

## Discussion
General discussion of design decisions, usage patterns, and important concepts. This section can have multiple subsections as needed. No blank line after the H2 tag.

### Subsection Topic
Details about a specific aspect.

### Another Topic
More details.

## Method Details
Detailed documentation for methods that need more explanation than fits in the table. No blank line after the H2 tag.

### `method_name(arg1: Type1, arg2: Type2) -> ReturnType`
Full description of what this method does.

**Args:**
- `arg1`: Description of first argument
- `arg2`: Description of second argument

**Returns:** Description of return value

**Raises:**
- `ErrorType`: When this error occurs

**Example:**
```python
result = entity.method_name(value1, value2)
```

### `another_method() -> ReturnType`
Description of this method.

## Protocol
```python
from typing import Protocol

class EntityName(Protocol):
    """Protocol definition."""

    @property
    def property_name(self) -> Type:
        """Description."""
        ...

    def method_name(self, arg: Type) -> ReturnType:
        """Description."""
        ...
```

## See Also
- [[RelatedEntity]] - How it relates
- [[AnotherEntity]] - Another relationship

---
## Template Notes

**Document structure rules:**
1. First line: H1 tag with entity name
2. Second line: **Bold relationship** to parent subsystem (no blank line after H1)
3. Third line(s): Description (can be multiple lines, no blank lines in top section)
4. No blank lines after any H2 tags
5. No headings above the Properties/Methods tables (tables have their own headers)
6. Properties table comes first, then Methods table, with a blank line between them
7. Discussion section for design decisions and usage patterns
8. Method Details section for detailed method documentation (H3 for each method with signature)
9. Protocol section with the Python protocol definition
10. See Also section at the bottom with related documents
