# Implementation Roadmap (`docs/roadmap.md`)

This document lays out the milestones and tasks to implement the new agentic architecture for the Biotech Analyst CLI (`ba`).

---

## Phase 1: Structure & Orchestration Setup

- [x] Move `bdscan` and `deepdive` pipeline execution logic out of [main.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/cli/main.py).
- [x] Create orchestrators [bdscan_orchestrator.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/core/bdscan_orchestrator.py) and [deepdive_orchestrator.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/core/deepdive_orchestrator.py) under `src/core/`.
- [x] Create the agent directories `src/agents/bdscan_agents/` and `src/agents/deepdive_agents/` to house individual agent implementations.
- [x] Implement the LLM Client interfaces for multi-model queries in [llm_client.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/services/llm_client.py) (Gemini, OpenRouter, and DeepSeek).
- [x] Set up the global [learning.md](file:///f:/AIML%20projects/biotech-analyst-cli/src/agents/learning.md) template file in the agents directory.

---

## Phase 2: Agent Implementations

- [x] **Context Agent (`context_agent.py`):**
  - Implement a 1-turn generation logic to write short, science-focused `context.md` files (shorter than the legacy `asset-pipeline-research` version to avoid downstream context bloating).
- [x] **Database Search Agent (`db_search_agent.py`):**
  - Refactor registry querying utilities under `src/utils/` (like ClinicalTrials, ANZCTR, PubChem, openFDA, CDE scraper, etc.) into reusable tools.
  - Implement a flexible 4-turn state search loop sequentially for the eight databases. Rather than rigid turn boundaries, allow the agent to review results, dynamically generate new search terms/queries, and paginate, ending with a finalization step.
  - Implement a deterministic append/de-duplicate utility script to compile raw registry data into source tables, ensuring 100% data integrity with no LLM rewriting of trial data.
- [x] **Landscape Compiler Agent (`landscape_compiler_agent.py`):**
  - Create the consolidation utility to merge the 8 source-specific tables into a single master landscape table under `research/` (one unique asset per row, merging targets, sponsors, indications, trials, formulations).
- [x] **Asset Research Agent (`asset_research_agent.py`):**
  - Implement the 4-turn row-specific web research loop.
  - Implement `web_search` and `edit_landscape_table` tools.
  - Ensure the agent writes web research outputs into _new_ columns in the master table, keeping the database-fetched columns immutable to prevent hallucination.
  - Focus alternative name and laboratory code queries on resolving partner/sponsor codes for the same asset.
  - Design the loop to track alternative names discovered so that duplicate assets/rows in the table are marked to avoid redundant web search effort.
- [x] **Final Synthesis Agent (`synthesis_agent.py`):**
  - Implement the 10-turn report drafting logic.
  - Reference sample output formats in `asset-pipeline-research/output/`.
  - Ensure the strategic markdown report is separate from the summarized table output to avoid PDF page-splitting/formatting issues.

---

## Phase 3: Curator Agent & Curation Loop

- [x] **Curator Agent (`curator_agent.py`):**
  - Implement stage-end logic to ingest execution logs from `db_search_agent` and `asset_research_agent`.
  - Update sections `## database-search` and `## web-search` inside the global [learning.md](file:///f:/AIML%20projects/biotech-analyst-cli/src/agents/learning.md) file (limiting each section to 20 lines max).

---

## Phase 4: CLI Command Routing & End-to-End Validation

- [x] Update `ba bdscan` and `ba deepdive` commands in [main.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/cli/main.py) to route execution through `src/core/bdscan_orchestrator.py` and `src/core/deepdive_orchestrator.py`.
- [x] Write integration test cases to execute and verify the multi-agent execution pipeline.
- [x] Run the end-to-end pipeline and verify generated output tables, reports, and compiled PDFs.
- [x] Audit output quality using `validate_report.py`.
- [x] Update [AGENTS.md](file:///f:/AIML%20projects/biotech-analyst-cli/AGENTS.md) with files and new documentation links.
- [x] Enhance `ba config` to allow interactive LLM provider selection (`gemini`, `openrouter`, `deepseek`), specific model configuration typing, and secure retention of other provider credentials/preferences in `.env`.

---

## Phase 5: Reliability & Queue Management

- [x] **LLM Client Queue:** Implement a thread-safe sequential FIFO queue manager in `LLMClient` to process all LLM requests one by one, eliminating race conditions.
- [x] **Dual-Level Retry & Backoff:**
  - Implement connection-level retries (on `httpx.RequestError` timeouts or drops) up to 3 times with exponential backoff (1s base, 2x multiplier).
  - Implement LLM-level retries (on transient `httpx.HTTPStatusError` codes `429`, `500`, `502`, `503`, `504`) up to 5 times with exponential backoff (2s base, 2x multiplier).
  - Ensure immediate termination on fatal client errors (e.g. 401 Unauthorized).
- [x] **Pytest Mock Compatibility:** Establish a synchronous bypass/fallback mode using a lock when running in `pytest` to prevent scoping or timeout issues with test mocks.
- [x] **Comprehensive Testing:** Add config and client-level test cases in `test_config.py` verifying retry sequences, queue processing order, and immediate fail behaviors.

---

## Phase 6: Code Quality, Windows Compatibility & Directory Restructuring

- [x] **Strict Error Policy (No Fallbacks):** Remove automatic fallbacks in `context_agent` so execution terminates loudly upon failure.
- [x] **Windows Encoding Fix:** Resolve Chinese search `UnicodeDecodeError` in Windows reader thread by forcing UTF-8 and replacement handling.
- [x] **Curator Isolation:** Remove duplicate learning update helpers across all agents; isolate learning edits strictly to `curator_agent.py`.
- [x] **Agent Tools Segregation:** Reorganize folder layout: move programmatic database query fetchers/summarizers into `src/tools/` acting as the agent tools registry, and keep `src/utils/` for helper modules (like PDF, table formats, CLI speech bubble).
- [x] **Text Table Formatting:** Format the competitive matrix and landscape output files with text Unicode box-drawers and `#` row numbering.

---

## Phase 7: Data Integrity & Broad Scan Refactoring

- [x] **Synonym and Registry Audit:** Confirm the search logic across all 8 registries and ensure de-duplicated registry tables are cleanly consolidated without text deletion.
- [x] **Synonym Grouping and Merging:** Ensure multi-source assets representing the same molecule under different synonyms are successfully merged in the master table.
- [x] **Web Search Column Cleanup:** Sync columns populated by the Web Search agent with standard landscape columns (e.g. Selectivity, Key Efficacy, Upcoming Milestones) and drop redundant columns.
- [x] **Asset Name AI Classification:** Prevent general modality terms (like `HER2` or `immunotherapy`) from sneaking into individual asset names by leveraging AI-based classification over brittle heuristic blocklists.
- [x] **LLM Client Key Errors Resolution:** Track down and fix Gemini/DeepSeek routing errors (e.g. 400 invalid API key) where active provider configuration was mismatched in `learning.md`.
- [x] **Broad Scan Refactoring Spec:** Create comprehensive architectural design specifications and plans in `docs/bdscan_refactor.md` for reconciliation mapper, synonym extractor, modular landscape compile, and concurrency.

---

## Phase 8: Advanced Config Capabilities & Portable Settings

- [x] **Portable Configuration:** Save settings path strings generically (using `~` for user desktop directory) to prevent exposing local machine-specific home folders in `.env`.
- [x] **Active Settings CLI Inspection (`ba config show`):** Implement subcommand to display all settings profiles and masked API credentials.
- [x] **LLM Settings Dynamic Control (`ba config llm`):** Implement subcommand to switch LLM provider and model, dynamically prompting for missing keys while maintaining non-interactive argument usage.

---

## Phase 9: Broad Scan Pipeline Refactoring

- [x] **Landscape Monolith Decomposition:** Deconstruct `generate_landscape_table.py` monolith into modular submodules under `src/utils/landscape/` (`table_formatters.py`, `config_builder.py`, `table_builder.py`, `exporters.py`), and migrate LLM classifier to `src/tools/classify_interventions.py`.
- [x] **Database Result Reconciliation:** Implement the Reconciliation Mapper (`src/utils/landscape/reconciliation.py`) to map and merge 8 database outputs into a unified `reconciled.json` layout, using LLM-primary matching.
- [x] **LLM-Based Alias Resolution:** Extend `classify_interventions()` to support structured synonyms, modalities, and targets JSON output. Implement a zero-hallucination synonym provenance verification.
- [x] **Pipeline Concurrency:** Speed up registry querying (8 concurrent workers) and qualitative web research (4 concurrent workers) using `ThreadPoolExecutor`. Implement a thread-safe registry lock (`_registry_lock`) to skip redundant web searches.

---

## Next Steps

- [x] It looks like all the json files and database search outputs are still being dumped in the tmp folder instead of the actual scan folder.
- [ ] Complete manual developer testing of the concurrent database searches and lock-protected asset research.
- [ ] Delete the temporary refactoring specification file `docs/bdscan_refactor.md`.
