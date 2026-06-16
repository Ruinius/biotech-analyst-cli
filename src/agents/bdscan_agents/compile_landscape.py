import os
import subprocess
import sys
from pathlib import Path

from src.utils import formatting


def compile_landscape_table(
    folder_safe_name: str,
    target_dir: Path,
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

    formatting.print_info("Running legacy landscape table generation script...")
    res = subprocess.run(cmd_args, env=my_env, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(temp_table_out):
        formatting.print_error(
            f"Landscape table generation failed: {res.stderr or res.stdout}"
        )
        # Write dummy empty table so pipeline doesn't crash entirely
        headers = "| Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Selectivity & Safety Profile | Key Efficacy / Biomarker Data | Upcoming Milestones | Citations |"
        divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        master_table_out.write_text(f"{headers}\n{divider}\n", encoding="utf-8")
        return master_table_out

    # Read the generated table and append Web-research columns
    with open(temp_table_out, encoding="utf-8") as f:
        lines = f.readlines()

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
            # Header line
            # Append 4 new columns: Web Selectivity & Safety, Web Efficacy, Web Milestones, Web Citations
            new_cols = cols[1:-1] + [
                "Web Selectivity & Safety Profile",
                "Web Key Efficacy Data",
                "Web Upcoming Milestones",
                "Web Citations / Sources",
            ]
            modified_lines.append("| " + " | ".join(new_cols) + " |")
        elif idx == 1:
            # Divider line
            new_divs = cols[1:-1] + [":---", ":---", ":---", ":---"]
            modified_lines.append("| " + " | ".join(new_divs) + " |")
        else:
            # Data row
            new_data = cols[1:-1] + [
                "Web research pending.",
                "Web research pending.",
                "Web research pending.",
                "N/A",
            ]
            modified_lines.append("| " + " | ".join(new_data) + " |")

    # Save to research/landscape_table.md
    master_table_out.write_text("\n".join(modified_lines) + "\n", encoding="utf-8")
    formatting.print_success(
        f"Successfully compiled master landscape table with Web columns at {master_table_out}"
    )

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
