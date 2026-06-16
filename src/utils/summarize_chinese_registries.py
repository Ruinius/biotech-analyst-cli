#!/usr/bin/env python3
"""
Chinese Registries (WHO ICTRP & ChiCTR) Summarizer Utility
Parses raw Chinese trial registry JSON databases and exports clean, readable text summaries.
Ensures UTF-8 encoding.
"""
import json
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Summarize Chinese Registries JSON data")
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
    translated = data.get("translated_term", "N/A")
    results = data.get("results", [])
    
    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("="*80 + "\n")
            out.write(f"CHINESE TRIAL REGISTRY REPORT (WHO ICTRP & CHICTR)\n")
            out.write(f"Query English Term : {term.upper()}\n")
            out.write(f"Mandarin Equivalent: {translated}\n")
            out.write(f"Total Trials Found : {len(results)}\n")
            out.write("="*80 + "\n\n")
            
            for idx, res in enumerate(results, 1):
                title = res.get("title", "No title available.")
                authors = res.get("authorString", "N/A")
                pub_year = res.get("pubYear", "N/A")
                source = res.get("source", "N/A")
                pmid = res.get("pmid", "N/A")
                doi = res.get("doi", "N/A")
                
                # Extract CTR or ChiCTR identifier
                registry_id = "N/A"
                cross_refs = res.get("dbCrossReferenceList", {}).get("dbName", [])
                cross_refs_str = ", ".join(cross_refs) if cross_refs else "N/A"
                
                for word in title.split() + cross_refs:
                    if "CTR20" in word or "ChiCTR" in word:
                        registry_id = word.strip(".,()[]")
                        break
                        
                abstract = res.get("abstractText", "No abstract details available.")
                
                out.write(f"--- REGISTRY RECORD #{idx}: {registry_id} ---\n")
                out.write(f"Title       : {title}\n")
                out.write(f"Registry/DB : {source} ({cross_refs_str})\n")
                out.write(f"Year        : {pub_year}\n")
                out.write(f"Author(s)   : {authors}\n")
                out.write(f"DOI/Link    : https://doi.org/{doi} (PMID: {pmid})\n\n")
                out.write("Abstract / Registry Description:\n")
                out.write(abstract[:1500] + ("..." if len(abstract) > 1500 else "") + "\n")
                out.write("-" * 80 + "\n\n")
                
            out.write("="*80 + "\n")
            
        print(f"Successfully generated summary report at: {args.output}")
        
    except Exception as e:
        print(f"Error writing summary report: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
