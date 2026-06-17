# De-duplication Workflow Refactoring Proposal: Programmatic Clustering and Self-Healing Configuration

This document proposes a refactoring plan for the competitive landscape de-duplication workflow in the Biotech Analyst CLI (`ba`). The current multi-agent reconciliation pipeline is overly complex and slow due to its heavy reliance on multi-stage LLM calls. By drawing inspiration from the efficient design pattern used in the Glioblastoma Multiforme (GBM) market scan, we can shift noise filtering and synonym clustering to local programmatic logic, while keeping the configuration self-creating and self-healing using targeted AI feedback loops.

---

## 1. Problem Statement: Current Over-Engineered Pipeline

In the current `biotech-analyst-cli` repository, resolving synonyms and filtering out background terms is split across several complex LLM-based stages:

```
[Raw Registry Names]
       │
       ▼
[Batched LLM Classification (classify_interventions)]  <-- 15-name batching, multiple calls
       │
       ▼
[Secondary LLM Modality Audit]                         <-- Checks for generic/modality words
       │
       ▼
[Tertiary LLM Global Consolidation]                    <-- Merges duplicate assets globally
       │
       ▼
[Local Synonym Normalization & Mapping]
```

### Systemic Bottlenecks
* **API Latency and Costs**: Running three sequential LLM phases (classification, auditing, global consolidation) across hundreds of scraped registry names results in dozens of API requests per scan. This scales poorly and is slow.
* **Context Bloat**: Feeding unstructured strings and massive token lists into the prompt context increases latency quadratically and causes the model to suffer from "lost-in-the-middle" attention degradation.
* **Brittle Auditing**: Asking the LLM to verify its own drug-name output or to audit generic modalities leads to hallucinations or infinite correction loops when names have minor character differences.
* **Complex Code Maintenance**: Managing worker pools, batching queues, and interleaved logs inside `intervention_classifier_agent.py` creates a high cognitive load for developers and agents.

---

## 2. Inspiration: The GBM Postrun Design Pattern

The Glioblastoma Multiforme market scan (`asset-pipeline-research`) achieved high-speed, 100% accurate de-duplication by using a **programmatic-first, agent-healed** architecture.

```
[Raw Registry Names] ──> [Local Regex Exclusions] ──> [Disjoint-Set Union (Union-Find)]
                                                                 │
                                                                 ▼
[Compiler Validation Gate (validate_report.py)] <── [Agent-Enriched Config Builder]
       │
       ├── Exit Code 1 (Missing Synonym) ──> [Agent Appends to Config] (Self-Healing)
       └── Exit Code 0 ──> Success!
```

Its workflow relies on three core tenets:
1. **Local Noise Cleansing**: A static, comprehensive list of regexes and excluded words filters out chemo agents (e.g., temozolomide, gemcitabine), placebos, saline, and general clinical parameters (e.g., dose-escalation, cohort) instantly. This eliminates over 90% of registry background noise without single LLM call.
2. **Disjoint-Set Union (DSU) / Union-Find Clustering**: If Trial 1 associates `"Paxalisib"` with `"GDC-0084"`, and Trial 2 associates `"GDC0084"` with `"Kazia"`, a pure Python union-find algorithm automatically groups them into `{"Paxalisib", "GDC-0084", "GDC0084", "Kazia"}` programmatically in milliseconds.
3. **Compile-Time Syncing & Self-Healing Feedback**:
   * **In-Memory Parsing**: A helper function (`parse_existing_report`) parses the existing Markdown table cells using regexes to extract primary names and parenthetical aliases, automatically updating the active config in-memory.
   * **Compiler Gate Feedback**: The validation script (`validate_report.py`) queries the raw databases for NCT/CDE trial identifiers cited in the final table. If it finds a synonym mapping that is missing from the configuration, it exits with `code 1` and prints the exact mismatch (e.g., `Missing alias Apadamtiganat for ACT-001`). The agent catches this error, appends the alias to the builder, and re-compiles until the compiler returns `code 0`.

---

## 3. Proposed Refactoring Plan

We will replace the multi-stage LLM pipeline in the reconciliation and config discovery modules with local programmatic pre-filtering, while maintaining agent-driven enrichment and compile-time syncing.

