#!/usr/bin/env python3
"""
Biotech BD Asset Pipeline - PDF Ingestion & Extraction Utility
Uses pypdf for rapid text extraction and pdfplumber for robust table extraction,
outputting formatted markdown, text, or JSON files.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import pdfplumber
import pypdf


def extract_text_pypdf(pdf_path: Path) -> str:
    """Extract plain text using pypdf for speed and robustness."""
    text_content = []
    try:
        reader = pypdf.PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_content.append(f"--- Page {i + 1} ---\n{text}\n")
    except Exception as e:
        print(f"Error during pypdf text extraction: {e}", file=sys.stderr)
    return "\n".join(text_content)


def extract_tables_pdfplumber(pdf_path: Path) -> list:
    """Extract tables using pdfplumber and return them as a list of lists of lists (table rows)."""
    extracted_tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    # Filter out completely empty rows and columns
                    filtered_table = []
                    for row in table:
                        if any(
                            cell is not None and str(cell).strip() != "" for cell in row
                        ):
                            cleaned_row = [
                                str(cell).replace("\n", " ").strip()
                                if cell is not None
                                else ""
                                for cell in row
                            ]
                            filtered_table.append(cleaned_row)

                    if filtered_table:
                        extracted_tables.append(
                            {
                                "page": page_num + 1,
                                "table_index": table_idx + 1,
                                "data": filtered_table,
                            }
                        )
    except Exception as e:
        print(f"Error during pdfplumber table extraction: {e}", file=sys.stderr)
    return extracted_tables


def convert_table_to_markdown(table_data: list) -> str:
    """Convert a raw table list of rows into a clean Markdown table using pandas."""
    if not table_data:
        return ""
    try:
        # Check if the table has at least one row
        table_data[0]
        table_data[1:]

        # Handle cases with single row or mismatched columns
        max_cols = max(len(row) for row in table_data)

        # Pad rows to have uniform length
        padded_table = []
        for row in table_data:
            padded_row = row + [""] * (max_cols - len(row))
            padded_table.append(padded_row)

        df = pd.DataFrame(padded_table[1:], columns=padded_table[0])
        return df.to_markdown(index=False)
    except Exception:
        # Fallback to simple markdown builder
        md = []
        for i, row in enumerate(table_data):
            row_str = " | ".join(row)
            md.append(f"| {row_str} |")
            if i == 0:
                sep = " | ".join(["---"] * len(row))
                md.append(f"| {sep} |")
        return "\n".join(md)


def run_parser(
    pdf_path: Path,
    output_path: Path = None,
    mode: str = "both",
    output_format: str = "markdown",
):
    """Orchestrates the extraction process and saves or prints the results."""
    print(f"Processing: {pdf_path.name}")
    print(f"Extraction Mode: {mode} | Output Format: {output_format}")

    if not pdf_path.exists():
        print(f"Error: Input file {pdf_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    extracted_text = ""
    extracted_tables = []

    # 1. Text extraction
    if mode in ["text", "both"]:
        print("Extracting text...")
        extracted_text = extract_text_pypdf(pdf_path)

    # 2. Table extraction
    if mode in ["tables", "both"]:
        print("Extracting tables...")
        extracted_tables = extract_tables_pdfplumber(pdf_path)

    # 3. Format output
    output_content = ""
    if output_format == "json":
        output_data = {
            "metadata": {
                "source_file": str(pdf_path),
                "total_pages": len(pypdf.PdfReader(pdf_path).pages)
                if mode in ["text", "both"]
                else "Unknown",
            }
        }
        if mode in ["text", "both"]:
            output_data["text"] = extracted_text
        if mode in ["tables", "both"]:
            output_data["tables"] = extracted_tables

        output_content = json.dumps(output_data, indent=2)
    else:  # markdown / plain text
        blocks = []
        blocks.append(f"# Analysis Report for {pdf_path.name}\n")

        if mode in ["tables", "both"] and extracted_tables:
            blocks.append("## Extracted Quantitative Tables\n")
            for t in extracted_tables:
                blocks.append(f"### Page {t['page']} - Table {t['table_index']}")
                md_table = convert_table_to_markdown(t["data"])
                blocks.append(md_table)
                blocks.append("")

        if mode in ["text", "both"] and extracted_text:
            blocks.append("## Raw Document Text\n")
            blocks.append(extracted_text)

        output_content = "\n".join(blocks)

    # 4. Save output or print
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_content)
        print(f"Success! Output written to {output_path}")
    else:
        # Default save next to input file if no output path specified
        fallback_ext = ".json" if output_format == "json" else ".md"
        default_out = pdf_path.with_suffix(fallback_ext)
        with open(default_out, "w", encoding="utf-8") as f:
            f.write(output_content)
        print(f"Success! Output written to default path: {default_out}")


def main():
    parser = argparse.ArgumentParser(
        description="Biotech Business Development PDF Parser - Extract Text and Tables into Markdown/JSON."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to the clinical/scientific PDF document.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to save the output. Defaults to same directory as input with .md/.json extension.",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["text", "tables", "both"],
        default="both",
        help="Extraction target: 'text' (raw text), 'tables' (structured tables), or 'both' (default).",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format: 'markdown' (default) or 'json'.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None

    run_parser(input_path, output_path, args.mode, args.format)


if __name__ == "__main__":
    main()
