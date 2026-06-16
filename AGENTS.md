# Agent Documentation and Project Index (AGENTS.md)

Welcome to the **Biotech Analyst CLI (`ba`)** project. This file indexes the workspace structure, documents rules, and outlines core architectural constraints.

---

## Project Structure

- `pyproject.toml`: Project metadata, dependencies, and script routing.
- `uv.lock`: Lockfile for python packages.
- `.gitignore`: Git ignored files.
- `README.md`: Basic usage, installation, and commands documentation.
- `AGENTS.md`: Architectural index, guidelines, and rules (this file).
- `.pre-commit-config.yaml`: Configuration file for git pre-commit/pre-push hooks.
- `.secrets.baseline`: Yelps detect-secrets baseline file representing approved false positives.
- `docs/`: Technical specifications and architectural guides.
  - `docs/architecture.md`: System design and directory layout.
  - `docs/cli_spec.md`: CLI interface inputs, parameters, and command behaviors.
  - `docs/bdscan_spec.md`: Agentic architecture design for broad scans.
  - `docs/roadmap.md`: Milestones and steps for pipeline refactoring.
- `main.py`: Entrypoint routing execution to `src/cli/main.py`.
- `src/`: Core source package.
  - `src/cli/`: Command-line interface submodules.
    - `src/cli/main.py`: CLI command router and application main loop.
  - `src/core/`: Configuration and settings.
    - `src/core/config.py`: Settings Pydantic module mapping to `.env` in the current folder.
    - `src/core/exceptions.py`: Custom execution exceptions.
  - `src/services/`: External API services.
    - `src/services/llm_client.py`: Unified interface to Gemini, OpenRouter, and DeepSeek.
  - `src/utils/`: Sourcing utility modules and formatting helpers.
    - `src/utils/formatting.py`: White Rabbit ASCII art renderer and biotech-nerdy speech bubble helper.
    - `src/utils/parse_pdf.py`: Extracting text and tables from publications.
    - `src/utils/fetch_clinicaltrials.py`: clinicaltrials.gov API fetcher.
    - `src/utils/summarize_clinicaltrials.py`: clinicaltrials.gov summarizer.
    - `src/utils/fetch_pubchem.py`: PubChem BioAssay search utility.
    - `src/utils/summarize_pubchem.py`: PubChem BioAssay active assays selectivity summarizer.
    - `src/utils/fetch_openfda.py`: openFDA drug label and safety query utility.
    - `src/utils/summarize_openfda.py`: openFDA drug label safety summarizer.
    - `src/utils/fetch_anzctr_ctis.py`: EU CTIS and ANZCTR trial query utility.
    - `src/utils/summarize_anzctr_ctis.py`: EU CTIS and ANZCTR trial summarizer.
    - `src/utils/fetch_conferences.py`: Conference abstracts search utility (ASCO, AACR, etc.).
    - `src/utils/summarize_conferences.py`: Conference abstracts summarizer.
    - `src/utils/fetch_chinese_registries.py`: Chinese registries & WHO ICTRP search utility.
    - `src/utils/summarize_chinese_registries.py`: Chinese registries & WHO ICTRP trial summarizer.
    - `src/utils/fetch_china_direct.py`: Playwright-based NMPA CDE direct search utility (WAF bypass).
    - `src/utils/summarize_china_direct.py`: NMPA CDE direct search result summarizer.
    - `src/utils/fetch_ip_lens.py`: Lens.org and Dimensions patent/IP search utility.
    - `src/utils/summarize_ip_lens.py`: Lens.org and Dimensions patent/IP result summarizer.
    - `src/utils/generate_landscape_table.py`: Programmatic competitive landscape table compiler.
    - `src/utils/validate_report.py`: Programmatic report audit and quality guardrail validator.
    - `src/utils/convert_md_to_pdf.py`: Paginated Markdown-to-PDF compiler.

---

## Architectural Guidelines

1. **Environment**:
   - Operating System: Windows
   - Terminal: PowerShell (`pwsh`)
   - Tooling: Managed entirely with `uv`. All python execution must use `uv run`.
2. **ASCII Art Interface**:
   - The CLI utilizes ASCII art depicting a white rabbit with glasses ("Dr. Hops").
   - Interactions use speech bubbles containing nerdy biotech-themed remarks.
3. **Registry & Scraper Boundaries**:
   - Scripts in `src/utils` must maintain backward-compatibility with parameters used in `asset-pipeline-research`.
   - Playwright requirements for CDE queries require execution of `playwright install chromium` inside the environment.
4. **Report Validation & Integrity**:
   - Landscape table and final PDF generations are strictly audited using `validate_report.py` to check for hallucinated IDs or data omissions.
5. **Linting & Secret Protection**:
   - Automated code formatting and lint checks are executed via `ruff`.
   - Secret scanning checks are executed via `detect-secrets` against `.secrets.baseline`.
   - Git push triggers these checks automatically if hooks are installed. Run `uv run pre-commit install --hook-type pre-push` to set them up locally.

