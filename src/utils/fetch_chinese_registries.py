#!/usr/bin/env python3
"""
Chinese Registries (WHO ICTRP & ChiCTR) Sourcing Utility
Queries WHO ICTRP syndicated trial records and ChiCTR/CTR publications via Europe PMC.
Integrates the BD English-to-Mandarin Translation Protocol.
"""
import urllib.request
import urllib.parse
import json
import argparse
import sys
import os

# BD Translation Table from workflows/market_scanning.md
TRANSLATION_MAP = {
    "phase 1": "I期临床试验",
    "phase 2": "II期临床试验",
    "first-in-human": "首次进入人体",
    "dose escalation": "剂量递增",
    "dose expansion": "剂量扩展",
    "breakthrough therapy": "突破性治疗",
    "sponsor": "申请人",
    "investigator-initiated trial": "研究者发起",
    "iit": "研究者发起"
}

def translate_term(term):
    term_lower = term.lower()
    return TRANSLATION_MAP.get(term_lower, term)

def fetch_chinese_trials(term, limit=50):
    translated = translate_term(term)
    query_str = f'("ChiCTR" OR "CTR20" OR REGISTRY:"ChiCTR" OR REGISTRY:"Chictr") AND ("{term}" OR "{translated}")'
    print(f"Querying Europe PMC/WHO ICTRP for: '{term}' / '{translated}' (limit: {limit})...")
    
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
            print(f"Error querying Chinese registries syndicates at cursor {cursor_mark}: {e}", file=sys.stderr)
            break
            
    return results[:limit]

def main():
    parser = argparse.ArgumentParser(description="Query Chinese Clinical Trial Registries via WHO syndicated systems")
    parser.add_argument("--term", required=True, help="Search term (e.g., drug name or target)")
    parser.add_argument("--output", default="tmp/chinese_registries_out.json", help="Path to save raw JSON")
    parser.add_argument("--limit", type=int, default=50, help="Maximum results to return")
    
    args = parser.parse_args()
    
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    results = fetch_chinese_trials(args.term, limit=args.limit)
    if not results:
        print(f"Error: No clinical trials found for '{args.term}' inside WHO syndicated Chinese registries.", file=sys.stderr)
        sys.exit(1)
        
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "term": args.term,
            "translated_term": translate_term(args.term),
            "results": results
        }, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved Chinese trial registry data to: {args.output}")

if __name__ == "__main__":
    main()
