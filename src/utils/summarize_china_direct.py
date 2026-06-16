#!/usr/bin/env python3
"""
Direct NMPA CDE Summarizer Utility
Parses raw CDE search JSON databases and exports clean, readable text summaries.
Ensures UTF-8 encoding.
"""
import json
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Summarize NMPA CDE direct search JSON data")
    parser.add_argument("--input", required=True, help="Path to raw JSON")
    parser.add_argument("--output", required=True, help="Path to write the report")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON from '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)
        
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    term = data.get("term", "N/A")
    source = data.get("source", "N/A")
    records = data.get("records", [])
    
    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("="*80 + "\n")
            out.write(f"NMPA CDE DIRECT REGISTRY & IND ACCEPTANCE REPORT\n")
            out.write(f"Query Target Term: {term.upper()}\n")
            out.write(f"Sourcing Method  : {source}\n")
            out.write(f"Total IND Records: {len(records)}\n")
            out.write("="*80 + "\n\n")
            
            for idx, rec in enumerate(records, 1):
                acc_num = rec.get("acceptance_number", "N/A")
                drug_name = rec.get("drug_name", "N/A")
                company = rec.get("company", "N/A")
                date = rec.get("date", "N/A")
                status = rec.get("status", "N/A")
                bt = rec.get("breakthrough_therapy", "No")
                
                out.write(f"--- CDE IND RECORD #{idx}: {acc_num} ---\n")
                out.write(f"Drug Name             : {drug_name}\n")
                out.write(f"Applicant Company     : {company}\n")
                out.write(f"Filing/Acceptance Date: {date}\n")
                out.write(f"Regulatory Status     : {status}\n")
                out.write(f"Breakthrough Therapy  : {bt}\n")
                out.write("-" * 80 + "\n\n")
                
            out.write("="*80 + "\n")
            
        print(f"Successfully generated summary report at: {args.output}")
        
    except Exception as e:
        print(f"Error writing summary report: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
