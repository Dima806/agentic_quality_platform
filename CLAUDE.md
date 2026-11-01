# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository. The
authoritative product spec is [`.llm/PRD_agentic_quality_platform.md`](.llm/PRD_agentic_quality_platform.md);
when this file and the PRD disagree, the PRD wins — update this file to match.

---

## What this is

An **agentic quality platform**. The first module — and the only one that
exists at first — is an **end-to-end test runner** that executes plain-language
Gherkin `.feature` files as live browser tests with **no step definitions, page
objects, selectors, or waits**. The feature file *is* the whole test.

A reasoning model reads **intent**; deterministic Python holds the **data and the
assertions**; a human reviews the **evidence**. That split is the heart of the
design — keep it intact in everything you build.

Over later phases the runner's pieces become **tools**, a reasoning agent is put
in front of them to decide which to run, and heavier capabilities move behind an
agent-to-agent (A2A) contract. Build the foundation first; don't build ahead.

Reference implementation to draw patterns from (not a repo we extend):
<https://github.com/Dima806/agentic_e2e-testing>.

---

## Golden rules (do not violate without changing the PRD)

1. **The model decides and drives; code holds the data, the assertions, and the
   record.** The model never carries, reformats, rounds, or recites asserted
   values. *"The data never passes through the model's mouth."*
2. **One hard boundary: selectors live only in the browser client.** Only
   `aqp.browser` may talk to the browser-automation MCP server. No selector,
   locator, or raw Playwright call ever appears above that layer — elements are
   addressed by snapshot references (e.g. `e12`), never CSS/XPath. Enforced by a
   lint rule (ruff banned-api) **and** an architecture test.
3. **Exact numeric comparison, always.** `272.00` must stay `272.00` — never
   `272` or `272.0`. No rounding, no reformatting. Comparisons happen in Python.
4. **Bounded retries, fail-fast, nothing silently dropped.** At most **2
   attempts** per step, then stop; the first *real* (non-recoverable) failure
   ends the scenario; every remaining step is recorded as `SKIPPED`.
5. **One step at a time.** The executor sees only the current step and the
   current snapshot — never the whole scenario. This is a harness decision that
   buys reliability and cheap, cacheable tokens; don't widen the context to
   "help" the model.
6. **Fits a 2-CPU Codespace.** Concurrency ≤ 2 everywhere: ≤ 2 parallel CI jobs,
   **one browser context at a time** inside a job. Stream artifacts to disk —
   never hold a whole run in memory.
7. **No custom `.devcontainer`.** Provisioning lives in version-controlled
   scripts (`make setup` → `scripts/bootstrap.sh`), not in container config.
8. **Secrets stay in the environment.** `ANTHROPIC_API_KEY` comes from the env;
   it is never committed, logged, or written to an artifact.
9. **Keep the agentic surface minimal.** Only the per-step executor/evaluator
   loop talks to a model. Everything else is plain, deterministic, testable
   Python.

---

## Commands

Provision once per fresh Codespace, then use the short targets. Run `make help`
for the full list.

| Command | What it does |
| --- | --- |
| `make setup` | One-time provisioning via `scripts/bootstrap.sh` (Node, Playwright MCP + browser OS deps, Python deps). **Do not** replace this with devcontainer config. |
| `make run FEATURE=<path>` | Run a feature file or a directory of them. Defaults to `features/`. |
| `make test` | Run the unit test suite (mocks the MCP client and the agents — no live browser or model needed). |
| `make lint` | `ruff check` + the import-boundary contract. |
| `make format` | `ruff format` + import sorting. |
| `make typecheck` | `mypy` over `src/`. |
| `make ci` | `lint` + `typecheck` + `test` — the full gate (`make check` is an alias). Run this before you call work done. |
| `make clean` | Remove caches and generated artifacts. |

Direct CLI (what `make run` wraps):

```bash
aqp run <path-to-feature-or-dir>     # e.g. aqp run features/refund.feature
```

---

## Architecture

A deterministic Python pipeline with a **single agentic sub-loop**. Only the
per-step loop talks to a model.

