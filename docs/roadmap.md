# Implementation Roadmap (`docs/roadmap.md`)

This document lays out the milestones and tasks to implement the new agentic architecture for the Biotech Analyst CLI (`ba`).

---

## Phase 1: File Structure & Core Utilities Setup
- [ ] Create the agent directory `src/agents/bdscan/`.
- [ ] Implement the LLM Client interfaces for multi-model queries in [src/services/llm_client.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/services/llm_client.py) (Gemini, OpenRouter, and DeepSeek).
- [ ] Set up the global `learning.md` template file in the root directory.

---

## Phase 2: Agent Implementations
- [ ] **Context Agent (`context_agent.py`):**
  - Implement a 1-turn generation logic to write short, science-focused `context.md` files.
- [ ] **Database Search Agent (`db_search_agent.py`):**
  - Implement the 4-turn state search loops (Query formulation -> Run & review -> Paginate & adapt -> Finalize).
  - Write helper scripts to format query returns and execute append/de-duplicate logic for raw trials.
- [ ] **Landscape Table Compiler (`compile_landscape.py`):**
  - Create the consolidation utility combining the source tables into a master table under `research/`.
- [ ] **Asset Research Agent (`asset_research_agent.py`):**
  - Implement the 4-turn row-specific research loop.
  - Implement web search integrations and row editing tools to mutate cells in the master landscape table.
- [ ] **Final Synthesis Agent (`synthesis_agent.py`):**
  - Implement the 10-turn report drafting logic.
  - Separate report narrative generation from table generation to ensure clean PDF compilation.

---

## Phase 3: Curator Agent & Curation Loop
- [ ] **Curator Agent (`curator_agent.py`):**
  - Implement logic to ingest execution logs from `db_search_agent` and `asset_research_agent`.
  - Update sections `## database-search` and `## web-search` inside the global `learning.md` file.

---

## Phase 4: CLI Command Routing & End-to-End Validation
- [ ] Update `ba bdscan` commands in [src/cli/main.py](file:///f:/AIML%20projects/biotech-analyst-cli/src/cli/main.py) to route execution through `src/agents/bdscan/orchestrator.py` instead of the old subprocess runner.
- [ ] Write integration test cases to execute and verify the multi-agent execution pipeline.
- [ ] Run the end-to-end pipeline and verify generated output tables, reports, and compiled PDFs.
- [ ] Audit output quality using `validate_report.py`.
- [ ] Update [AGENTS.md](file:///f:/AIML%20projects/biotech-analyst-cli/AGENTS.md) with files and new documentation links.
