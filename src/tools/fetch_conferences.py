#!/usr/bin/env python3
"""
Conference Libraries Sourcing Utility
Queries Europe PMC API for conference abstracts and papers (ASCO, AACR, ASH, EHA).
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def fetch_conference_abstracts(term, limit=50):
    venues = '(ASCO OR AACR OR ASH OR EHA OR "Clinical Oncology" OR "Cancer Research" OR "Hematology")'
    query_str = f'{venues} AND "{term}"'
    print(
        f"Querying Europe PMC for conference abstracts matching: '{term}' (limit: {limit})..."
    )

    results = []
    cursor_mark = "*"
    page_size = min(limit, 100)  # Fetch up to 100 per page to be efficient

    while len(results) < limit:
        encoded_query = urllib.parse.quote(query_str)
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={encoded_query}&format=json&pageSize={page_size}&cursorMark={cursor_mark}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))

            page_results = data.get("resultList", {}).get("result", [])
            if not page_results:
                break

            results.extend(page_results)

            next_cursor = data.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            cursor_mark = next_cursor

        except Exception as e:
            print(
                f"Error querying Europe PMC for conferences at cursor {cursor_mark}: {e}",
                file=sys.stderr,
            )
            break

    return results[:limit]


def main():
    parser = argparse.ArgumentParser(
        description="Query Europe PMC for oncology/hematology conference abstracts"
    )
    parser.add_argument(
        "--term", required=True, help="Search term (e.g., drug name or target)"
    )
    parser.add_argument(
        "--output", default="tmp/conferences_out.json", help="Path to save raw JSON"
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Maximum results to return"
    )

    args = parser.parse_args()

    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    results = fetch_conference_abstracts(args.term, limit=args.limit)
    if not results:
        print(
            f"Error: No conference abstracts found for '{args.term}' inside major meeting libraries.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(
            {"term": args.term, "results": results}, f, indent=2, ensure_ascii=False
        )
    print(f"Successfully saved conference raw JSON to: {args.output}")


if __name__ == "__main__":
    main()
