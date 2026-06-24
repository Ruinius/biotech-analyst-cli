#!/usr/bin/env python3
"""
openFDA Drug Label & Event Sourcing Utility
Queries the openFDA API for drug labels and recent adverse events.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def query_openfda(endpoint, query_str, limit=5):
    encoded_query = urllib.parse.quote(query_str, safe="+=&:")
    url = f"https://api.fda.gov/{endpoint}.json?search={encoded_query}&limit={limit}"

    print(f"Querying openFDA {endpoint} with: {query_str}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error querying openFDA {endpoint}: {e}", file=sys.stderr)
        return None


def fetch_drug_data(drug_name):
    # Query Drug Labels
    label_query = (
        f'openfda.brand_name:"{drug_name}" OR openfda.generic_name:"{drug_name}"'
    )
    label_data = query_openfda("drug/label", label_query, limit=1)

    # Query Drug Adverse Events
    event_query = f'patient.drug.medicinalproduct:"{drug_name}"'
    event_data = query_openfda("drug/event", event_query, limit=10)

    results = {
        "drug_name": drug_name,
        "label": label_data.get("results", [{}])[0]
        if label_data and "results" in label_data
        else {},
        "events": event_data.get("results", [])
        if event_data and "results" in event_data
        else [],
    }
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Query openFDA API for Drug Labels & Events"
    )
    parser.add_argument(
        "--drug", required=True, help="Drug brand or generic name (e.g., 'Aspirin')"
    )
    parser.add_argument(
        "--output", default="tmp/openfda_out.json", help="Path to save raw JSON"
    )

    args = parser.parse_args()

    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    data = fetch_drug_data(args.drug)
    if data:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved openFDA data to: {args.output}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
