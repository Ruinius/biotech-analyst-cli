#!/usr/bin/env python3
"""
PubChem BioAssay Sourcing Utility
Queries the PubChem PUG REST API for compound properties and active BioAssay summaries.
"""
import urllib.request
import urllib.parse
import json
import argparse
import sys
import os

def query_pug_rest(path):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/{path}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error querying PubChem PUG REST API ({path}): {e}", file=sys.stderr)
        return None

def fetch_compound_data(name):
    print(f"Resolving compound CID for: '{name}'...")
    cid_data = query_pug_rest(f"compound/name/{urllib.parse.quote(name)}/cids/json")
    if not cid_data or "IdentifierList" not in cid_data or "CID" not in cid_data["IdentifierList"]:
        print(f"Could not resolve compound CID for: '{name}'", file=sys.stderr)
        return None
    
    cid = cid_data["IdentifierList"]["CID"][0]
    print(f"Found CID: {cid}. Fetching chemical properties...")
    
    prop_path = f"compound/cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,IUPACName,XLogP/json"
    prop_data = query_pug_rest(prop_path)
    
    print(f"Fetching BioAssay summary for CID {cid}...")
    assay_path = f"compound/cid/{cid}/assaysummary/json"
    assay_data = query_pug_rest(assay_path)
    
    results = {
        "compound_name": name,
        "cid": cid,
        "properties": prop_data.get("PropertyTable", {}).get("Properties", [{}])[0] if prop_data else {},
        "assays": assay_data.get("Table", {}) if assay_data else {}
    }
    return results

def main():
    parser = argparse.ArgumentParser(description="Query PubChem PUG REST API for BioAssay & Compound Data")
    parser.add_argument("--compound", required=True, help="Compound name (e.g., 'Aspirin' or 'Osemitamab')")
    parser.add_argument("--output", default="tmp/pubchem_out.json", help="Path to save raw JSON")
    
    args = parser.parse_args()
    
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    data = fetch_compound_data(args.compound)
    if data:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved PubChem data to: {args.output}")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
