# CLI Interface Specification (`docs/cli_spec.md`)

This document defines the CLI interface commands, arguments, option structures, and terminal behaviors for the Biotech Analyst CLI (`ba`).

---

## 1. Global Setup & Command Structure

The CLI is built using **Typer** and styled using **Rich**. It features **Dr. Hops** (the nerdy biotech rabbit) who delivers setup guides and pipeline diagnostics in terminal speech panels.

All commands are executed using `uv run ba <command>` or via the global activated environment shim `ba <command>`.

---

## 2. CLI Command Reference

### `ba config`
* **Objective:** Interactive wizard to set up or modify your user profile and API key/model settings.
* **Flow:**
  1. Prompts for `Full Name` (uses existing config default if present).
  2. Prompts for `Email Address`.
  3. Prompts for `Base Folder` target for all research outputs.
  4. Interactive confirmation: "Would you like to configure LLM settings?".
     * Prompts to select the active `LLM Provider` (`gemini`, `openrouter`, or `deepseek`).
     * Prompts for the API key of the selected provider.
     * Prompts to type the custom model name to use for that provider.
  5. Saves configuration settings directly to `.env` in the current folder, retaining legacy keys and preferences for other non-active providers.
  6. Renders a masked configuration summary.

---

### `ba folder`
* **Objective:** Quick directory explorer for your active biotech research portfolio.
* **Flow:**
  1. Verifies if configuration exists.
  2. Scans the configured base folder for any directories.
  3. Lists directories sorted alphabetically, assigned letter codes (e.g. `a)`, `b)`, `c)`).
  4. Prompts: "Select a folder by its letter (or 'q' to quit)".
  5. If running on Windows, prompts: "Would you like to open this folder in Windows Explorer?". Launches Explorer if confirmed.

---

### `ba bdscan [new/rerun] [query]`
* **Objective:** Orchestrates target pathway and molecule-class broad meta-analysis scanning.
* **Arguments:**
  * `action` (required): `new` or `rerun`.
  * `query` (optional, for `new` action): The target pathway search query (e.g. `"Claudin 18.2 ADC"` or `"Claudin 18.2 pancreatic cancer"`). If not provided on the command line, the user will be prompted to enter it. The pipeline automatically extracts the target name, English/Mandarin search synonyms, and modality filters from this query.
  * `rerun`: Allows selecting an existing scan directory and re-runs the pipeline.
* **Options:** None required.
* **Output Folders:**
  Creates a folder inside the configured base directory: `{YYYYMMDD}_{Target}_Scan/`
  * `{Target}_Scan/research/`: Contains context overview (`context.md`), source-specific query tables, the master landscape table, and intermediate researcher logs.
  * `{Target}_Scan/final_output/`: Contains the summarized competitive table, final synthesized report, and compiled paginated PDF.

---

### `ba deepdive [new/rerun]`
* **Objective:** Performs clinical and commercial due diligence on a specific clinical asset.
* **Arguments:**
  * `new`: Prompts for asset name, sponsor/developer, and clinical trial IDs (NCT or CTR numbers). Runs the deep-dive diligence pipeline.
  * `rerun`: Re-runs the pipeline for an existing asset folder.
* **Output Folders:**
  Creates a folder inside the configured base directory: `{YYYYMMDD}_{Asset}_DeepDive/`
  * `{Asset}_DeepDive/research/`: Contains context overview (`context.md`) and raw clinical trial, openFDA, and PubChem query summary logs.
  * `{Asset}_DeepDive/final_output/`: Contains the synthesized due diligence memo (`deep_dive_{Asset}_{YYYYMMDD}.md`) and the compiled PDF.
