import datetime
import os
import subprocess
import sys
from pathlib import Path

from src.core.config import Settings
from src.utils import formatting


def run_pipeline_step(cmd_args, step_name):
    """Execute a python subprocess pipeline stage with formatting and error logs."""
    formatting.print_info(f"Running: {step_name}...")
    my_env = os.environ.copy()
    my_env["PYTHONIOENCODING"] = "utf-8"

    res = subprocess.run(
        [sys.executable] + cmd_args,
        env=my_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        formatting.print_warning(
            f"Step '{step_name}' completed with warning or error (Code {res.returncode})."
        )
        if res.stderr:
            print(f"Diagnostics (stderr):\n{res.stderr.strip()}", file=sys.stderr)
        return False
    else:
        formatting.print_success(f"Completed: {step_name}.")
        return True


def run_deepdive_pipeline(
    settings: Settings,
    action: str,
    asset_name: str,
    folder_safe_name: str,
    target_dir: Path,
    developer: str = "",
    trial_id: str = "",
) -> Path:
    """Execute single asset deep-dive due diligence pipeline."""
    if action == "new":
        formatting.speak(f"Initializing deep-dive directory: {target_dir}...")

        # Create folders
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "research").mkdir(exist_ok=True)
            (target_dir / "final_output").mkdir(exist_ok=True)

            # Write a default context.md layman overview template
            context_path = target_dir / "context.md"
            if not context_path.exists():
                context_content = (
                    f"# Layman Overview: {asset_name} ({developer})\n\n"
                    f"**Asset Code**: {asset_name}\n"
                    f"**Sponsor**: {developer}\n"
                    f"**Date**: {datetime.date.today().strftime('%Y-%m-%d')}\n\n"
                    f"This document describes {asset_name}, an investigational therapy developed by {developer}.\n"
                )
                context_path.write_text(context_content, encoding="utf-8")
                formatting.print_success("Initialized context.md template.")
        except Exception as e:
            formatting.print_error(f"Failed to initialize directories: {e}")
            raise RuntimeError(f"Failed to initialize directories: {e}")

        os.makedirs("tmp", exist_ok=True)

        # --- Run fetches and summaries ---
        formatting.speak(
            "Transcribing trials! Fetching registry records for diligence audit..."
        )

        # 1. ClinicalTrials.gov by NCT or term
        ct_file = f"tmp/{folder_safe_name}_ct.json"
        if trial_id.strip().upper().startswith("NCT"):
            run_pipeline_step(
                [
                    "src/tools/fetch_clinicaltrials.py",
                    "--nct-ids",
                    trial_id,
                    "--output",
                    ct_file,
                ],
                f"ClinicalTrials.gov for NCT '{trial_id}'",
            )
        else:
            run_pipeline_step(
                [
                    "src/tools/fetch_clinicaltrials.py",
                    "--terms",
                    asset_name,
                    "--output",
                    ct_file,
                    "--limit",
                    "5",
                ],
                f"ClinicalTrials.gov for asset '{asset_name}'",
            )
        if os.path.exists(ct_file):
            run_pipeline_step(
                [
                    "src/tools/summarize_clinicaltrials.py",
                    "--input",
                    ct_file,
                    "--output",
                    ct_file.replace(".json", "_sum.txt"),
                ],
                "ClinicalTrials summary",
            )

        # 2. openFDA Labels
        fda_file = f"tmp/{folder_safe_name}_openfda.json"
        run_pipeline_step(
            ["src/tools/fetch_openfda.py", "--drug", asset_name, "--output", fda_file],
            f"openFDA label check for '{asset_name}'",
        )
        if os.path.exists(fda_file):
            run_pipeline_step(
                [
                    "src/tools/summarize_openfda.py",
                    "--input",
                    fda_file,
                    "--output",
                    fda_file.replace(".json", "_sum.txt"),
                ],
                "openFDA safety summary",
            )

        # 3. PubChem BioAssay
        pubchem_file = f"tmp/{folder_safe_name}_pubchem.json"
        run_pipeline_step(
            [
                "src/tools/fetch_pubchem.py",
                "--compound",
                asset_name,
                "--output",
                pubchem_file,
            ],
            f"PubChem compound lookup for '{asset_name}'",
        )
        if os.path.exists(pubchem_file):
            run_pipeline_step(
                [
                    "src/tools/summarize_pubchem.py",
                    "--input",
                    pubchem_file,
                    "--output",
                    pubchem_file.replace(".json", "_sum.txt"),
                ],
                "PubChem BioAssay selectivity summary",
            )

        # --- Copy summaries to research directory ---
        import glob

        research_dir = target_dir / "research"
        for sum_file in glob.glob(f"tmp/{folder_safe_name}_*_sum.txt"):
            try:
                dest = (
                    research_dir / f"{Path(sum_file).name.replace('_sum.txt', '.md')}"
                )
                with open(sum_file, encoding="utf-8") as s:
                    text = s.read()
                log_md = (
                    f"# Diligence Research Log: {dest.stem}\n"
                    f"**Accessed Date**: {datetime.date.today().strftime('%Y-%m-%d')}\n\n"
                    f"```text\n{text}\n```\n"
                )
                dest.write_text(log_md, encoding="utf-8")
            except Exception as e:
                print(f"Failed to write log {sum_file}: {e}")

    # Create the report document draft
    report_file = (
        target_dir
        / "final_output"
        / f"deep_dive_{folder_safe_name}_{datetime.date.today().strftime('%Y%m%d')}.md"
    )

    formatting.speak("Synthesizing due diligence report...")
    context_text = ""
    context_file = target_dir / "context.md"
    if context_file.exists():
        context_text = context_file.read_text(encoding="utf-8")

    # Read summaries for report drafting if available
    ct_sum_path = target_dir / "research" / f"{folder_safe_name}_ct.md"
    if ct_sum_path.exists():
        ct_sum_path.read_text(encoding="utf-8")

    report_content = (
        f"# Asset Deep-Dive Diligence Memo: {asset_name}\n\n"
        f"**Date of Report**: {datetime.date.today().strftime('%Y-%m-%d')}\n"
        f"**Analyst**: Senior Biotech BD Scout\n"
        f"**Sponsor/Developer**: {asset_name}\n\n"
        f"## Executive Summary & BD Recommendation\n"
        f"Recommendation: **GO / NO-GO / DEFER**\n\n"
        f"## 1. Context Overview\n"
        f"{context_text}\n\n"
        f"## 2. Clinical Trial Overview\n"
        f"Provide detailed trial records here.\n\n"
        f"## 3. Preclinical and Selectivity Benchmarking\n"
        f"Selectivity analysis compared to competitors.\n\n"
        f"## 4. SWOT Analysis\n"
        f"### Strengths\n- High selectivity profile.\n"
        f"### Weaknesses\n- Early clinical development stage.\n"
        f"### Opportunities\n- Fast-track or breakthrough designations.\n"
        f"### Threats\n- Competitor crowding.\n"
    )
    report_file.write_text(report_content, encoding="utf-8")
    formatting.print_success(f"Diligence memo draft saved to: {report_file}")

    # Generate PDF
    formatting.speak("Translating draft report. Compiling premium paginated PDF...")
    pdf_out = report_file.with_suffix(".pdf")

    # Run generic compilation
    run_pipeline_step(
        ["src/utils/convert_md_to_pdf.py", report_file, pdf_out],
        "Markdown to PDF Compiler",
    )

    return pdf_out
