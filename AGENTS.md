# Agent Documentation and Project Index (AGENTS.md)

This file indexes the workspace structure and defines architectural rules/constraints for AI coding agents.

---

## Project Structure

- `pyproject.toml` & `uv.lock`: Project metadata and locked dependencies.
- `README.md`: Basic usage, installation, and commands.
- `AGENTS.md`: Architectural rules, guidelines, and project index (this file).
  - `docs/`: Technical specifications.
    - `architecture.md`: System design and directory layout.
    - `cli_spec.md`: CLI interface parameters and command behaviors.
    - `bdscan_spec.md`: Multi-agent pipeline design for broad scans.
    - `roadmap.md`: Refactoring milestones and steps.
- `tests/`: Project unit, integration, and command-line test suite.
  - `test_agents.py`: Pipeline and agent integration tests.
  - `test_config.py`: LLM client queue, config manager, and retry tests.
  - `test_query_parser.py`: Regex and LLM-based query parsing tests.
  - `run_tests.py`: Subprocess command-line integration tests for fetchers/summarizers.
  - `test_landscape_modules.py`: Tests for modularized landscape table generation.
  - `test_classify_interventions.py`: Tests for LLM-based intervention classification and alias resolution.
  - `test_reconciliation.py`: Tests for broad scan data reconciliation and mapper logic.
  - `test_concurrency.py`: Tests for thread pool query execution and concurrent web research locking.
- `src/`: Source code package.
  - `cli/main.py`: Command router and main execution loop.
  - `core/`: Config settings and pipeline orchestrators.
    - `config.py`: Settings mapping to `.env` in the root folder.
    - `exceptions.py`: Custom execution exceptions.
    - `bdscan_orchestrator.py` & `deepdive_orchestrator.py`: Multi-agent pipeline orchestrators.
  - `agents/`: AI agents folder (one agent per file).
    - `learning.md`: Shared lessons and guidelines.
    - `bdscan_agents/`: Broad scan agents (`context_agent.py`, `db_search_agent.py`, `landscape_compiler_agent.py`, `asset_research_agent.py`, `curator_agent.py`, `synthesis_agent.py`, `intervention_classifier_agent.py`).
    - `deepdive_agents/`: Deep-dive diligence agents.
  - `services/llm_client.py`: Thread-safe FIFO queue LLM interface (Gemini, OpenRouter, DeepSeek).
  - `tools/`: Programmatic database fetchers and summarizers.
    - `fetch_*.py` & `summarize_*.py`: API/scraping queries for sources (ClinicalTrials, PubChem, openFDA, ANZCTR/CTIS, conferences, Chinese registries, NMPA CDE direct, Lens.org).
  - `utils/`: Data parsing, reporting, and CLI utilities.
    - `generate_landscape_table.py`: Re-export shim for landscape table compilation.
    - `landscape/`: Modular landscape table compilation package.
      - `table_formatters.py`: Constants and parsing utilities.
      - `config_builder.py`: Synonym grouping and configuration discovery.
      - `table_builder.py`: Table construction loop.
      - `exporters.py`: CSV and text formatters.
      - `reconciliation.py`: Multi-source database reconciliation mapper.
    - `validate_report.py`: Integrity and quality gate checks for compiled reports.
    - `convert_md_to_pdf.py`: Paginated PDF compiler.
    - `query_parser.py`: Query processing with local fallbacks.

---

## Architectural Rules for Agents

1. **Execution Environment**:
   - OS: Windows. Shell: PowerShell (`pwsh`).
   - Run Python via `uv run <command>`. Add packages via `uv add <package>`.
   - Playwright requires chromium: run `playwright install chromium` if missing.
   - CLI output formatting must use the 'Dr. Hops' ASCII art speech bubble rendering interface from `src/utils/formatting.py`.
2. **AI Agent Centricity**:
   - Prefer AI agents and LLM calls over heuristics, which are brittle and unreliable. Replace existing heuristics with LLM implementations where appropriate.
   - All AI agents live in `src/agents/`. Design pattern: exactly one agent per file.
3. **LLM Query Client**:
   - All LLM queries must route through `src/services/llm_client.py`.
   - Utilizes thread-safe FIFO queue, connection/LLM retries, and exponential backoff.
   - Never catch errors silently: fail loudly using distinct error prefixes.
4. **No Silent Fallbacks**:
   - Avoid silent fallback strategies (like falling back to another provider or catching exceptions silently). Report errors to the user immediately.
5. **Data Extraction & Tables**:
   - Competitive landscape output in `generate_landscape_table.py` classifies pipeline assets using the batched LLM-based `classify_interventions()`. No hardcoded blocklists.
   - Ensure landscape tables and PDF reports are audited using `validate_report.py` to prevent hallucinated IDs or data omissions.
   - Maintain parameter backward-compatibility with `asset-pipeline-research` across scripts in `src/utils/`.
6. **Testing Standards**:
   - Strictly test-driven. Write unit/integration tests (`tests/test_*.py`) for all additions and changes.
   - Do NOT make real network or LLM API calls in tests. Mock all external dependencies.
7. **Secrets & Linting**:
   - Run code formatting and lint checks using `ruff`.
   - Do not commit secrets. Update/check `.secrets.baseline` using `detect-secrets` if configuring new variables.
