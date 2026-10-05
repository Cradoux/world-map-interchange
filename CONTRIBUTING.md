# Contributing

Thank you for helping shape World Map Interchange. At this experimental stage, the most valuable contributions are
**discussion and evidence**: what your tool produces or consumes, where the draft is ambiguous, and where an exchange
between tools failed.

## Ways to contribute

| You want to... | Do this |
|---|---|
| Propose a new quantity, layer kind, geometry or field | Open a [proposal issue](https://github.com/Cradoux/world-map-interchange/issues/new?template=proposal.yml) |
| Point out unclear or contradictory text | Open an [ambiguity issue](https://github.com/Cradoux/world-map-interchange/issues/new?template=ambiguity.yml) |
| Report that a package from one tool was misread by another | Open an [interoperability-failure issue](https://github.com/Cradoux/world-map-interchange/issues/new?template=interoperability-failure.yml) |
| Fix a typo, a test or the reference tools | Open a pull request |
| Comment on a provisional choice | Comment on its issue, or reference its number in [docs/open-decisions.md](docs/open-decisions.md) |

Please keep shared material free of private worlds, proprietary source code, credentials, local paths and third-party
assets you cannot redistribute. Packages attached to issues should be minimal and synthetic where possible, and must
declare their licence in `package.license`.

## Changing the specification

1. Discuss significant changes in an issue first. Small clarifications can go straight to a PR.
2. A PR that changes normative behaviour must update **all** of the following together:
   - `spec/<version>/specification.md`;
   - `schemas/<version>/*.schema.json`, where the change is structural;
   - `registry/<version>/quantities.json`, then regenerate the registry page with `uv run python scripts/render_registry.py`;
   - the reference validator and tests;
   - examples, if relevant, regenerated with `uv run python scripts/generate_examples.py`;
   - `CHANGELOG.md`.
3. Note in the PR description whether the change is compatible ([COMPATIBILITY.md](COMPATIBILITY.md)).
4. Mark anything not yet agreed as **[Proposal]** in the text. Don't present it as settled.

## Adding a registry quantity

A new registry quantity needs:

- a precise definition that says what is and isn't included (for example liquid only or all phases, terrain height or
  sea-level reduced);
- the layer kind, the allowed units (from the unit table, or a proposal to extend the table) and the canonical unit;
- temporal semantics (`snapshot`, `aggregated` or `any`), whether it is an accumulation, and its physical valid range;
- a qualifier schema for anything a consumer must know;
- at least one synthetic example layer, or a test.

Until a quantity is accepted, use a namespaced extension (`yourtool:name`) with a definition. Nothing is lost while
discussion continues.

## Development setup

```bash
uv sync --locked
uv run pytest
uv run python scripts/generate_examples.py --check
uv run python scripts/render_registry.py --check
uv run wmi validate examples/valid/climate-only
```

Without uv: `pip install -e . pytest`, then run the same commands without `uv run`.

Style: keep dependencies minimal (currently `numpy`, `pillow` and `jsonschema`). Error messages should say what is wrong,
where (file and JSON Pointer), and how to fix it.

## Conduct

Participation is subject to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Licensing of contributions

By contributing to this repository you agree that your contribution to the repository's original content is licensed
under the MIT licence. Datasets you attach keep the licence you declare for them.