### Component-Level Changes

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                    PROPOSAL                                       │
├──────────────────────────────────┬────────────────────────────────────────────────┤
│ Current LLM-Centric Component     │ Proposed Programmatic / Self-Healing Component │
├──────────────────────────────────┼────────────────────────────────────────────────┤
│ classify_interventions (LLM)     │ Local Regex Exclusions + DSU Clustering         │
│ Secondary Modality Audit (LLM)   │ Static Blocklists & Target Word Matching        │
│ Global Consolidation (LLM)      │ Programmatic Alias Consolidation (DSU)         │
│ LLM-Batched Discovery            │ Python Configuration Builder (Self-Creating)   │
└──────────────────────────────────┴────────────────────────────────────────────────┘
```

### Phase 1: Local Pre-Filtering & DSU Clustering
We will migrate the cleaning and exclusion lists from `scratch_test_discover.py` to `src/utils/landscape/table_formatters.py`:
* **`EXCLUDE_LOWER`**: Standard background agents (chemotherapies, target synonyms, placebos).
* **`GENERIC_WORDS`**: Modal/clinical descriptors (e.g., "monotherapy", "injection", "dose").
* **`clean_drug_name(name)`**: A pure-string cleanser that strips HTML, splits combination therapies (by `+`, `/`, `联合`), isolates alphanumeric codes (e.g., `ERAS-801`), and filters against exclusion lists.
* **`discover_config()` / `reconcile_all_sources()`**: Run the DSU algorithm over the cleansed database outputs to automatically build the initial asset configuration mapping.

### Phase 2: Simplified LLM Intervention Classification
Instead of asking the LLM to process every raw registry string:
1. The orchestrator cleanses and groups candidate strings programmatically.
2. The agent (`intervention_classifier_agent.py`) is presented with a vastly smaller list of *pre-cleansed, pre-clustered asset candidates*.
3. The agent only determines if the candidate cluster represents a genuine pipeline asset targeting the research target (e.g., yes/no classification) and assigns its modality.
4. **Remove** the secondary modality audit prompt and tertiary global consolidation LLM call completely, saving up to 90% of the API overhead.

### Phase 3: Self-Healing validation loops
We will wire the programmatic validation script (`src/utils/validate_report.py`) as the primary compiler feedback loop for the agents:
1. When the agent runs `validate_report.py`, it compares all table entries and citations against raw JSON files.
2. If the validator detects a trial citing a synonym that is not registered under the asset's aliases in the config, it terminates with a clear message: `VALIDATION ERROR: Trial NCT05053880 lists Apadamtiganat which is not mapped to ACT-001.`
3. The agent is prompted to parse this error, write the alias directly to the configuration JSON or Python builder script, and re-execute.

---

## 4. Architectural Comparison

| Metric / Dimension | Current Workflow (`biotech-analyst-cli`) | Proposed Workflow (`de-dup-refactor`) |
| :--- | :--- | :--- |
| **Noise Filtering** | Batched LLM classification + secondary LLM audit. | Local programmatic regex and static blocklists. |
| **Synonym Grouping** | Local normalization + tertiary global LLM consolidation. | Local Disjoint-Set Union (Union-Find) clustering. |
| **LLM Calls Per Scan** | 10 to 30+ calls (scaling with raw registry rows). | 1 or 2 high-level enrichment calls. |
| **Execution Latency** | 2 to 5 minutes. | < 10 seconds. |
| **Error Handling** | Brittle; prone to rate-limiting and formatting errors. | Robust; compiler-driven errors with auto-healing. |
| **Configuration State** | Master config built dynamically using LLM outputs. | Self-creating draft config, healed via agent verification. |

---

## 5. Verification Plan

### Automated Verification
* **Unit Tests**: Write `tests/test_reconciliation.py` and `tests/test_classify_interventions.py` asserting that:
  * Exclusions (e.g., placebos, gemcitabine, standard chemotherapies) are successfully ignored.
  * Overlapping synonym sets (e.g., `{"Paxalisib", "GDC-0084"}` and `{"GDC0084", "Kazia"}`) merge into a single disjoint set.
  * Target-related terms (e.g., "EGFR", "EGFRvIII") are not classified as canonical assets.
* **Mock Pipeline Run**: Run a local integration test of the broad scan using a mocked LLM response for the single remaining classification query, verifying that the output table maps trials to assets correctly.

### Manual Verification
* Run a scan command (e.g., `ba bdscan --target "Glioblastoma"`) and verify that the programmatically generated configuration matches the asset list without generating duplicate rows.
