"""
Landscape Compiler Agent — §3 refactor: direct Python imports, no subprocess.

Orchestrates compilation of the initial competitive landscape table by:
1. Loading raw CT + China CDE data from database_json/
2. Calling build_landscape_table() directly via Python import
3. Appending Web-research placeholder columns
4. Writing aligned landscape_table.md and landscape_table.csv to {target_dir}/research/
"""

import os
from pathlib import Path

from src.utils import formatting
from src.utils.landscape.exporters import md_table_to_csv, md_table_to_text_table
from src.utils.landscape.table_builder import load_and_build_from_files


def compile_landscape_table(
    folder_safe_name: str,
    target_dir: Path,
    target_name: str = "",
    target_synonyms: list | None = None,
) -> Path:
    """Compile raw sources into the initial master landscape table under research/."""
    formatting.print_info("Compiling master landscape table...")

    master_table_out = target_dir / "research" / "landscape_table.md"
    master_table_out.parent.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Resolve input paths — strictly from database_json/ directory
    # -----------------------------------------------------------------------
    database_json_dir = target_dir / "database_json"
    if not database_json_dir.exists():
        raise FileNotFoundError(
            f"Database JSON directory not found: {database_json_dir}"
        )

    merged_ct_file = os.path.join(
        str(database_json_dir), f"{folder_safe_name}_clinicaltrials.json"
    )
    merged_china_file = os.path.join(
        str(database_json_dir), f"{folder_safe_name}_china_direct.json"
    )

    if not os.path.exists(merged_ct_file):
        raise FileNotFoundError(
            f"Merged ClinicalTrials JSON not found: {merged_ct_file}"
        )
    if not os.path.exists(merged_china_file):
        raise FileNotFoundError(
            f"Merged China Direct JSON not found: {merged_china_file}"
        )

    temp_table_out = target_dir / "research" / "_initial_landscape_base.md"

    # -----------------------------------------------------------------------
    # Run build_landscape_table via direct import (no subprocess)
    # -----------------------------------------------------------------------
    formatting.print_info("Building landscape table via direct import...")
    try:
        load_and_build_from_files(
            clinicaltrials_path=merged_ct_file,
            china_direct_path=merged_china_file,
            config_path=None,
            existing_report_path=None,
            output_path=str(temp_table_out),
            target_name=target_name,
            target_synonyms=target_synonyms,
            database_json_dir=str(database_json_dir)
            if database_json_dir.exists()
            else None,
        )
    except Exception as e:
        formatting.print_error(f"Landscape table generation failed: {e}")
        # Write dummy empty table so pipeline doesn't crash entirely
        headers = "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |"
        divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        dummy_md = f"{headers}\n{divider}\n"
        master_table_out.write_text(md_table_to_text_table(dummy_md), encoding="utf-8")
        csv_out = master_table_out.with_suffix(".csv")
        csv_out.write_text(md_table_to_csv(dummy_md), encoding="utf-8-sig")
        return master_table_out

    if not temp_table_out.exists():
        formatting.print_error("Landscape table generation produced no output file.")
        return master_table_out

    # -----------------------------------------------------------------------
    # Append Web-research placeholder columns
    # -----------------------------------------------------------------------
    with open(temp_table_out, encoding="utf-8") as f:
        lines = f.readlines()

    modified_lines = []
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 3:
            modified_lines.append(line)
            continue

        if idx == 0:
            # Header line: append 4 new Web columns
            new_cols = cols[1:-1] + [
                "Web Selectivity & Safety Profile",
                "Web Key Efficacy Data",
                "Web Upcoming Milestones",
                "Web Citations / Sources",
            ]
            modified_lines.append("| " + " | ".join(new_cols) + " |")
        elif idx == 1:
            # Divider line: append 4 new dividers
            new_divs = cols[1:-1] + [":---", ":---", ":---", ":---"]
            modified_lines.append("| " + " | ".join(new_divs) + " |")
        else:
            # Data row: append 4 Web placeholder cells
            new_data = cols[1:-1] + [
                "Web research pending.",
                "Web research pending.",
                "Web research pending.",
                "N/A",
            ]
            modified_lines.append("| " + " | ".join(new_data) + " |")

    final_md = "\n".join(modified_lines) + "\n"
    aligned_md = md_table_to_text_table(final_md)
    master_table_out.write_text(aligned_md, encoding="utf-8")
    formatting.print_success(
        f"Successfully compiled column-aligned landscape table at {master_table_out}"
    )

    # Write CSV version alongside the .md
    csv_out = master_table_out.with_suffix(".csv")
    csv_out.write_text(md_table_to_csv(final_md), encoding="utf-8-sig")
    formatting.print_success(f"Saved CSV table at {csv_out}")

    # Clean up temporary base file
    try:
        temp_table_out.unlink(missing_ok=True)
    except Exception:
        pass

    return master_table_out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Compile raw sources into master landscape table"
    )
    parser.add_argument("--folder-name", required=True)
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--target-name", default="")
    parser.add_argument("--target-synonyms", default="")
    args = parser.parse_args()
    synonyms = [s.strip() for s in args.target_synonyms.split(",") if s.strip()]
    compile_landscape_table(
        args.folder_name, Path(args.target_dir), args.target_name, synonyms
    )
