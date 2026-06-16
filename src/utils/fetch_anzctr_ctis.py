#!/usr/bin/env python3
"""
EU CTIS & Australian ANZCTR Sourcing Utility
Queries Europe PMC API for clinical trial records from EUCTR, CTIS, and ANZCTR.
"""
import urllib.request
import urllib.parse
import json
import argparse
import sys
import os

def fetch_anzctr_ctis_trials(term, limit=50):
    query_str = f'(REGISTRY:"ANZCTR" OR REGISTRY:"EUCTR" OR REGISTRY:"CTIS" OR SRC:"ANZCTR") AND {term}'
    print(f"Querying Europe PMC for trials matching: '{term}' in EU/Australian registries (limit: {limit})...")
    
    results = []
    cursor_mark = "*"
    page_size = min(limit, 100) # Fetch up to 100 per page to be efficient
    
    while len(results) < limit:
        encoded_query = urllib.parse.quote(query_str)
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={encoded_query}&format=json&pageSize={page_size}&cursorMark={cursor_mark}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            page_results = data.get("resultList", {}).get("result", [])
            if not page_results:
                break
                
            results.extend(page_results)
            
            next_cursor = data.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            cursor_mark = next_cursor
            
        except Exception as e:
            print(f"Error querying Europe PMC at cursor {cursor_mark}: {e}", file=sys.stderr)
            break
            
    return results[:limit]

def main():
    parser = argparse.ArgumentParser(description="Query Europe PMC for EU CTIS & Australian ANZCTR clinical trials")
    parser.add_argument("--term", required=True, help="Search term (e.g., drug name or target)")
    parser.add_argument("--output", default="tmp/anzctr_ctis_out.json", help="Path to save raw JSON")
    parser.add_argument("--limit", type=int, default=50, help="Maximum results to return")
    
    args = parser.parse_args()
    
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    results = fetch_anzctr_ctis_trials(args.term, limit=args.limit)
    if not results:
        print(f"Error: No clinical trials found for '{args.term}' inside EU CTIS / Australian ANZCTR registries.", file=sys.stderr)
        sys.exit(1)
        
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"term": args.term, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved ANZCTR/CTIS raw JSON to: {args.output}")

if __name__ == "__main__":
    main()
