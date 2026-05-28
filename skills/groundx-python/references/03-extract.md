# 3. The `extract` submodule

`src/groundx/extract/` is the largest hand-written area in the repo — agent
definitions, prompt templates, classes, celery tasks, post-processing, services,
and settings. It is **the** place hand-written contribution work tends to land,
and it has its own contribution rules separate from the generated SDK surface.

**Public API stability:** the extract submodule's public API is **provided
as-is and may change between minor versions**. External consumers should pin a
minor-version range (`groundx[extract] >= 3.5, < 3.6`). This is a deliberate
defensive default for an early-stage product surface — contributions should not
assume backward-compatibility constraints that the team hasn't yet committed to.

For the canonical contribution rules, see the repo's
[`AGENTS.md`](https://github.com/eyelevelai/groundx-python/blob/main/AGENTS.md).
The relevant sections are AGENTS.md §4 (the extract submodule) and
AGENTS.md §5 (extending or adding a hand-written submodule).

## 3.1 What the extract submodule is

- Hand-written, in `.fernignore` (so it survives regen)
- End users install it via `pip install groundx[extract]`
- Has a much larger optional-dep footprint than the core SDK (boto3, celery,
  fastapi, gspread, minio, openai, pillow, redis, smolagents, etc.) — see
  `[tool.poetry.extras]` in `pyproject.toml` for the live list
- Stability: see the front-of-file note above on the as-is contract

## 3.2 Adding a new optional dep

**Edit `.fern/metadata.json`, not `pyproject.toml`** (see [§2 core-sdk](./02-core-sdk.md) §2.2).
Two entries needed under `generatorConfig`:

1. `extra_dependencies.<name>` — `{"version": "*", "optional": true}`
2. `extras.extract` — append the dep name to the list

If the dep needs a mypy override (missing third-party stubs, etc.), append a
TOML block to `generatorConfig.pyproject_toml` in the same file.

Every new dep enlarges the `groundx[extract]` install footprint — justify in
the PR description.

## 3.3 Where extract tests live (post-AGE-67)

Extract unit tests live under `tests/extract/`, mirroring source structure:

- `tests/extract/classes/test_group.py` tests `src/groundx/extract/classes/group.py`
- `tests/extract/prompt/test_manager.py` tests `src/groundx/extract/prompt/manager.py`
- etc.

Tests use `unittest.TestCase` and import via absolute paths
(`from groundx.extract.classes.group import Group`).

Run with `poetry run pytest -rP -n auto`.

### Cross-test fixtures

Shared fixtures between extract test files (sample YAML constants, a `Source`
test-double) live in **underscore-prefixed modules** like
`tests/extract/prompt/_fixtures.py`. The underscore prefix keeps pytest from
collecting them as test modules.

### Public-API test helpers

Some public-API helpers carry the `Test*` prefix (`TestField`, `TestChunk`,
`TestDocumentPage`, `TestXRay`) — they are exported as part of `groundx.extract`
for downstream test code, **not** unittest classes. They live in
`src/groundx/extract/classes/testing.py` and carry `__test__ = False` so pytest
doesn't try to collect them.

The `Test*`-prefix-for-helper convention is a pre-existing API choice and is
preserved for backward compatibility. New helpers added to `testing.py` should
follow the same pattern (Test* name + `__test__ = False`).

## 3.4 Extending or adding a hand-written submodule

For extending within `extract/`:

- **New module in an existing subdir** — add the file, update the subdir's
  `__init__.py` to re-export the public surface, add a corresponding test
  under `tests/extract/<subdir>/` (mirroring the source path)
- **New subdir under extract** — create with hand-written `__init__.py`; no
  `.fernignore` change needed (parent `src/groundx/extract` is already covered)

For adding a brand-new sibling submodule (like extract, at `src/groundx/<name>/`):

1. **Add the path to `.fernignore` first** — otherwise Fern wipes the new
   directory on the next regen
2. Create the directory with a hand-written `__init__.py`
3. Users will import via `from groundx.<submodule> import X` — **not** from
   `groundx` at the top level (the top-level `__init__.py` is Fern-generated and
   won't know about the new submodule)
4. Add tests under `tests/<submodule>/` mirroring the source structure (the
   convention used for `tests/extract/`)

Surfacing new symbols at top-level `from groundx import ...` requires a Fern
generator-config change (see how `ingest.py` does it via
`.fern/metadata.json`'s `generatorConfig.client.exported_filename`). That's a
Fern-config conversation, not a self-service contribution.

## 3.5 mypy applies to extract

`poetry run mypy .` covers the extract submodule. Submodule-specific stub gaps
are handled via `[[tool.mypy.overrides]]` declared in
`.fern/metadata.json` → `generatorConfig.pyproject_toml` (existing overrides
for `groundx.extract.classes.document` and `groundx.extract.tasks.utility` live
there). Editing `pyproject.toml`'s overrides directly will be overwritten on
regen.

## 3.6 No live network in unit tests

Mock S3, Google Sheets, Redis, OpenAI, etc. The repo CI does not have live
GroundX credentials and the extract unit tests do not require them.

If a contribution needs to verify against the live GroundX API, gate it behind
an env-var skip — see repo `AGENTS.md` §6.

## 3.7 Pydantic V1 → V2 conventions

The hand-written extract code uses Pydantic V2's `model_config = ConfigDict(...)`
syntax (since AGE-67). New extract code that defines BaseModel subclasses should
follow this pattern, not the V1 `class Config:` syntax (which emits
`PydanticDeprecatedSince20` warnings on every import).

The Fern-generated core SDK already handles V1/V2 properly via runtime
branching (`if IS_PYDANTIC_V2:`), so no change is needed in the generated tree.
