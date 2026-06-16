#!/usr/bin/env python3
"""
Global Patent & IP Summarizer Utility
Parses raw Lens/Dimensions patent JSON databases and exports clean, readable text summaries.
Ensures UTF-8 encoding.
"""
import json
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Summarize Global IP & Patent JSON data")
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
            out.write(f"GLOBAL PATENT & INTELLECTUAL PROPERTY (IP) REPORT\n")
            out.write(f"Query Target Term: {term.upper()}\n")
            out.write(f"Total IP Records : {len(results)}\n")
            out.write("="*80 + "\n\n")
            
            for idx, res in enumerate(results, 1):
                title = res.get("title", "No patent title available.")
                inventors = res.get("authorString", "N/A")
                pub_year = res.get("pubYear", "N/A")
                source = res.get("source", "N/A")
                patent_id = res.get("pmid", "N/A")
                doi = res.get("doi", "N/A")
                abstract = res.get("abstractText", "No patent abstract details available.")
                
                out.write(f"--- PATENT APPLICATION #{idx}: {patent_id} ---\n")
                out.write(f"Title       : {title}\n")
                out.write(f"Patent Office: {source}\n")
                out.write(f"Pub Year    : {pub_year}\n")
                out.write(f"Inventor(s) : {inventors}\n")
                out.write(f"DOI/Ref Link: https://doi.org/{doi}\n\n")
                out.write("Abstract / Claims Summary:\n")
                out.write(abstract[:1500] + ("..." if len(abstract) > 1500 else "") + "\n")
                out.write("-" * 80 + "\n\n")
                
            out.write("="*80 + "\n")
            
        print(f"Successfully generated summary report at: {args.output}")
        
    except Exception as e:
        print(f"Error writing summary report: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
