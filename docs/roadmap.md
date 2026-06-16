# Implementation Roadmap (`docs/roadmap.md`)

This document lays out the milestones and tasks to implement the new agentic architecture for the Biotech Analyst CLI (`ba`).

---

## Phase 1: Structure & Orchestration Setup
- [ ] Move `bdscan` and `deepdive` pipeline execution logic out of [main.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/cli/main.py).
- [ ] Create orchestrators [bdscan_orchestrator.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/core/bdscan_orchestrator.py) and [deepdive_orchestrator.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/core/deepdive_orchestrator.py) under `src/core/`.
- [ ] Create the agent directories `src/agents/bdscan_agents/` and `src/agents/deepdive_agents/` to house individual agent implementations.
- [ ] Implement the LLM Client interfaces for multi-model queries in [llm_client.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/services/llm_client.py) (Gemini, OpenRouter, and DeepSeek).
- [ ] Set up the global [learning.md](file:///f:/AIML%20projects/biotech-analyst-cli/learning.md) template file in the root directory.

---

## Phase 2: Agent Implementations
- [ ] **Context Agent (`context_agent.py`):**
  - Implement a 1-turn generation logic to write short, science-focused `context.md` files (shorter than the legacy `asset-pipeline-research` version to avoid downstream context bloating).
- [ ] **Database Search Agent (`db_search_agent.py`):**
  - Refactor registry querying utilities under `src/utils/` (like ClinicalTrials, ANZCTR, PubChem, openFDA, CDE scraper, etc.) into reusable tools.
  - Implement a flexible 4-turn state search loop sequentially for the eight databases. Rather than rigid turn boundaries, allow the agent to review results, dynamically generate new search terms/queries, and paginate, ending with a finalization step.
  - Implement a deterministic append/de-duplicate utility script to compile raw registry data into source tables, ensuring 100% data integrity with no LLM rewriting of trial data.
- [ ] **Landscape Table Compiler (`compile_landscape.py`):**
  - Create the consolidation utility to merge the 8 source-specific tables into a single master landscape table under `research/` (one unique asset per row, merging targets, sponsors, indications, trials, formulations).
- [ ] **Asset Research Agent (`asset_research_agent.py`):**
  - Implement the 4-turn row-specific web research loop.
  - Implement `web_search` and `edit_landscape_table` tools.
  - Ensure the agent writes web research outputs into *new* columns in the master table, keeping the database-fetched columns immutable to prevent hallucination.
  - Focus alternative name and laboratory code queries on resolving partner/sponsor codes for the same asset.
  - Design the loop to track alternative names discovered so that duplicate assets/rows in the table are marked to avoid redundant web search effort.
- [ ] **Final Synthesis Agent (`synthesis_agent.py`):**
  - Implement the 10-turn report drafting logic.
  - Reference sample output formats in `asset-pipeline-research/output/`.
  - Ensure the strategic markdown report is separate from the summarized table output to avoid PDF page-splitting/formatting issues.

---

## Phase 3: Curator Agent & Curation Loop
- [ ] **Curator Agent (`curator_agent.py`):**
  - Implement stage-end logic to ingest execution logs from `db_search_agent` and `asset_research_agent`.
  - Update sections `## database-search` and `## web-search` inside the global [learning.md](file:///f:/AIML%20projects/biotech-analyst-cli/learning.md) file (limiting each section to 20 lines max).

---

## Phase 4: CLI Command Routing & End-to-End Validation
- [ ] Update `ba bdscan` and `ba deepdive` commands in [main.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/cli/main.py) to route execution through `src/core/bdscan_orchestrator.py` and `src/core/deepdive_orchestrator.py`.
- [ ] Write integration test cases to execute and verify the multi-agent execution pipeline.
- [ ] Run the end-to-end pipeline and verify generated output tables, reports, and compiled PDFs.
- [ ] Audit output quality using `validate_report.py`.
- [ ] Update [AGENTS.md](file:///f:/AIML%20projects/biotech-analyst-cli/AGENTS.md) with files and new documentation links.
