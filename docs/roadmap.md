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

## Phase 10: Robustness, Performance Tuning, & Architecture Alignment

- [x] **Scan Directory Isolation:** Ensure search outputs and JSON results are correctly routed to the active scan directory rather than lingering in temporary folders.
- [x] **Registry Scrapers & Coverage Expansion:** Verify CDE (Center for Drug Evaluation) direct scraping with Playwright, and increase results limit for ClinicalTrials.gov query tool from 50 to 200 records.
- [x] **Dynamic Agent Learning Integration:** Expand `learning.md` injection into agent prompting contexts, empowering both Database Search and Web Research agents to leverage historical learning iterations when dynamically choosing tools.
- [x] **LLM Client Resilience & Scaling:** Configure read timeout options specifically for the streaming HTTP client in [llm_client.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/services/llm_client.py) (using `httpx.Timeout(60.0, connect=10.0)`) to mitigate connection drops and timeout issues during peak API server loads.
- [x] **Prompt and Batch Size Optimization:** Reduce the batch size of parallel assets queried inside orchestrators to decrease prompt size, improve latency, and avoid load-related LLM failures.
- [x] **Concurrency & Interleaved Logging:** Implement parallel batch execution in `classify_interventions()`, support worker pools and jitter in `LLMClient`, and buffer console outputs to keep logs clean and readable.
- [x] **Agent Refactoring:** Move `classify_interventions` to live as an independent agent under `src/agents/bdscan_agents/`.
- [x] **Deep-Dive Diligence Stub:** Set up the `deepdive` pipeline runner to correctly render as under construction pending detailed implementation specifications.

---

## Next Steps / Bugs

- [x] Looking at "C:\Users\tiger\Desktop\AI_Native_2026\20260616_Claudin_18_2_Scan\final_output\meta_analysis_Claudin_18_2_table_20260616.md", everything just says web search pending despite 110 web searches being completed. I suspect the web search agent does not have a reminder that it's on the final turn and needs to finalize. In fact, every agent needs this final turn reminder.
- [x] **synonym/duplicate resolution**: Resolve duplicate rows (e.g. `IBI343` combos, `IMC002` Chinese suffixes/descriptions) by updating `intervention_classifier_agent.py` prompts to classify combination regimens and parentheticals under core base canonical names, and penalizing messy/long names in `_name_priority` (`table_formatters.py`) to keep canonical keys clean.
- [x] **Fix LLM repetition/attention loops during web search query generation in `AssetResearchAgent`**:
  - [x] Add a query string length cap and sanitization in `AssetResearchAgent` to prevent repeating or runaway generated queries from breaking DuckDuckGo searches.
  - [x] Update `LLMClient` (`src/services/llm_client.py`) to support custom `generationConfig` parameters like `temperature` (frequency/presence penalties were removed for all providers because they are not supported by Gemini developer API models and triggered HTTP 400 errors).
  - [x] Streamline and consolidate the `## web-search` instructions in `learning.md` to prevent prompt inflation and instruction conflict.

## Future Ideas

- [ ] **Phase 11: Agentic Deep-Dive Diligence Pipeline**
  - Transition the `deepdive` pipeline from the current sequential subprocess-based implementation to a fully agentic workflow in `src/agents/deepdive_agents/`.
  - Implement a multi-turn deep-dive analyst agent to cross-examine and summarize ClinicalTrials records, PubChem bioassays, and openFDA label text into a structured, publication-ready SWOT analysis and investment memo.
  - Design interactive post-report chat interfaces, allowing users to dynamically probe the agent with follow-up clinical or preclinical questions on the parsed deep-dive assets.
- [ ] **Quality Audit & Verification Expansion**
  - Enhance the [validate_report.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/utils/validate_report.py) script to audit the output PDF files directly (converting PDF back to text) to ensure no target assets or regulatory IDs were truncated or dropped during layout pagination.
  - Implement an automated report diffing tool to compare newly synthesized markdown reports against historic baselines, highlighting differences in clinical efficacy figures or timeline forecasts.
- [ ] **Registry Tool Coverage Expansion**
  - Add new registry fetchers under `src/tools/` for additional regions and data sources (e.g., Japan's PMDA clinical trial registry, Health Canada clinical trials search, or WHO International Clinical Trials Registry Platform (ICTRP) direct API calls).
  - Integrate structured academic literature searching (e.g., PubMed/EuropePMC citation parsing) directly into the Database Search agent workflow to automatically extract early-stage conference abstracts (ASCO, AACR, ESMO) mentioning the asset.
- [ ] **LLM Performance & Multi-Key Load Balancing**
  - Implement support for multi-provider API keys and automatic key rotation within `LLMQueueManager` to overcome rate limit bottlenecks when executing highly concurrent agent queries.
  - Investigate local/open-source model options (e.g., Llama-3 or Mistral variants via Ollama or local vLLM instances) as secondary query providers for routine name sanitization tasks to decrease API latency and cost.