```
.feature  →  validate   →  parse   →  ┌─ PER-STEP LOOP (the only agentic part) ─┐  →  artifacts
(Gherkin)    (pytest-bdd)  (steps)     │  executor (acts)                         │     step_status
                                       │  evaluator (judges)   ⇄   Browser-MCP    │     trace · tokens
                                       │  assertion engine (compares in code)     │     screenshots
                                       └──────────────────────────────────────────┘     report.json
```

### Package layout (`src/` layout — implemented)

```
src/aqp/
  __init__.py
  cli.py            # `aqp run <path>` (+ `--collect-only`) entry point
  config.py         # max_attempts, model IDs, MCP endpoint, max_parallel — defaults + aqp.toml + env
  errors.py         # AQPError hierarchy (FeatureValidationError, InfrastructureError, ...)
  models.py         # typed records: Step, Verdict, StepReport, ScenarioReport, SuiteSummary, TokenUsage
  ports.py          # the Protocols (Browser, LLM, StepExecutor, StepEvaluator) the core depends on
  features/
    loader.py       # collect & validate .feature files via pytest-bdd; fail early on bad Gherkin
    parser.py       # scenario → ordered list of typed steps (keyword, text, optional data table)
  browser/
    mcp_client.py   # THE ONLY module that talks to Browser-MCP. Selectors/refs live here, nowhere else.
  agents/
    llm.py          # AnthropicLLM — the only module that imports the Claude SDK
    prompts.py      # system prompts + structured-output tool schemas (narrow per-step context)
    executor.py     # one step + snapshot → choose & call browser tool(s) via the LLM port
    evaluator.py    # step + action + snapshot → pass | fail{failure_class, retryable, reason}
  assertions/
    engine.py       # compare located on-screen values in code, exact-match, no rounding
  runner/
    loop.py         # loop controller: attempt cap, fail-fast, skip, classify — deterministic
    artifacts.py    # stream step status/trace/tokens/screenshots to disk; write report.json
    summary.py      # aggregate per-feature outcomes into a suite summary

tests/              # parser, loader, assertion engine, loop controller, summary, config, cli,
                    # artifacts, architecture test — fakes implement the ports; no browser or model
features/           # example .feature files (refund.feature)
scripts/bootstrap.sh
.github/workflows/  # CI matrix (≤ 2 parallel) → suite summary — PLANNED, not yet added
```

The deterministic core (`features`, `assertions`, `runner`, `models`) depends
only on the `ports` Protocols; real adapters (`browser/mcp_client.py`,
`agents/llm.py`) are injected. Only `agents/llm.py` imports the Claude SDK and
only `browser/mcp_client.py` imports the MCP SDK — which is what makes the core
testable with fakes.

### The one hard boundary, concretely

- `aqp.browser.mcp_client` is a thin wrapper over the browser-automation MCP
  server (a Playwright-style MCP exposing `navigate`, `snapshot`, `find`,
  `click`, `type`, `assert-visible`). MCP endpoint: `stdio://@playwright/mcp`.
- No module outside `aqp.browser` imports `playwright` or constructs a selector.
  The ruff `banned-api` rule flags it; `tests/test_architecture.py` fails the
  build if an import crosses the line. If you need a new browser capability, add
  it to the client — don't reach around it.

### The agents

The executor and evaluator are calls to the **Claude Platform API** (Messages
API, with tool use). Model IDs are **configuration, not hard-coded**:

```toml
# config defaults (see src/aqp/config.py)
executor_model  = "claude-sonnet-5-5"   # capable model drives the browser
evaluator_model = "claude-haiku-5-5"    # cheaper model judges each step
max_attempts    = 2                       # per step, then stop
mcp_endpoint    = "stdio://@playwright/mcp"
max_parallel    = 2                       # fits a 2-CPU Codespace
```

Keep models swappable behind an interface — the reasoning model, the browser
driver, and (later) the serving runtime are all replaceable.

---

## The execution loop (PRD §6)

For each step, in order:

1. Hand the step text to the **executor**; it acts via Browser-MCP, interpreting
   intent, not a selector.
2. Evaluate the result: **pass** → record, advance. **fail** → the **evaluator**
   decides `retry` or `stop`.
3. At most **2 attempts** per step, then stop.
4. First *real* failure ends the scenario; remaining steps → `SKIPPED`.

The evaluator separates genuine defects from recoverable execution issues:

