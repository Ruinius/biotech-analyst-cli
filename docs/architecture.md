# System Architecture (`docs/architecture.md`)

This document outlines the high-level architecture, directory layouts, and data flow pipelines of the Biotech Analyst CLI (`ba`).

---

## 1. High-Level Architecture

The Biotech Analyst CLI is structured to combine deterministic, zero-hallucination data compilation scripts with an LLM-powered multi-agent pipeline for due diligence context mapping and report synthesis.

```mermaid
graph TD
    CLI[CLI Entrypoint: Typer] --> config[Config Wizard]
    CLI --> folder[Folder Browser]
    CLI --> bdscan[BD Scan Orchestrator]
    CLI --> deepdive[Deep-Dive Pipeline]

    bdscan --> Agents[Agent Pipeline: context, db_search, asset_research, synthesis]
    deepdive --> fetch[Subprocess Sourcing Utilities]

    fetch --> Registry[ClinicalTrials.gov, CDE Scraper, PubChem, openFDA]
    Agents --> Registry

    Agents --> Curator[Curator Agent]
    Curator --> GlobalLearning[Global learning.md in Root]

    Agents --> PDF[Markdown-to-PDF Compiler]
    deepdive --> PDF
```

---

## 2. Directory Structure

```
biotech-analyst-cli/
├── docs/                           # Project documentation and specifications
│   ├── architecture.md
│   ├── cli_spec.md
│   ├── bdscan_spec.md
│   └── roadmap.md
├── tmp/                            # Temporary raw records, databases, and tables
├── src/                            # Core application package
│   ├── cli/                        # CLI Commands definition
│   │   └── main.py                 # Command router and main execution loop
│   ├── core/                       # Shared configurations and exceptions
│   │   ├── config.py               # Pydantic configuration loaded from .env
│   │   └── exceptions.py           # Custom exception definitions
│   ├── services/                   # Unified API services
│   │   └── llm_client.py           # Gemini, OpenRouter, and DeepSeek client
│   ├── agents/                     # Multi-Agent workflows
│   │   └── bdscan/                 # Pathway Broad Scan agent directory
│   │       ├── orchestrator.py     # Sequencer for the BD Scan agents
│   │       ├── context_agent.py    # 1-turn scientific context compiler
│   │       ├── db_search_agent.py  # 4-turn database search coordinator
│   │       ├── compile_landscape.py# Script consolidating database outputs
│   │       ├── asset_research_agent.py # 4-turn row-specific web researcher
│   │       ├── synthesis_agent.py  # 10-turn executive report synthesizer
│   │       └── curator_agent.py    # Stage-end compiler of global learnings
│   ├── utils/                      # Programmatic fetchers and parsers
│   │   ├── formatting.py           # Dr. Hops speech bubbles and Rich console
│   │   ├── parse_pdf.py            # PDF text and table extractor
│   │   ├── fetch_clinicaltrials.py # ClinicalTrials.gov query API
│   │   ├── fetch_anzctr_ctis.py    # ANZCTR & EU CTIS search API
│   │   ├── fetch_conferences.py    # ASCO/AACR abstract scraper
│   │   ├── fetch_chinese_registries.py # WHO ICTRP & ChiCTR search client
│   │   ├── fetch_china_direct.py   # Playwright scraper for NMPA CDE
│   │   ├── fetch_ip_lens.py        # Patent search API client
│   │   ├── fetch_pubchem.py        # PubChem Compound search client
│   │   ├── fetch_openfda.py        # FDA safety labeling API client
│   │   ├── generate_landscape_table.py # Script building competitive matrix
│   │   ├── validate_report.py      # Validator checking IDs against raw logs
│   │   └── convert_md_to_pdf.py    # Paginated PDF compiler
│   └── main.py                     # Entry point routing to src/cli/main.py
├── pyproject.toml                  # Python package configuration (uv managed)
├── uv.lock                         # Lockfile for python packages
├── learning.md                     # Global pipeline learnings and lessons
└── AGENTS.md                       # Project index and architectural constraints
```

---

## 3. Data Pipelines Flow

1. **Configuration (`ba config`):** Wizard that creates/saves name, email, research folder target, and LLM API keys directly to `.env` in the current folder.
2. **Interactive Folder Navigator (`ba folder`):** Interactive listing of research folders enabling users to browse and open directories in Windows Explorer.
3. **Pathway Scan (`ba bdscan`):** Runs the agent-based scanner to construct context files, query databases in multiple languages, compile competitive matrices, conduct web searches, validate results, and generate paginated PDFs.
4. **Diligence Deep-dive (`ba deepdive`):** Queries registries, openFDA, and PubChem for a single asset, logs results to markdown files, and compiles a comprehensive due diligence memo.
