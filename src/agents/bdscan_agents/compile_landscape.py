import os
import subprocess
import sys
from pathlib import Path

from src.utils import formatting
from src.utils.generate_landscape_table import md_table_to_csv, md_table_to_text_table


def compile_landscape_table(
    folder_safe_name: str,
    target_dir: Path,
    target_name: str = "",
    target_synonyms: list | None = None,
) -> Path:
    """Compile raw sources into the initial master landscape table under research/."""
    formatting.print_info("Compiling master landscape table...")

    merged_ct_file = f"tmp/{folder_safe_name}_clinicaltrials.json"
    merged_china_file = f"tmp/{folder_safe_name}_china_direct.json"
    temp_table_out = f"tmp/{folder_safe_name}_initial_landscape.md"
    master_table_out = target_dir / "research" / "landscape_table.md"

    # Make sure target folder exists
    master_table_out.parent.mkdir(parents=True, exist_ok=True)

    # Run the existing generate_landscape_table.py script
    my_env = os.environ.copy()
    my_env["PYTHONIOENCODING"] = "utf-8"
    cmd_args = [
        sys.executable,
        "src/utils/generate_landscape_table.py",
        "--clinicaltrials",
        merged_ct_file,
        "--china-direct",
        merged_china_file,
        "--output",
        temp_table_out,
    ]
    if target_name:
        cmd_args += ["--target-name", target_name]
    if target_synonyms:
        cmd_args += ["--target-synonyms", ",".join(target_synonyms)]

    formatting.print_info("Running legacy landscape table generation script...")
    res = subprocess.run(cmd_args, env=my_env, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(temp_table_out):
        formatting.print_error(
            f"Landscape table generation failed: {res.stderr or res.stdout}"
        )
        # Write dummy empty table (with # column) so pipeline doesn't crash entirely
        headers = "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |"
        divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        dummy_md = f"{headers}\n{divider}\n"
        master_table_out.write_text(md_table_to_text_table(dummy_md), encoding="utf-8")
        csv_out = master_table_out.with_suffix(".csv")
        csv_out.write_text(md_table_to_csv(dummy_md), encoding="utf-8-sig")
        return master_table_out

    # Read the generated table and append Web-research columns
    with open(temp_table_out, encoding="utf-8") as f:
        lines = f.readlines()

    # The generated .md already has the # column from generate_landscape_table.py.
    # We just need to append the 4 Web columns.
    # idx 0 = header, idx 1 = divider, idx >= 2 = data rows
    modified_lines = []
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        # Split columns
        cols = [c.strip() for c in line.split("|")]
        # Since line starts and ends with '|', cols[0] and cols[-1] are empty
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

    # Save to research/landscape_table.md with column-aligned formatting
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

    return master_table_out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Compile raw sources into master landscape table"
    )
    parser.add_argument("--folder-name", required=True)
    parser.add_argument("--target-dir", required=True)
    args = parser.parse_args()
    compile_landscape_table(args.folder_name, Path(args.target_dir))
