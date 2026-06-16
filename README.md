# Biotech Analyst CLI (ba)

A specialized business development scanning and due diligence CLI for biotech assets, pathway meta-analyses, and market scans. It features a nerdy white rabbit interface named **Dr. Hops** who assists in fetching data from registries, compiling landscape matrices, validating reports against raw databases, and converting markdown documentation to print-ready PDFs.

## How to Start and Run the CLI

Since this project is managed using `uv`, you can run the CLI commands in a few different ways:

### 1. Using `uv run` (Recommended)
You can invoke the CLI directly from the project root without activating the virtual environment:
```powershell
uv run ba --help
```

### 2. Activating the Virtual Environment
Activate the local environment and use the global `ba` shim:
```powershell
# In PowerShell:
.venv\Scripts\Activate.ps1

# Run the command directly:
ba --help
```

### 3. Editable Installation
If the command `ba` is not found after activation, make sure the local package is installed in editable mode in your environment:
```powershell
uv pip install -e .
```

---

## Commands

- `ba config`: Run the interactive configuration flow to set name, email, API keys, and default base directory (defaults to Desktop).
- `ba folder`: List all target research folders in the configured base directory alphabetically (using letters `a`, `b`, `c`, etc.) to easily view/locate active directories.
- `ba bdscan [new/rerun]`:
  - `new`: Prompts for pathway/target names, creates a new directory, and triggers the multi-registry fetch + compile + PDF sequence.
  - `rerun`: Allows selecting an existing scan directory and re-runs the fetching/report generation pipeline.
- `ba deepdive [new/rerun]`:
  - `new`: Prompts for specific asset names and trial IDs, creates a directory, and runs the deep-dive diligence pipeline.
  - `rerun`: Selects an existing deep-dive directory and re-runs the pipeline.

## Dependencies

Managed using `uv`:
- Typer, Rich (CLI & terminal styling)
- Pydantic (Configuration & schemas)
- Pandas, PDFPlumber, PyPDF (Data processing & extraction)
- Playwright (China Drug Trials direct scraping)
- Markdown-PDF, PyMuPDF (PDF generation & header/footer embedding)
