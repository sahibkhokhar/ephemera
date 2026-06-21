# Hermes-specific setup

Ephemera follows the [Agent Skills](https://agentskills.io) format. Hermes adds
optional frontmatter extensions on top.

## Environment variables

Hermes can prompt for secrets on skill load. Add this block to `SKILL.md`
frontmatter if you maintain a Hermes-only fork, or configure manually:

```yaml
required_environment_variables:
  - name: EPHEMERA_URL
    prompt: Ephemera instance URL
    help: "Base URL, e.g. http://192.168.1.50:8000"
    required_for: posting artifacts
  - name: EPHEMERA_API_KEY
    prompt: Ephemera API key (optional)
    help: Leave unset if writes are open
    required_for: authenticated writes
```

Hermes also supports nested metadata (not part of the Agent Skills spec):

```yaml
metadata:
  hermes:
    tags: [dev, logs, ci, sharing]
```

## Install

```bash
hermes skills install <owner>/ephemera   # when published to Skills Hub
```

Or copy `skills/ephemera/` into your Hermes skills directory.

## Test

```bash
hermes chat --toolsets skills -q "Post ./test.log to Ephemera as a log artifact"
```

Requires `EPHEMERA_URL` set and a running instance.
