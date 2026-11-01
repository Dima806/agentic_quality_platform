# agentic_quality_platform

An agentic quality platform that runs plain-language Gherkin feature files as
live browser tests — **no step definitions, page objects, selectors, or waits**.
The feature file *is* the whole test.

A reasoning model reads **intent**; deterministic Python holds the **data and the
assertions**; a human reviews the **evidence**. That split runs through the whole
system.

> Built for a standard 2-CPU GitHub Codespace. The foundation module (the test
> runner) is implemented and green under `make ci`; it grows into an
> orchestrating platform from there. See [`.llm/PRD_agentic_quality_platform.md`](.llm/PRD_agentic_quality_platform.md)
> for the full product spec and [CLAUDE.md](CLAUDE.md) for contributor guidance.

## The core idea

A feature describes intent, not implementation. There are no step definitions
behind it — a reasoning model interprets each step against a live browser through
a browser-automation MCP server, and deterministic code checks the data.

```gherkin
Feature: Refund flow

  Scenario: Customer requests a refund for a delivered order
    Given a user is on the orders page
    When the user opens their most recent delivered order
    And the user hovers over the order, finds the refund control, clicks it to open the refund page
    Then the refund page should be visible
    When the user submits the refund with reason "Damaged on arrival"
    Then the confirmation page should be visible
    Then the results table should be shown with the following values
      | Status      | Order | Reference | Amount |
      | Successful  | <id>  | <ref>     | 272.00 |
```

How each step is judged is mechanical: a `Then` carrying concrete data (a table,
a quoted value, a number) is checked **in code**, exact-match — `272.00` never
becomes `272` or `272.0`. A `<name>` placeholder matches any non-empty value, so
dynamic data like a generated reference number still passes. Every other `Then`
is judged by the evaluator model.

## How it works

```
.feature  →  validate   →  parse   →  ┌─ PER-STEP LOOP (the only agentic part) ─┐  →  artifacts
(Gherkin)    (pytest-bdd)  (steps)     │  executor (acts)                         │     step_status
                                       │  evaluator (judges)   ⇄   Browser-MCP    │     trace · tokens
                                       │  assertion engine (compares in code)     │     screenshots
                                       └──────────────────────────────────────────┘     report.json
```

Everything outside the dashed box is deterministic Python. The executor and
evaluator are the only parts that call a model (the Claude Platform API). The
per-step loop retries at most twice, fails fast on the first real defect, and
records every remaining step as `SKIPPED`. Only the browser client talks to the
MCP server, and no selector ever appears above it.

## Quickstart

```bash
make setup                               # provision a fresh Codespace (Node, Playwright MCP, Python deps)
export ANTHROPIC_API_KEY=sk-...          # the executor/evaluator run on the Claude Platform API

aqp run features/refund.feature          # run a feature (or a directory of them)
aqp run --collect-only features/         # validate & parse only — no browser or model
make ci                                  # lint + typecheck + unit tests (no browser or model needed)
```

Runs stream evidence to `artifacts/<feature>/<scenario>/`: per-step status, a
trace, token accounting, screenshots, and a machine-readable `report.json`.

## Status

- **Foundation module — done.** Feature loader/validator, step parser,
  browser-MCP client, executor + evaluator agents, the deterministic assertion
  engine, loop controller, artifact writer, and suite summary, with a CLI and a
  unit suite (parser, assertion engine, loop controller, architecture boundary).
- **Ahead:** wrap the pieces as tools → put a reasoning agent in front → tune the
  harness → move specialists behind an A2A contract → serve (only if
  self-hosting). See the PRD's rollout phases.

## Related projects

Other work by [@Dima806](https://github.com/Dima806) that this platform draws on
or complements:

**Agentic systems**
- [agentic_e2e-testing](https://github.com/Dima806/agentic_e2e-testing) — the reference implementation this foundation module draws its patterns from: Gherkin features run as live browser tests by a reasoning model.
- [energy_grid_research_agent](https://github.com/Dima806/energy_grid_research_agent) — a multi-framework agentic RAG system for industrial technical-document analysis.
- [financial_research_agent](https://github.com/Dima806/financial_research_agent) — a LangGraph-based multi-agent deep-research system for financial documents.

**Evaluation & quality**
- [llm_judge_benchmark](https://github.com/Dima806/llm_judge_benchmark) — local LLM judges compared against human annotation on the same RAG answers; the "is the evaluator trustworthy?" question, measured.
- [model_drift_detector](https://github.com/Dima806/model_drift_detector) — a drift detector for ML models in production.

**Retrieval & RAG** (the shape of a future coverage/retrieval tool)
- [graphrag_vs_vectorrag](https://github.com/Dima806/graphrag_vs_vectorrag) — a side-by-side comparison of Graph RAG and Vector RAG.
- [retrieval_arena](https://github.com/Dima806/retrieval_arena) — a head-to-head of retrieval strategies (TF-IDF, BM25, dense bi-encoders, hybrid fusion, cross-encoder reranking).
- [rag_101](https://github.com/Dima806/rag_101) — RAG end to end on CPU with tiny local models: chunk, embed, retrieve, generate.

## License

See [LICENSE](LICENSE).
