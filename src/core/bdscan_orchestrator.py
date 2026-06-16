import os
import subprocess
import sys
from pathlib import Path

from src.agents.bdscan_agents.asset_research_agent import AssetResearchAgent
from src.agents.bdscan_agents.compile_landscape import compile_landscape_table
from src.agents.bdscan_agents.context_agent import generate_context
from src.agents.bdscan_agents.curator_agent import CuratorAgent
from src.agents.bdscan_agents.db_search_agent import DatabaseSearchAgent
from src.agents.bdscan_agents.synthesis_agent import SynthesisAgent
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


def run_bdscan_pipeline(
    settings: Settings,
    action: str,
    target_name: str,
    folder_safe_name: str,
    target_dir: Path,
    en_list: list[str] | None = None,
    zh_list: list[str] | None = None,
    modality: str = "",
) -> Path:
    """Execute pathway broad scan pipeline using multi-agent loops."""
    formatting.speak("Dr. Hops is initializing the agentic Broad Scan pipeline...")

    # Set synonyms
    en_terms = en_list or [target_name]
    zh_terms = zh_list or [target_name]

    if action == "new":
        formatting.speak(f"Initializing target directory structure: {target_dir}...")
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "research").mkdir(exist_ok=True)
            (target_dir / "final_output").mkdir(exist_ok=True)
        except Exception as e:
            formatting.print_error(f"Failed to initialize directories: {e}")
            raise RuntimeError(f"Directory initialization failed: {e}")

        # Step 1: Context Agent
        generate_context(
            settings, target_name, en_terms, zh_terms, modality, target_dir
        )

        # Step 2: Database Search Agent (4-turn sequential loop for 8 databases)
        db_agent = DatabaseSearchAgent(settings, folder_safe_name, target_dir)
        db_agent.execute_search_pipeline(target_name, en_terms, zh_terms, modality)

        # Curation Step: Curate database search logs
        curator = CuratorAgent(settings)
        curator.curate_database_search(target_dir)

        # Step 3: Landscape Table Compiler
        compile_landscape_table(folder_safe_name, target_dir)

    # Re-run or compilation phase
    table_path = target_dir / "research" / "landscape_table.md"
    if not table_path.exists():
        formatting.print_warning(
            "Landscape table not found. Compiling from existing source JSONs..."
        )
        compile_landscape_table(folder_safe_name, target_dir)

    # Step 4: Asset Research Agent (4-turn web search loop per asset)
    asset_agent = AssetResearchAgent(settings, target_dir)
    asset_agent.research_all_assets()

    # Curation Step: Curate web search logs
    curator = CuratorAgent(settings)
    curator.curate_web_search(target_dir)

    # Step 5: Final Synthesis Agent (10-turn strategic synthesis)
    synthesis_agent = SynthesisAgent(settings, folder_safe_name, target_dir)
    report_file, table_file = synthesis_agent.generate_synthesis(target_name, modality)

    # Generate PDF from the strategic report markdown
    formatting.speak("Compiling strategic report to premium paginated PDF...")
    pdf_out = report_file.with_suffix(".pdf")
    run_pipeline_step(
        ["src/utils/convert_md_to_pdf.py", str(report_file), str(pdf_out)],
        "Markdown to PDF Compiler",
    )

    return pdf_out
