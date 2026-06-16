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
import os

import typer

from src.core.bdscan_orchestrator import run_bdscan_pipeline
from src.core.config import Settings, config_exists, load_config, mask_key, save_config
from src.core.deepdive_orchestrator import run_deepdive_pipeline
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
    folder_safe_name = None
    en_list = None
    zh_list = None
    modality = ""

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

        en_list = [t.strip() for t in en_terms.split(",") if t.strip()]
        zh_list = [t.strip() for t in zh_terms.split(",") if t.strip()]

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
            parts = target_dir.name.split("_")
            if len(parts) >= 3:
                target_name = "_".join(parts[1:-1])
            else:
                target_name = target_dir.name
            folder_safe_name = "".join(
                c if c.isalnum() or c in ("-", "_") else "_" for c in target_name
            )
        else:
            formatting.print_error("Invalid selection.")
            raise typer.Exit(1)

    else:
        formatting.print_error("Action must be 'new' or 'rerun'.")
        raise typer.Exit(1)

    try:
        pdf_out = run_bdscan_pipeline(
            settings=settings,
            action=action,
            target_name=target_name,
            folder_safe_name=folder_safe_name,
            target_dir=target_dir,
            en_list=en_list,
            zh_list=zh_list,
            modality=modality,
        )
    except Exception as e:
        formatting.print_error(f"Pipeline execution failed: {e}")
        raise typer.Exit(1)

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
    folder_safe_name = None
    developer = ""
    trial_id = ""

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

        today = datetime.date.today().strftime("%Y%m%d")
        folder_safe_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in asset_name
        )
        target_folder_name = f"{today}_{folder_safe_name}_DeepDive"
        target_dir = base_path / target_folder_name

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

    try:
        pdf_out = run_deepdive_pipeline(
            settings=settings,
            action=action,
            asset_name=asset_name,
            folder_safe_name=folder_safe_name,
            target_dir=target_dir,
            developer=developer,
            trial_id=trial_id,
        )
    except Exception as e:
        formatting.print_error(f"Pipeline execution failed: {e}")
        raise typer.Exit(1)

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
