#!/usr/bin/env python3
"""
ClinicalTrials.gov API v2 Query Utility
Designed for Windows and PowerShell compatibility. Bypasses fcntl Unix dependencies.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def fetch_studies(term, limit=50):
    results = []
    page_token = None
    page_size = min(limit, 100)  # Fetch up to 100 per page to be efficient

    print(f"Querying ClinicalTrials.gov for: '{term}' (limit: {limit})...")

    while len(results) < limit:
        url = f"https://clinicaltrials.gov/api/v2/studies?query.term={urllib.parse.quote(term)}&pageSize={page_size}"
        if page_token:
            url += f"&pageToken={page_token}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))

            studies = data.get("studies", [])
            if not studies:
                break

            results.extend(studies)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        except Exception as e:
            print(
                f"Error querying ClinicalTrials.gov API for '{term}' at page token {page_token}: {e}",
                file=sys.stderr,
            )
            break

    return {"studies": results[:limit]}


def fetch_by_nct(nct_id):
    url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
    print(f"Retrieving trial details for: {nct_id}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except Exception as e:
        print(f"Error retrieving trial {nct_id}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Query ClinicalTrials.gov API v2 (Windows & Unix Compatible)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--terms",
        nargs="+",
        help="One or more search terms (e.g., drug name or target)",
    )
    group.add_argument(
        "--nct-ids", nargs="+", help="One or more ClinicalTrials.gov NCT identifiers"
    )
    parser.add_argument(
        "--output",
        default="tmp/trials_out.json",
        help="Path to write the raw JSON results",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of studies to fetch per term",
    )

    args = parser.parse_args()
    results = {}

    # Ensure output directory exists
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    if args.terms:
        for term in args.terms:
            data = fetch_studies(term, limit=args.limit)
            if data and "studies" in data:
                for study in data["studies"]:
                    nct_id = (
                        study.get("protocolSection", {})
                        .get("identificationModule", {})
                        .get("nctId")
                    )
                    if nct_id:
                        results[nct_id] = study
        print(f"Total matching studies found: {len(results)}")

    elif args.nct_ids:
        for nct_id in args.nct_ids:
            study = fetch_by_nct(nct_id)
            if study:
                results[nct_id] = study
        print(f"Total trials retrieved: {len(results)}")

    if results:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Raw JSON data successfully saved to: {args.output}")
    else:
        print("No studies found matching the search criteria.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
