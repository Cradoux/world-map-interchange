## Summary

<!-- What changes, and why? Link related issues. -->

## Type

- [ ] Clarification / editorial (no behaviour change)
- [ ] Normative change: compatible
- [ ] Normative change: incompatible (see COMPATIBILITY.md)
- [ ] Registry change
- [ ] Reference tools / tests / examples only
- [ ] Docs / process

## Checklist

- [ ] Spec, schemas, registry, validator and examples agree (where affected)
- [ ] `uv run pytest` passes
- [ ] `uv run python scripts/generate_examples.py --check` and `uv run python scripts/render_registry.py --check` pass
- [ ] `CHANGELOG.md` updated (for anything beyond editorial changes)
- [ ] Unagreed material is marked **[Proposal]** and listed in `docs/open-decisions.md`
- [ ] No private worlds, proprietary code, credentials, local paths or non-redistributable assets
