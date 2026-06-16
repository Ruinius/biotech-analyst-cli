import sys
from pathlib import Path

# Ensure console handles Chinese characters correctly on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import datetime
import json
import os
import subprocess

import typer

from src.core.config import Settings, config_exists, load_config, mask_key, save_config
from src.utils import formatting

app = typer.Typer(
    name="ba",
    help="Dr. Hops' Biotech Analyst CLI Assistant",
    no_args_is_help=True,
)


@app.command("config")
def main_config():
    """Interactive wizard to configure your profile and API keys."""
    formatting.speak(
        "Welcome to the configuration sequence! Let us sequence your settings genes!",
        include_interjection=False,
    )

    # Try to load existing settings for defaults
    try:
        current = load_config()
    except Exception:
        current = None

    default_name = current.full_name if current else ""
    default_email = current.email if current else ""
    default_base = current.base_folder if current else str(Path.home() / "Desktop")
    default_gemini = current.gemini_api_key if current else ""
    default_openrouter = current.openrouter_api_key if current else ""
    default_deepseek = current.deepseek_api_key if current else ""

    # Prompts
    name = typer.prompt("Enter your full name", default=default_name)
    email = typer.prompt("Enter your email address", default=default_email)
    base_folder = typer.prompt(
        "Enter base folder for research output", default=default_base
    )

    # Ask if they want to configure API keys
    configure_keys = typer.confirm(
        "Would you like to configure API keys for LLM report drafting?", default=True
    )
    gemini_key = default_gemini
    openrouter_key = default_openrouter
    deepseek_key = default_deepseek

    if configure_keys:
        gemini_key = typer.prompt(
            "Gemini API Key (press Enter to keep current)",
            default=default_gemini,
            show_default=False,
        )
        openrouter_key = typer.prompt(
            "OpenRouter API Key (press Enter to keep current)",
            default=default_openrouter,
            show_default=False,
        )
        deepseek_key = typer.prompt(
            "DeepSeek API Key (press Enter to keep current)",
            default=default_deepseek,
            show_default=False,
        )

    # Save
    new_settings = Settings(
        full_name=name,
        email=email,
        base_folder=base_folder,
        gemini_api_key=gemini_key if gemini_key else None,
        openrouter_api_key=openrouter_key if openrouter_key else None,
        deepseek_api_key=deepseek_key if deepseek_key else None,
    )

    try:
        save_config(new_settings)
        formatting.print_success("Configuration saved successfully to .env!")

        # Show configuration summary
        formatting.speak(
            f"Fascinating transcripts! Here is your active profile summary:\n\n"
            f"  [bold]Name:[/bold] {name}\n"
            f"  [bold]Email:[/bold] {email}\n"
            f"  [bold]Base Folder:[/bold] {base_folder}\n"
            f"  [bold]Gemini Key:[/bold] {mask_key(gemini_key)}\n"
            f"  [bold]OpenRouter Key:[/bold] {mask_key(openrouter_key)}\n"
            f"  [bold]DeepSeek Key:[/bold] {mask_key(deepseek_key)}\n",
            include_interjection=False,
        )
    except Exception as e:
        formatting.print_error(f"Failed to save configuration: {e}")


