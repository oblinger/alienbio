 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# bio.agent

Manage agent registrations.

## Synopsis

```bash
bio agent <subcommand> [options]
```

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `add <name>` | Register a new agent |
| `list` | Show registered agents |
| `test <name>` | Verify agent connection works |
| `remove <name>` | Delete agent and credentials |

## Examples

**Register an agent:**
```bash
bio agent add claude --api anthropic --model claude-opus-4
# → Enter API key: ****
# → Testing connection... OK
# → Agent 'claude' registered
```

**List registered agents:**
```bash
bio agent list
# → claude     anthropic/claude-opus-4
# → gpt-4      openai/gpt-4-turbo
```

**Test connection:**
```bash
bio agent test claude
# → Testing claude... OK (238ms)
```

**Remove an agent:**
```bash
bio agent remove claude
# → Agent 'claude' removed
```

## Configuration

Agent credentials are stored in `~/.config/alienbio/agents.yaml`:

```yaml
agents:
  claude:
    api: anthropic
    model: claude-opus-4
    api_key: sk-ant-...    # encrypted or plaintext
```

Never commit this file to version control.

## Built-in Agents

These agents require no registration:

| Agent | Description |
|-------|-------------|
| `random` | Random valid actions, seeded (lower bound baseline) |
| `scripted` | Predefined action sequence (verify scenario solvability) |
| `human` | Interactive CLI (manual exploration, debugging) |

## See Also

- [[ABIO Run|run]] — run with specific agent
- [[Execution Guide]] — execution model overview
- [[Agent Interface]] — agent protocol details