| Class | Meaning | Behaviour |
| --- | --- | --- |
| **defect** | The app is genuinely wrong | Not retried — this is the bug you wanted |
| **execution** | Transient (slow load, momentary miss) | Retried, up to the attempt limit |
| **infrastructure** | Environment broken (browser won't start) | Run marked **blocked**, not failed |

---

## Data & assertion handling (critical — PRD §7)

How a `Then` step is judged is **mechanical**:

- A `Then` carrying concrete data — a data table, a double-quoted value, a
  standalone number, or a text block — is checked **in code**.
- Any other `Then` is judged by the **evaluator model**.
- At a data assertion, the model's only job is to **locate/extract** on-screen
  values via the browser tool. The **comparison happens in Python**.
- Gherkin data tables are parsed and matched **cell by cell**. A cell written as
  `<name>` (e.g. `<ref>`) matches **any non-empty value** (dynamic data like a
  generated reference); a literal like `272.00` is matched **exactly**.

---

## Artifacts & reporting (PRD §8)

Every run streams evidence to disk (memory-aware). Per step and per scenario:
`step_status` (`PASSED`/`FAILED`/`SKIPPED` + attempt count/`RETRIED`), `trace`
(tool calls/actions), `tokens` (prompt, completion, cached, reasoning),
`screenshots`, and `report.json`. A **suite summary** aggregates per-feature
reports for CI. Treat **token accounting as a quality signal**, not just a cost
line — where tokens go tracks the health of a run.

Artifacts are generated output: they live under `artifacts/` and are
git-ignored, never committed.

---

## Testing & quality bar

- **Unit tests are the core deliverable**, not an afterthought. Cover: the step
  parser; the assertion engine (**exact numeric match, no rounding**); the loop
  controller (retry cap, fail-fast, skip). **Mock the MCP client and the agents**
  so the deterministic core is tested without a live browser or model.
- Keep the **architecture test** green: no selectors above the browser client.
- Prefer deterministic, fast tests. Anything that needs a real browser or a real
  model API key is an integration test, gated separately — not part of
  `make test`.
- Run `make check` before declaring work done; report failures honestly with the
  output rather than hiding them.

---

## Codespaces constraints (apply to every phase — PRD §1)

- Standard **2-CPU** container (~8 GB RAM, Linux). Design for it.
- Concurrency ≤ 2: cap the CI matrix at 2 parallel jobs; one browser context at a
  time inside a job. Favor sequential, resumable work over wide fan-out.
- Headless browser only; its OS deps come from the bootstrap script.
- Memory-aware: write artifacts to disk and stream; don't hold a whole run in
  memory. Move a heavy nightly suite to a larger runner when it outgrows the box.

---

## Build order & current status

Current status: **foundation module implemented and green under `make ci`**
(ruff, import-linter, mypy `--strict`, and the unit suite all pass without a live
browser or model). PRD §14 steps 1–10 and 12 are done; **step 11 (the CI
workflow) is not yet added** — add `.github/workflows/` with a feature-discovery
matrix capped at 2 parallel jobs plus a suite-summary job when you pick it up.

When extending, keep to PRD §14 order and don't build ahead of it. Later phases:
wrap pieces as tools → put a reasoning agent in front → tune the harness → move
specialists behind the A2A contract + a registry → serve (only if self-hosting
the model; otherwise stay on the Claude Platform API).

Prior art and related work worth reading: the reference implementation
[agentic_e2e-testing](https://github.com/Dima806/agentic_e2e-testing), and, for
the "is the evaluator trustworthy?" question, [llm_judge_benchmark](https://github.com/Dima806/llm_judge_benchmark).
The README lists more of @Dima806's related projects.

### Confirmation gate

The agent prepares and runs work; a **human confirms the verdict**. Anything that
opens a defect, changes a scenario, or spends real compute gets confirmed by
default. This is not full autonomy — keep the checkpoint.

---

## Conventions

- Python ≥ 3.11, `src/` layout, package import name `aqp`, distribution name
  `agentic-quality-platform`.
- Format and lint with **ruff**; type-check with **mypy**. Match the style of
  surrounding code.
- Config via `src/aqp/config.py` (env + `aqp.toml`); never hard-code model IDs,
  limits, or the MCP endpoint — they are configuration.
- Keep deterministic code free of model calls; keep the two agent modules the
  only places that import the Claude SDK.
