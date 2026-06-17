# Specification: Agentic BD Scan Pipeline (`docs/bdscan_spec.md`)

This specification details the architecture, agent configurations, and data structures for the `ba bdscan` pipeline. The pipeline combines parallel database fetching, an LLM-based reconciliation and alias resolution engine, modular table formatters, and concurrent web research to build competitive biotech matrices and strategic diligence reports.

---

## 1. Pipeline Architecture & Orchestration

The pipeline is managed by a central **BD Scan Orchestrator** (`src/core/bdscan_orchestrator.py`) which sequences five cooperative agents, the Reconciliation Mapper, and modular formatter submodules.

```mermaid
graph TD
    A[User Input: Pathway/Target] -->|1. Trigger| Orch[BD Scan Orchestrator]
    Orch -->|2. Invoke 1-Turn| Context[Context Agent]
    Context -->|Generates context.md| TargetDir[Research Directory]

    Orch -->|3. Invoke 4-Turn Concurrently| DbSearch[Database Search Agent]
    DbSearch -->|Queries & Saves Raw JSONs| DbJsonDir[database_json/]

    DbJsonDir -->|4. Ingest Logs & Curate| Curator[Curator Agent]
    Curator -->|Updates ##database-search| GlobalLearning[learning.md in src/agents/]

    DbJsonDir -->|5. Run Reconciliation| Mapper[Reconciliation Mapper]
    Mapper -->|Generates reconciled.json & asset_config.json| DbJsonDir

    DbJsonDir -->|6. Direct Imports| Compiler[Landscape Compiler Agent]
    Compiler -->|Calls modular build_landscape_table()| BigTable[landscape_table.md in research/]

    BigTable -->|7. Run 4-Turn Concurrently| AssetResearch[Asset Research Agent]
    AssetResearch -->|Web Search & Edit| BigTable
    AssetResearch -->|Saves Logs| WebLogsDir[web_search/]

    WebLogsDir -->|8. Curate| Curator
    Curator -->|Updates ##web-search| GlobalLearning

    BigTable -->|9. Run 10-Turn| Synthesis[Final Synthesis & Report Agent]
    Synthesis -->|Output Reports| FinalOut[final_output/]
```

---

## 2. Directory Layout & Storage Structure

To prevent polluting the project root's `tmp/` folder, all raw query results, intermediate databases, and configuration settings are saved within the pathways target directory:

| File Type / Purpose                                                          | Location (Post-Refactor)                                                                                            |
| :--------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| **Raw Registry Database Results** (ClinicalTrials, China CDE, PubChem, etc.) | `{target_dir}/database_json/{query}_{source}.json`                                                                  |
| **Reconciled Master JSON** (`reconciled.json`)                               | `{target_dir}/database_json/reconciled.json`                                                                        |
| **Asset Configuration** (`asset_config.json`)                                | `{target_dir}/database_json/asset_config.json` (persisted output of `discover_config()` + synonym discovery)        |
| **Web Research Logs**                                                        | `{target_dir}/web_search/web_research_log_*.md`                                                                     |
| **Compiled Landscape Table**                                                 | `{target_dir}/research/landscape_table.md` & `landscape_table.csv`                                                  |
| **Final Strategic Report & PDF**                                             | `{target_dir}/final_output/`                                                                                        |

_Note: `{target_dir}` is the pathway scan folder initialized in `bdscan_orchestrator.py` (e.g., `outputs/CLDN18.2_Scan/`). The orchestrator initializes `database_json/`, `web_search/`, `research/`, and `final_output/` directories._

---

## 3. Agent Configurations

### Agent 1: Context Agent (`src/agents/bdscan_agents/context_agent.py`)
- **Mode:** One-turn generation agent.
- **Role:** Analyzes the target biological pathway/molecule class.
- **Objective:** Generates a concise scientific grounding document (`context.md`) saved directly under `{target_dir}/research/`.
- **Guidelines:** Keeps notes shorter than the legacy version to prevent LLM context-window bloating for downstream agents.

### Agent 2: Database Search Agent (`src/agents/bdscan_agents/db_search_agent.py`)
- **Mode:** Structured 4-turn loop agent, executed concurrently using a `ThreadPoolExecutor` for the 8 databases.
- **Turn Budget & State Loop:**
  - **Turn 1:** Reads synonyms and target metadata. Formulates search keywords (English/Mandarin). Launches initial queries.
  - **Turn 2:** Reviews raw search outputs, identifies gaps, handles spelling variations, and paginates.
  - **Turn 3:** Runs secondary queries for assets found in other sources or synonyms with sparse data.
  - **Turn 4:** Finalizes queries and triggers migration of raw JSONs to `database_json/`.
- **Error Isolation:** Each worker runs inside its own `try/except` block. Failure in one database does not crash the pipeline. The orchestrator continues if at least two core registries (ClinicalTrials.gov + NMPA CDE Direct) succeed.

