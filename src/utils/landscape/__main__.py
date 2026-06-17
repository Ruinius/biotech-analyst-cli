"""
CLI shim for src.utils.landscape — preserves the original generate_landscape_table.py
command-line interface for any external scripts or ad-hoc usage:

    python -m src.utils.landscape --clinicaltrials ... --output ...

This delegates to load_and_build_from_files() from table_builder.py.
"""

import argparse
import sys

from src.utils.landscape.table_builder import load_and_build_from_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Competitive Landscape Table from raw clinical registries."
    )
    parser.add_argument(
        "--config", help="Path to config JSON mapping drug names to synonyms (optional)"
    )
    parser.add_argument(
        "--clinicaltrials", help="Path to ClinicalTrials.gov JSON database"
    )
    parser.add_argument(
        "--china-direct", help="Path to ChinaDrugTrials direct search JSON"
    )
    parser.add_argument(
        "--existing-report",
        help="Path to existing report to extract qualitative metadata",
    )
    parser.add_argument(
        "--output", required=True, help="Path to write the markdown table output"
    )
    parser.add_argument(
        "--target-name",
        default="",
        help="Primary target name for LLM-based intervention classification",
    )
    parser.add_argument(
        "--target-synonyms",
        default="",
        help="Comma-separated list of target name synonyms for classification context",
    )
    parser.add_argument(
        "--database-json-dir",
        default=None,
        help="Optional path to {target_dir}/database_json/ for raw source files",
    )

    args = parser.parse_args()

    target_synonyms_list = [
        s.strip() for s in args.target_synonyms.split(",") if s.strip()
    ]

    try:
        load_and_build_from_files(
            clinicaltrials_path=args.clinicaltrials,
            china_direct_path=getattr(args, "china_direct", None),
            config_path=args.config,
            existing_report_path=getattr(args, "existing_report", None),
            output_path=args.output,
            target_name=args.target_name,
            target_synonyms=target_synonyms_list,
            database_json_dir=args.database_json_dir,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
