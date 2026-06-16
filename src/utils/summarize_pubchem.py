#!/usr/bin/env python3
"""
PubChem BioAssay Summarizer Utility
Parses raw PubChem compound & BioAssay JSON databases and exports clean, readable text summaries.
Ensures UTF-8 encoding.
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Summarize PubChem JSON data")
    parser.add_argument("--input", required=True, help="Path to raw PubChem JSON")
    parser.add_argument("--output", required=True, help="Path to write the report")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON from '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    compound_name = data.get("compound_name", "N/A")
    cid = data.get("cid", "N/A")
    props = data.get("properties", {})
    assays = data.get("assays", {})

    formula = props.get("MolecularFormula", "N/A")
    mw = props.get("MolecularWeight", "N/A")
    smiles = props.get("CanonicalSMILES", "N/A")
    iupac = props.get("IUPACName", "N/A")
    xlogp = props.get("XLogP", "N/A")

    # Process assays
    columns = assays.get("Columns", {}).get("Column", [])
    rows = assays.get("Row", [])

    active_count = 0
    inactive_count = 0
    other_count = 0
    active_assays = []

    # Map column headers to index
    col_map = {col: idx for idx, col in enumerate(columns)}

    outcome_idx = col_map.get("Activity Outcome")
    aid_idx = col_map.get("AID")
    target_gene_idx = col_map.get("Target Gene Symbol") or col_map.get("Target Gene ID")
    value_idx = col_map.get("Activity Value [uM]") or col_map.get("Activity Value")
    type_idx = col_map.get("Activity Type")
    name_idx = col_map.get("Assay Name")

    for row in rows:
        cell = row.get("Cell", [])
        if not cell:
            continue

        outcome = (
            cell[outcome_idx]
            if outcome_idx is not None and outcome_idx < len(cell)
            else "N/A"
        )
        aid = cell[aid_idx] if aid_idx is not None and aid_idx < len(cell) else "N/A"
        target = (
            cell[target_gene_idx]
            if target_gene_idx is not None and target_gene_idx < len(cell)
            else "N/A"
        )
        val = (
            cell[value_idx]
            if value_idx is not None and value_idx < len(cell)
            else "N/A"
        )
        act_type = (
            cell[type_idx] if type_idx is not None and type_idx < len(cell) else "N/A"
        )
        assay_name = (
            cell[name_idx] if name_idx is not None and name_idx < len(cell) else "N/A"
        )

        if outcome == "Active":
            active_count += 1
            if len(active_assays) < 15:  # Capture first 15 active assays
                active_assays.append(
                    {
                        "aid": aid,
                        "target": target,
                        "val": val,
                        "type": act_type,
                        "name": assay_name,
                    }
                )
        elif outcome == "Inactive":
            inactive_count += 1
        else:
            other_count += 1

    total_assays = active_count + inactive_count + other_count
    selectivity_ratio = (active_count / total_assays * 100) if total_assays > 0 else 0

    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("=" * 80 + "\n")
            out.write("PUBCHEM COMPOUND & BIOASSAY SUMMARY REPORT\n")
            out.write(f"Compound Name  : {compound_name.upper()}\n")
            out.write(f"PubChem CID    : {cid}\n")
            out.write("=" * 80 + "\n\n")

            out.write("--- CHEMICAL PROPERTIES ---\n")
            out.write(f"IUPAC Name       : {iupac}\n")
            out.write(f"Molecular Formula: {formula}\n")
            out.write(f"Molecular Weight : {mw} g/mol\n")
            out.write(f"XLogP            : {xlogp}\n")
            out.write(f"Canonical SMILES : {smiles}\n\n")

            out.write("--- BIOASSAY METRICS ---\n")
            out.write(f"Total Assays Screened: {total_assays}\n")
            out.write(f"  Active Assays      : {active_count}\n")
            out.write(f"  Inactive Assays    : {inactive_count}\n")
            out.write(f"  Other/Unspecified  : {other_count}\n")
            out.write(f"Selectivity Index    : {selectivity_ratio:.2f}% active\n\n")

            out.write("--- REPRESENTATIVE ACTIVE TARGETS (SELECTIVITY PROFILE) ---\n")
            if active_assays:
                for idx, assay in enumerate(active_assays, 1):
                    out.write(f"Assay #{idx}: AID {assay['aid']}\n")
                    out.write(f"  Target Gene/ID: {assay['target']}\n")
                    out.write(f"  Activity Value: {assay['val']} {assay['type']}\n")
                    out.write(f"  Assay Name    : {assay['name']}\n\n")
            else:
                out.write("No active assays found in PubChem BioAssay records.\n")

            out.write("=" * 80 + "\n")

        print(f"Successfully generated summary report at: {args.output}")

    except Exception as e:
        print(f"Error writing summary report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