def get_folders_list(base_path: Path):
    """Retrieve subdirectories in the base folder sorted alphabetically."""
    if not base_path.exists():
        return []
    return sorted(
        [p for p in base_path.iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda x: x.name.lower(),
    )


@app.command("folder")
def main_folder():
    """List all target research folders in alphabetical choice labels for easy access."""
    if not config_exists():
        formatting.print_error("Configuration not found. Please run 'ba config' first.")
        raise typer.Exit(1)

    settings = load_config()
    base_path = Path(settings.base_folder)

    if not base_path.exists():
        formatting.print_error(f"Base folder '{base_path}' does not exist.")
        raise typer.Exit(1)

    folders = get_folders_list(base_path)
    if not folders:
        formatting.speak(
            f"By my telomeres! No research folders found under your base directory:\n  {base_path}",
            include_interjection=False,
        )
        return

    # Print out folders in a, b, c format
    formatting.speak(
        "Here is your active research portfolio directories:",
        include_interjection=False,
    )

    def get_letter_label(index: int) -> str:
        label = ""
        while index >= 0:
            label = chr(ord("a") + (index % 26)) + label
            index = (index // 26) - 1
        return label

    label_map = {}
    for idx, folder in enumerate(folders):
        label = get_letter_label(idx)
        label_map[label] = folder
        print(f"  {label}) {folder.name}")

    print()
    choice = typer.prompt("Select a folder by its letter (or 'q' to quit)", default="q")
    choice = choice.strip().lower()

    if choice == "q":
        return

    if choice in label_map:
        selected = label_map[choice]
        formatting.print_success(f"Selected folder: {selected}")

        # Ask to open in Explorer on Windows
        if sys.platform.startswith("win"):
            open_exp = typer.confirm(
                "Would you like to open this folder in Windows Explorer?", default=True
            )
            if open_exp:
                try:
                    os.startfile(selected)
                    formatting.print_success("Windows Explorer launched.")
                except Exception as e:
                    formatting.print_error(f"Failed to open folder: {e}")
    else:
        formatting.print_error("Invalid selection choice.")


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
    )
    if res.returncode != 0:
        formatting.print_warning(
            f"Step '{step_name}' completed with warning or error (Code {res.returncode})."
        )
        # Print output diagnostics for debugging
        if res.stderr:
            print(f"Diagnostics (stderr):\n{res.stderr.strip()}", file=sys.stderr)
        return False
    else:
        formatting.print_success(f"Completed: {step_name}.")
        return True


@app.command("bdscan")
def main_bdscan(
    action: str = typer.Argument(..., help="Action to perform: 'new' or 'rerun'"),
):
    """Execute target pathway or molecule-class broad meta-analysis scanning."""
    if not config_exists():
        formatting.print_error("Configuration not found. Please run 'ba config' first.")
        raise typer.Exit(1)

    settings = load_config()
    base_path = Path(settings.base_folder)
    action = action.strip().lower()

    target_dir = None
    target_name = None

    if action == "new":
        target_name = typer.prompt(
            "Enter pathway/target biological name (e.g. CLDN18.2)"
        )
        target_name = target_name.strip()
        if not target_name:
            formatting.print_error("Target name cannot be empty.")
            raise typer.Exit(1)

        en_terms = typer.prompt(
            "Enter English search synonyms (comma-separated)",
            default=f"{target_name}, {target_name.replace('.', '')}",
        )
        zh_terms = typer.prompt(
            "Enter Mandarin search synonyms (comma-separated)", default=target_name
        )
        modality = typer.prompt(
            "Enter modality filter (e.g. ADC, Bispecific, Small Molecule or empty)",
            default="",
        )

        # Format target folder name
        today = datetime.date.today().strftime("%Y%m%d")
        folder_safe_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in target_name
        )
        target_folder_name = f"{today}_{folder_safe_name}_Scan"

        target_dir = base_path / target_folder_name
        formatting.speak(f"Initializing scan directory: {target_dir}...")

        # Create folders
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "research").mkdir(exist_ok=True)
            (target_dir / "final_output").mkdir(exist_ok=True)

            # Write a default context.md layman overview template
            context_path = target_dir / "context.md"
            if not context_path.exists():
                context_content = (
                    f"# Context Overview: {target_name} Sourcing\n\n"
                    f"**Target Pathway**: {target_name}\n"
                    f"**Modality Filters**: {modality if modality else 'All'}\n"
                    f"**Date**: {datetime.date.today().strftime('%Y-%m-%d')}\n\n"
                    f"## 1. Biology and Scientific Rationale\n"
                    f"Provide background science for target {target_name} here.\n\n"
                    f"## 2. Clinical Settings and Disease Areas\n"
                    f"Summarize the patient population and target indications.\n"
                )
                context_path.write_text(context_content, encoding="utf-8")
                formatting.print_success("Initialized context.md template.")
        except Exception as e:
            formatting.print_error(f"Failed to initialize directories: {e}")
            raise typer.Exit(1)

        # Build clean lists of terms
        en_list = [t.strip() for t in en_terms.split(",") if t.strip()]
        zh_list = [t.strip() for t in zh_terms.split(",") if t.strip()]

        os.makedirs("tmp", exist_ok=True)

        # --- Run fetches and summaries ---
        formatting.speak(
            "Ribosomes active! Commencing automated database fetching routines..."
        )

        # 1. ClinicalTrials.gov
        for term in en_list:
            out_file = f"tmp/{folder_safe_name}_ct_{term.replace(' ', '_')}.json"
            run_pipeline_step(
                [
                    "src/utils/fetch_clinicaltrials.py",
                    "--terms",
                    term,
                    "--output",
                    out_file,
                    "--limit",
                    "50",
                ],
                f"ClinicalTrials.gov for '{term}'",
            )
            if os.path.exists(out_file):
                run_pipeline_step(
                    [
                        "src/utils/summarize_clinicaltrials.py",
                        "--input",
                        out_file,
                        "--output",
                        out_file.replace(".json", "_sum.txt"),
                    ],
                    f"ClinicalTrials summary for '{term}'",
                )

        # 2. EU CTIS / ANZCTR
        for term in en_list:
            out_file = f"tmp/{folder_safe_name}_anzctr_{term.replace(' ', '_')}.json"
            run_pipeline_step(
                [
                    "src/utils/fetch_anzctr_ctis.py",
                    "--term",
                    term,
                    "--output",
                    out_file,
                    "--limit",
                    "50",
                ],
                f"ANZCTR/CTIS for '{term}'",
            )
            if os.path.exists(out_file):
                run_pipeline_step(
                    [
                        "src/utils/summarize_anzctr_ctis.py",
                        "--input",
                        out_file,
                        "--output",
                        out_file.replace(".json", "_sum.txt"),
                    ],
                    f"ANZCTR/CTIS summary for '{term}'",
                )

        # 3. Conferences
        for term in en_list:
            out_file = f"tmp/{folder_safe_name}_conf_{term.replace(' ', '_')}.json"
            run_pipeline_step(
                [
                    "src/utils/fetch_conferences.py",
                    "--term",
                    term,
                    "--output",
                    out_file,
                    "--limit",
                    "50",
                ],
                f"Conferences for '{term}'",
            )
            if os.path.exists(out_file):
                run_pipeline_step(
                    [
                        "src/utils/summarize_conferences.py",
                        "--input",
                        out_file,
                        "--output",
                        out_file.replace(".json", "_sum.txt"),
                    ],
                    f"Conferences summary for '{term}'",
                )

        # 4. Chinese WHO Registries
        for term in zh_list:
            out_file = f"tmp/{folder_safe_name}_chreg_{term.replace(' ', '_')}.json"
            run_pipeline_step(
                [
                    "src/utils/fetch_chinese_registries.py",
                    "--term",
                    term,
                    "--output",
                    out_file,
                    "--limit",
                    "50",
                ],
                f"Chinese WHO Registries for '{term}'",
            )
            if os.path.exists(out_file):
                run_pipeline_step(
                    [
                        "src/utils/summarize_chinese_registries.py",
                        "--input",
                        out_file,
                        "--output",
                        out_file.replace(".json", "_sum.txt"),
                    ],
                    f"Chinese Registries summary for '{term}'",
                )

        # 5. Direct CDE Playwright Scrape
        for term in zh_list:
            out_file = f"tmp/{folder_safe_name}_cdirect_{term.replace(' ', '_')}.json"
            run_pipeline_step(
                [
                    "src/utils/fetch_china_direct.py",
                    "--term",
                    term,
                    "--output",
                    out_file,
                ],
                f"NMPA CDE direct Playwright search for '{term}'",
            )
            if os.path.exists(out_file):
                run_pipeline_step(
                    [
                        "src/utils/summarize_china_direct.py",
                        "--input",
                        out_file,
                        "--output",
                        out_file.replace(".json", "_sum.txt"),
                    ],
                    f"CDE direct summary for '{term}'",
                )

        # 6. Patents (Lens.org)
        for term in en_list:
            out_file = f"tmp/{folder_safe_name}_lens_{term.replace(' ', '_')}.json"
            run_pipeline_step(
                [
                    "src/utils/fetch_ip_lens.py",
                    "--term",
                    term,
                    "--output",
                    out_file,
                    "--limit",
                    "50",
                ],
                f"Lens.org Patents for '{term}'",
            )
            if os.path.exists(out_file):
                run_pipeline_step(
                    [
                        "src/utils/summarize_ip_lens.py",
                        "--input",
                        out_file,
                        "--output",
                        out_file.replace(".json", "_sum.txt"),
                    ],
                    f"Lens.org summary for '{term}'",
                )

        # 7. PubChem BioAssays
        for term in en_list[:2]:
            out_file = f"tmp/{folder_safe_name}_pubchem_{term.replace(' ', '_')}.json"
            run_pipeline_step(
                [
                    "src/utils/fetch_pubchem.py",
                    "--compound",
                    term,
                    "--output",
                    out_file,
                ],
                f"PubChem Compound search for '{term}'",
            )
            if os.path.exists(out_file):
                run_pipeline_step(
                    [
                        "src/utils/summarize_pubchem.py",
                        "--input",
                        out_file,
                        "--output",
                        out_file.replace(".json", "_sum.txt"),
                    ],
                    f"PubChem summary for '{term}'",
                )

        # Merge trials database into clinicaltrials.json expected by generators
        import glob

        merged_trials = {}
        for f_path in glob.glob(f"tmp/{folder_safe_name}_ct_*.json") + glob.glob(
            f"tmp/{folder_safe_name}_anzctr_*.json"
        ):
            try:
                with open(f_path, encoding="utf-8") as f:
                    trials_data = json.load(f)
                if isinstance(trials_data, dict):
                    # ClinicalTrials.gov output is dict of {nctId: study}
                    for nct, study in trials_data.items():
                        merged_trials[nct] = study
            except Exception:
                pass

        merged_ct_file = f"tmp/{folder_safe_name}_clinicaltrials.json"
        with open(merged_ct_file, "w", encoding="utf-8") as f:
            json.dump(merged_trials, f, indent=2, ensure_ascii=False)

        # Direct China search list merging
        merged_china = []
        for f_path in glob.glob(f"tmp/{folder_safe_name}_cdirect_*.json"):
            try:
                with open(f_path, encoding="utf-8") as f:
                    c_data = json.load(f)
                merged_china.extend(c_data.get("records", []))
            except Exception:
                pass
        merged_china_file = f"tmp/{folder_safe_name}_china_direct.json"
        with open(merged_china_file, "w", encoding="utf-8") as f:
            json.dump({"records": merged_china}, f, indent=2, ensure_ascii=False)

        # --- Copy summaries to research directory ---
        formatting.speak(
            "Fascinating transcripts! Copying summary logs to the research folder..."
        )
        research_dir = target_dir / "research"
        for sum_file in glob.glob(f"tmp/{folder_safe_name}_*_sum.txt"):
            try:
                dest = (
                    research_dir / f"{Path(sum_file).name.replace('_sum.txt', '.md')}"
                )
                with open(sum_file, encoding="utf-8") as s:
                    text = s.read()
                # format log as markdown
                log_md = (
                    f"# Research Log: {dest.stem}\n"
                    f"**Accessed Date**: {datetime.date.today().strftime('%Y-%m-%d')}\n\n"
                    f"```text\n{text}\n```\n"
                )
                dest.write_text(log_md, encoding="utf-8")
            except Exception as e:
                print(f"Failed to write log {sum_file}: {e}")

    elif action == "rerun":
        folders = get_folders_list(base_path)
        if not folders:
            formatting.print_error("No scan directories available for rerun.")
            raise typer.Exit(1)

        print("Select scan folder to rerun:")
        for idx, folder in enumerate(folders):
            print(f"  {idx}) {folder.name}")
        choice_idx = typer.prompt("Select folder number", type=int)
        if 0 <= choice_idx < len(folders):
            target_dir = folders[choice_idx]
            # Infer target name from directory name YYYYMMDD_[Name]_Scan
            parts = target_dir.name.split("_")
            if len(parts) >= 3:
                target_name = "_".join(parts[1:-1])
            else:
                target_name = target_dir.name
            folder_safe_name = "".join(
                c if c.isalnum() or c in ("-", "_") else "_" for c in target_name
            )
            merged_ct_file = f"tmp/{folder_safe_name}_clinicaltrials.json"
            merged_china_file = f"tmp/{folder_safe_name}_china_direct.json"
        else:
            formatting.print_error("Invalid selection.")
            raise typer.Exit(1)

    else:
        formatting.print_error("Action must be 'new' or 'rerun'.")
        raise typer.Exit(1)

    # --- Table Generation ---
    formatting.speak("Initiating competitive landscape table construction schedules...")
    table_out_file = f"tmp/{folder_safe_name}_landscape_table.md"
    run_pipeline_step(
        [
            "src/utils/generate_landscape_table.py",
            "--clinicaltrials",
            merged_ct_file,
            "--china-direct",
            merged_china_file,
            "--output",
            table_out_file,
        ],
        "Competitive Landscape Table Compiler",
    )

    # Read the compiled table
    table_md = ""
    if os.path.exists(table_out_file):
        with open(table_out_file, encoding="utf-8") as tf:
            table_md = tf.read()

    # Create the report document draft
    report_file = (
        target_dir
        / "final_output"
        / f"meta_analysis_{folder_safe_name}_{datetime.date.today().strftime('%Y%m%d')}.md"
    )

    formatting.speak("Synthesizing clinical endpoints report draft...")
    context_text = ""
    context_file = target_dir / "context.md"
    if context_file.exists():
        context_text = context_file.read_text(encoding="utf-8")

    report_content = (
        f"# Pathway Landscape Meta-Analysis: {target_name}\n\n"
        f"**Date of Report**: {datetime.date.today().strftime('%Y-%m-%d')}\n"
        f"**Analyst**: Senior Biotech BD Scout\n"
        f"**Target Pathway**: {target_name}\n\n"
        f"## Executive Summary\n"
        f"Provide synthesized findings here. Reference the research directory.\n\n"
        f"{context_text}\n\n"
        f"## Competitive Landscape Table\n\n"
        f"{table_md}\n\n"
        f"## Strategic BD Takeaways\n"
        f"1. **Rights Availability**: U.S./Global rights availability analysis.\n"
        f"2. **Competitive Crowding**: Sourcing priorities and candidate positioning.\n"
    )
    report_file.write_text(report_content, encoding="utf-8")
    formatting.print_success(f"Report draft saved to: {report_file}")

    # Generate PDF
    formatting.speak("Translating draft report. Compiling premium paginated PDF...")
    pdf_out = report_file.with_suffix(".pdf")

    # Run generic compilation
    run_pipeline_step(
        ["src/utils/convert_md_to_pdf.py", report_file, pdf_out],
        "Markdown to PDF Compiler",
    )

    # Done
    formatting.speak(
        f"Sequence analysis complete! All pipelines ran successfully.\n"
        f"Synthesized PDF report is available at:\n  {pdf_out}",
        include_interjection=True,
    )

    # Open PDF in Windows
    if sys.platform.startswith("win") and pdf_out.exists():
        open_pdf = typer.confirm(
            "Would you like to open the compiled PDF now?", default=True
        )
        if open_pdf:
            try:
                os.startfile(pdf_out)
                formatting.print_success("PDF Reader launched.")
            except Exception as e:
                formatting.print_error(f"Failed to open PDF: {e}")


