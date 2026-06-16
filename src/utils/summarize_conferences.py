#!/usr/bin/env python3
"""
Conference Libraries Summarizer Utility
Parses raw Europe PMC conference search data and exports clean, readable text summaries.
Ensures UTF-8 encoding.
"""
import json
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Summarize Conference JSON data")
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
    results = data.get("results", [])
    
    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("="*80 + "\n")
            out.write(f"MAJOR CONFERENCE ABSTRACTS & PRESENTATIONS REPORT\n")
            out.write(f"Query Target Term: {term.upper()}\n")
            out.write(f"Total Abstracts Identified: {len(results)}\n")
            out.write("="*80 + "\n\n")
            
            for idx, res in enumerate(results, 1):
                title = res.get("title", "No title available.")
                authors = res.get("authorString", "N/A")
                pub_year = res.get("pubYear", "N/A")
                journal = res.get("journalInfo", {}).get("journal", {}).get("title", "N/A")
                pmid = res.get("pmid", "N/A")
                doi = res.get("doi", "N/A")
                
                # Deduce conference
                conf = "ASCO/AACR/ASH/EHA Sourced"
                title_lower = title.lower()
                journal_lower = journal.lower()
                if "asco" in title_lower or "clinical oncology" in journal_lower:
                    conf = "ASCO (American Society of Clinical Oncology)"
                elif "aacr" in title_lower or "cancer research" in journal_lower:
                    conf = "AACR (American Association for Cancer Research)"
                elif "ash" in title_lower or "blood" in journal_lower:
                    conf = "ASH (American Society of Hematology)"
                elif "eha" in title_lower or "european hematological" in journal_lower:
                    conf = "EHA (European Hematology Association)"
                
                abstract = res.get("abstractText", "No abstract text available.")
                
                out.write(f"--- ABSTRACT #{idx}: {conf} [{pub_year}] ---\n")
                out.write(f"Title     : {title}\n")
                out.write(f"Journal   : {journal}\n")
                out.write(f"Author(s) : {authors}\n")
                out.write(f"DOI/Link  : https://doi.org/{doi} (PMID: {pmid})\n\n")
                out.write("Abstract Text / Clinical Summary:\n")
                out.write(abstract[:1500] + ("..." if len(abstract) > 1500 else "") + "\n")
                out.write("-" * 80 + "\n\n")
                
            out.write("="*80 + "\n")
            
        print(f"Successfully generated summary report at: {args.output}")
        
    except Exception as e:
        print(f"Error writing summary report: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
