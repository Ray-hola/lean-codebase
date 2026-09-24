## What this changes

<!-- One or two sentences. -->

## How it was verified

<!-- Paste test output, or the before/after of a script run. -->

```
python3 -m unittest discover -s tests -t . -b
```

## Checklist

- [ ] Standard library only (runs on clean Python 3.9+, no `pip install`)
- [ ] Tests pass locally; new behaviour has a test
- [ ] `SKILL.md` / `references/` updated if agent-facing behaviour changed
- [ ] No diverged duplicate is labelled "safe to merge"
