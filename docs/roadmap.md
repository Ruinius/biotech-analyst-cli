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
- [x] **Landscape Table Compiler (`compile_landscape.py`):**
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

Next steps:

- [x] format the landscape and the final output table so that it shows as a table when opened with text (Unicode box-drawing `.txt` + `#` row-number column)
- [x] in the context_agent, kill the fallback. The run should just stop with an error. NO FALLBACKS.
- config needs option to switch LLM provider and models. Maybe call it "ba config llm"
- double check the default config for folder name. I still see address specific to my computer instead of a generic address.
- [x] double check how does db_search_agent actually work. Does it create a table of data that is merged at the end? I see jsons, but I see only clinicaltrials.gov and CDE are merged. What about the others?
- [x] double check that when generating the final output table, that same assets with different names are actually merged. I see a bunch of web search pending right now in the final table.
- [ ] Implement database result reconciliation to merge all 8 database search results (registries, patents, conferences, PubChem, openFDA) into a unified, asset-centric JSON structure.
  - Define a nested JSON schema under `tmp/` (keyed by canonical asset names, containing sub-fields/lists for matching trial records, patents, conference abstracts, PubChem bioassays, and openFDA safety labels).
  - Implement a name/alias reconciliation mapper that scans raw search outputs in `tmp/` and assigns matched records to their respective assets.
  - Run the reconciler in the orchestrator pipeline right after the database search phase finishes.
- [x] other targets, such as HER2 and generic terms such as immunotherapy are sneaking into the "Asset Name" column in the landscape and final output table. Double check if the asset name column is heuristics (which is failing) or AI Agent based. The asset name column should be a molecule name, a brand name, or a codename (e.g., TST001)
- [ ] Eliminate all dynamic cell-parsing alias extraction heuristics. Transition to using an LLM-based agent/parser to dynamically identify, reconcile, and validate canonical assets and their drug synonyms, removing all regex-based string extraction and subsequent heuristic filters.
- the web search agent is creating new columns instead of using existing Selectivity, Key Efficacy, Upcoming Milestones, and Citations columns, leading to them not being used at all. Let's delete these unused columns and just keep the web search agent code intact.
- build concurrency for the database search and web search. Need to be careful that the next step in the pipeline waits for all the previous agents to finish working
- investigate the web-seach error in learning.md. It looks like there's a recurring issue with "valid API key" are there places where the llm_client is trying to call Gemini when it's been set tp deepseek? API Error (HTTP 400): {"error":{"code":400,"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT"}}
- what is "update_learnings" in asset_reserach_agent? Only the curator_agent can update learnings.
- error when searching in Chinese:
  Traceback (most recent call last):
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\threading.py", line 1082, in \_bootstrap_inner
  self.\_context.run(self.run)
  ```^^^^^^^^^^
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\threading.py", line 1024, in run
  self.\_target(*self.\_args, \*\*self.\_kwargs)
  ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\threading.py", line 1082, in \_bootstrap_inner
  self.\_context.run(self.run)
  ~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\subprocess.py", line 1613, in \_readerthread
  buffer.append(fh.read())
  ~~~~~~~^^
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\encodings\cp1252.py", line 23, in decode
  return codecs.charmap_decode(input,self.errors,decoding_table)[0]
  ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 45: character maps to <undefined>
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\threading.py", line 1024, in run
  self.\_target(*self.\_args, \*\*self.\_kwargs)
  ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\subprocess.py", line 1613, in \_readerthread
  buffer.append(fh.read())
  ~~~~~~~^^
  File "C:\Users\tiger\AppData\Roaming\uv\python\cpython-3.14.2-windows-x86_64-none\Lib\encodings\cp1252.py", line 23, in decode
  return codecs.charmap_decode(input,self.errors,decoding_table)[0]
  ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 44: character maps to <undefined>
  ℹ INFO: Turn 4/4 for Chinese WHO Registries...
  ```
