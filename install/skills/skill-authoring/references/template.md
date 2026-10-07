Copy this to `~/.agents/skills/<name>/SKILL.md` and fill it in.

```
---
name: <name>
description: <What it does. When to use it. One or two sentences, under 300 characters.>
---

# <name>

1. <Exact command or action.>
2. <Next step.>

Notes: <only what the model would get wrong.>
```

Python script header:

```
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""One line: what it does. Usage: name.py <args>"""
```

Bash script header:

```
#!/usr/bin/env bash
set -euo pipefail
```