@app.command("deepdive")
def main_deepdive(
    action: str = typer.Argument(..., help="Action to perform: 'new' or 'rerun'"),
):
    """Conduct due diligence clinical and commercial deep-dives on a specific asset."""
    if not config_exists():
        formatting.print_error("Configuration not found. Please run 'ba config' first.")
        raise typer.Exit(1)

    settings = load_config()
    base_path = Path(settings.base_folder)
    action = action.strip().lower()

    target_dir = None
    asset_name = None

    if action == "new":
        asset_name = typer.prompt("Enter target asset name/code (e.g. Osemitamab)")
        asset_name = asset_name.strip()
        if not asset_name:
            formatting.print_error("Asset name cannot be empty.")
            raise typer.Exit(1)

        developer = typer.prompt("Enter developer/sponsor (e.g. Transcenta)")
        trial_id = typer.prompt(
            "Enter primary Clinical Trial ID (NCT or CTR ID)", default="NCT04818671"
        )

        # Format target folder name
        today = datetime.date.today().strftime("%Y%m%d")
        folder_safe_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in asset_name
        )
        target_folder_name = f"{today}_{folder_safe_name}_DeepDive"

        target_dir = base_path / target_folder_name
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
            raise typer.Exit(1)

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
                    "src/utils/fetch_clinicaltrials.py",
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
                    "src/utils/fetch_clinicaltrials.py",
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
                    "src/utils/summarize_clinicaltrials.py",
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
            ["src/utils/fetch_openfda.py", "--drug", asset_name, "--output", fda_file],
            f"openFDA label check for '{asset_name}'",
        )
        if os.path.exists(fda_file):
            run_pipeline_step(
                [
                    "src/utils/summarize_openfda.py",
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
                "src/utils/fetch_pubchem.py",
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
                    "src/utils/summarize_pubchem.py",
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

    elif action == "rerun":
        folders = get_folders_list(base_path)
        if not folders:
            formatting.print_error("No deep-dive directories available for rerun.")
            raise typer.Exit(1)

        print("Select deep-dive folder to rerun:")
        for idx, folder in enumerate(folders):
            print(f"  {idx}) {folder.name}")
        choice_idx = typer.prompt("Select folder number", type=int)
        if 0 <= choice_idx < len(folders):
            target_dir = folders[choice_idx]
            parts = target_dir.name.split("_")
            if len(parts) >= 3:
                asset_name = "_".join(parts[1:-1])
            else:
                asset_name = target_dir.name
            folder_safe_name = "".join(
                c if c.isalnum() or c in ("-", "_") else "_" for c in asset_name
            )
        else:
            formatting.print_error("Invalid selection.")
            raise typer.Exit(1)

    else:
        formatting.print_error("Action must be 'new' or 'rerun'.")
        raise typer.Exit(1)

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

    # Done
    formatting.speak(
        f"Deep-dive completed! All pipelines ran successfully.\n"
        f"Synthesized PDF report is available at:\n  {pdf_out}",
        include_interjection=True,
    )

    # Open PDF in Windows
    if sys.platform.startswith("win") and pdf_out.exists():
        open_pdf = typer.confirm(
            "Would you like to open the compiled PDF now?", default=True
        )
        if open_pdf:
            try:
                os.startfile(pdf_out)
                formatting.print_success("PDF Reader launched.")
            except Exception as e:
                formatting.print_error(f"Failed to open PDF: {e}")


def main():
    args = sys.argv[1:]

    # Check for help options
    is_help = "--help" in args or "-h" in args or not args

    if is_help:
        msg = "By my double helix! I am Dr. Hops, your biotech concierge. Let us scan the genomic databases and sequence some clinical trials!"
        for arg in args:
            if arg == "config":
                msg = "Telomere extension sequence ready! Shall we configure your settings, my dear colleague?"
                break
            elif arg == "folder":
                msg = "Fascinating transcript folders! Let us browse the active research directories!"
                break
            elif arg == "bdscan":
                msg = "Scanning sequence initiated! Shall we run a broad market or pathway meta-analysis scan?"
                break
            elif arg == "deepdive":
                msg = "Due diligence sweep ready! Let us perform deep clinical asset diligence!"
                break
        formatting.speak(msg, include_interjection=False)

    app()


if __name__ == "__main__":
    main()