### Agent 3: Landscape Compiler Agent (`src/agents/bdscan_agents/landscape_compiler_agent.py`)
- **Objective:** Orchestrates landscape table compilation via direct Python imports from `src/utils/landscape/` and calls `classify_interventions()` from `src/tools/`.
- **Execution:** Calls `build_landscape_table()` from `src/utils/landscape/table_builder.py` directly, passing `reconciled.json` and `asset_config.json`. No subprocess calls.
- **Saves:** Final `landscape_table.md` and `landscape_table.csv` to `{target_dir}/research/`.

### Agent 4: Asset Research Agent (`src/agents/bdscan_agents/asset_research_agent.py`)
- **Mode:** Structured 4-turn loop agent, executed concurrently with a `ThreadPoolExecutor` (max 4 workers).
- **Objective:** Research qualitative clinical metrics (development status, selectivity, key efficacy, milestones) using web search.
- **Concurrency & Deduplication:** Checks a lock-protected registry before researching. If another worker has claimed the asset or its synonyms, skips research and links to the parent row. Writes outputs strictly to new qualitative columns.

### Agent 5: Final Synthesis Agent (`src/agents/bdscan_agents/synthesis_agent.py`)
- **Mode:** 10-turn strategic synthesis agent.
- **Objective:** Generates the final strategically synthesized markdown report and competitive matrix in `final_output/`.
- **Formatting Constraints:** The strategic report markdown must **not** embed the big table inline to avoid page-splitting/formatting bugs in PDF generation.

### Curator Agent (`src/agents/bdscan_agents/curator_agent.py`)
- **Mode:** Stage-end curation agent.
- **Objective:** Gathers logs from search and web research stages and updates the global learning index file `src/agents/learning.md` (max 20 lines per section).

---

## 4. Database Result Reconciliation

The competitive landscape compiles data across 8 supported databases (ClinicalTrials.gov, ChinaDrugTrials, PubChem, openFDA, Lens.org patents, conferences, CTIS/ANZCTR, and Chinese registries) before initiating web research.

### Reconciled JSON Schema
Save the output to `{target_dir}/database_json/reconciled.json`. The top-level structure is keyed by canonical asset names:

```json
{
  "canonical_name": "Zolbetuximab",
  "aliases": ["Vyloy", "IMAB362", "佐妥昔单抗"],
  "sponsors": ["Astellas Pharma", "Ganymed"],
  "modality": "Monoclonal Antibody",
  "lead_indication": "Gastric / GEJ Adenocarcinoma",
  "trials": {
    "clinicaltrials": [
      {
        "id": "NCT03504397",
        "status": "COMPLETED",
        "phase": "PHASE3",
        "title": "SPOTLIGHT Study..."
      }
    ],
    "china_cde": [
      {
        "id": "CTR20182245",
        "status": "进行中",
        "company": "安斯泰来",
        "drug_name": "佐妥昔单抗"
      }
    ],
    "anzctr_ctis": [
      { "id": "ACTRN12617000XXXp", "status": "Recruiting", "title": "..." }
    ],
    "chinese_registries": [
      { "id": "ChiCTR2100042XXX", "status": "招募中", "title": "..." }
    ]
  },
  "patents": [
    {
      "id": "US10450378B2",
      "title": "Antibodies against Claudin 18.2...",
      "assignee": "Ganymed"
    }
  ],
  "conferences": [
    {
      "title": "Zolbetuximab combined with mFOLFOX6...",
      "event": "ASCO 2023",
      "abstract_id": "LBA4002"
    }
  ],
  "pubchem": {
    "cid": 138734994,
    "bioassays": 4
  },
  "openfda": {
    "adverse_events": 124,
    "labels": ["Vyloy FDA approval label text snippet..."]
  }
}
```

### Reconciliation Mapper (`src/utils/landscape/reconciliation.py`)
Mappers extract fields from raw source files and map them structurally. They do not resolve aliases—the LLM performs that matching step.

| Source                 | Mapper Function                                         | Extraction Logic                                                   |
| :--------------------- | :------------------------------------------------------ | :----------------------------------------------------------------- |
| ClinicalTrials.gov     | `map_clinicaltrials(raw_data) -> list[AssetRecord]`     | Interventions names, `otherNames[]`                                |
| ANZCTR / CTIS          | `map_anzctr_ctis(raw_data) -> list[AssetRecord]`        | Titles, cross-reference NCT IDs                                    |
| China CDE              | `map_china_cde(raw_data) -> list[AssetRecord]`          | `drug_name`, `acceptance_number`                                   |
| Chinese WHO Registries | `map_chinese_registries(raw_data) -> list[AssetRecord]` | Title text passed to LLM for name extraction                       |
| Conferences            | `map_conferences(raw_data) -> list[ConferenceRecord]`   | Title text passed to LLM for name extraction                       |
| Lens.org Patents       | `map_patents(raw_data) -> list[PatentRecord]`           | Title, assignee                                                    |
| PubChem                | `map_pubchem(raw_data) -> PubChemRecord`                | CID, bioassays, formula                                            |
| openFDA                | `map_openfda(raw_data) -> OpenFDARecord`                | Adverse events count, label snippets                               |

### Matching Algorithm (LLM-Primary)
1. **Preprocessing (Exact-Dedup):** Case-insensitive exact matches are collapsed to reduce LLM tokens.
2. **LLM-Based Grouping:** Unique names are batched through `classify_interventions()`. The LLM classifies names as `"asset"` or `"background"`, groups synonyms, selects canonical names, and extracts target/modality metadata.
3. **Record Assignment:** Assigns source records to the canonical asset entry. Drops background terms and logs them to `reconciliation_log.json`.
4. **Cross-Language Resolution:** Multi-lingual alias grouping (English ↔ Chinese) is handled natively by the LLM. Shared trial IDs (e.g. CTR linked to NCT) are provided as structural context.

---

## 5. LLM-Based Alias Resolution & Synonyms Extraction

This pipeline replaces heuristic blocklists and regex parenthetical parsing with LLM-based classifications.

### Single Source of Truth
All classification logic resides in **`src/tools/classify_interventions.py`**, which is imported by the Reconciliation Mapper, the Landscape Compiler Agent, and the configuration utilities.

### Extended Schema
`classify_interventions()` returns a structured schema:
```json
{
  "canonical_name": "Zolbetuximab",
  "aliases": ["Vyloy", "IMAB362"],
  "modality": "Monoclonal Antibody",
  "targets": ["CLDN18.2"],
  "filtered_terms": ["Chemotherapy", "HER2", "immunotherapy"]
}
```

### Zero-Hallucination Synonym Validator
1. **Provenance Trace Verification:** Confirms that every alias and canonical name in the LLM output is contained verbatim (case-insensitive) in the original raw fields of the source records. Hallucinated terms are discarded.
2. **LLM-Based Modality/Target Filter:** A secondary validation LLM call reviews the `"asset"` list and filters out modal terms (e.g. `"HER2"`, `"immunotherapy"`, `"chemotherapy"`) that slipped past the primary classifier.
3. **Report Audit:** `validate_report.py` audits the generated `asset_config.json` against the raw JSONs under `database_json/` before proceeding to report synthesis.

---

## 6. Landscape Table Generator Refactoring

The monolithic `generate_landscape_table.py` is modularized under `src/utils/landscape/` and `src/tools/`:

```
src/utils/landscape/
├── __init__.py
├── table_formatters.py    # Pure parsing utilities (phases, sponsors, formulations)
├── config_builder.py      # Asset discovery, synonym grouping, report parsing
├── table_builder.py       # Core table construction loop from raw and reconciled data
├── exporters.py           # Markdown table to CSV and column-aligned text formatters
└── reconciliation.py      # Source registry data mappers and reconciliation logic
```

### CLI Backward-Compatibility
`landscape_compiler_agent.py` uses direct Python imports of `build_landscape_table()` instead of running a subprocess. For external scripts or command-line testing, a thin `__main__.py` entrypoint is provided in `src/utils/landscape/`, exposing the legacy CLI flags:
```powershell
uv run python -m src.utils.landscape --clinicaltrials ... --output ...
```

---

## 7. Pipeline Concurrency

Concurrency is managed using Python's `concurrent.futures.ThreadPoolExecutor` which integrates smoothly with blocking subprocess executions and the sequential thread-safe LLM client queue.

### Concurrency Allocations
- **Database Search Phase:** Parallelized across the 8 sources using `ThreadPoolExecutor(max_workers=8)`.
- **Web Research Phase:** Parallelized across unique assets using `ThreadPoolExecutor(max_workers=4)` (capped at 4 to prevent DuckDuckGo rate limiting).

### Thread-Safe Duplicate Asset Protection
To prevent multiple workers from researching the same asset under different synonyms concurrently:
1. **Registry Lock:** A `threading.Lock` protects `AssetResearchAgent._claimed_assets` (normalized alias ↔ canonical name).
2. **Pre-Research Verification:** A worker acquires the lock, checks if the asset or any of its aliases are claimed, and either registers all aliases (claiming the asset) or skips research and links to the parent row.
3. **Mid-Research Collision Resolution:** If a worker discovers a new alias during its reasoning turns:
   - Acquires the lock.
   - If the new alias is already claimed by another worker, marks the assets for post-research merge.
   - Otherwise, registers the alias.
4. **Post-Research Consolidator:** Consolidates duplicate table rows after all workers complete.
