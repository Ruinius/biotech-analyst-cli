#!/usr/bin/env python3
"""
openFDA Drug Label & Event Summarizer Utility
Parses raw openFDA JSON databases and exports clean, readable text summaries.
Ensures UTF-8 encoding.
"""
import json
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Summarize openFDA JSON data")
    parser.add_argument("--input", required=True, help="Path to raw openFDA JSON")
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
        
    drug_name = data.get("drug_name", "N/A")
    label = data.get("label", {})
    events = data.get("events", [])
    
    # Label data parsing
    brand_name = ", ".join(label.get("openfda", {}).get("brand_name", ["N/A"]))
    generic_name = ", ".join(label.get("openfda", {}).get("generic_name", ["N/A"]))
    manufacturer = ", ".join(label.get("openfda", {}).get("manufacturer_name", ["N/A"]))
    
    boxed_warning = "\n".join(label.get("boxed_warning", ["None listed."]))
    indications = "\n".join(label.get("indications_and_usage", ["None listed."]))
    adverse_reactions = "\n".join(label.get("adverse_reactions", ["None listed."]))
    
    # Events data parsing
    event_summaries = []
    serious_count = 0
    deaths_count = 0
    
    for idx, ev in enumerate(events, 1):
        seriousness = ev.get("serious", "N/A")
        if seriousness == "1":
            serious_count += 1
            
        reactions = [r.get("reactionmeddrapt", "N/A") for r in ev.get("patient", {}).get("reaction", [])]
        reactions_str = ", ".join(reactions)
        
        # Check for death outcome
        outcomes = ev.get("seriousnessdeath", "0")
        if outcomes == "1":
            deaths_count += 1
            
        patient_sex = ev.get("patient", {}).get("patientsex", "N/A")
        sex_map = {"1": "Male", "2": "Female", "0": "Unknown"}
        sex_str = sex_map.get(patient_sex, "Unknown")
        
        age = ev.get("patient", {}).get("patientonsetage", "N/A")
        age_unit = ev.get("patient", {}).get("patientonsetageunit", "")
        unit_map = {"800": "Decades", "801": "Years", "802": "Months", "803": "Weeks", "804": "Days", "805": "Hours"}
        age_str = f"{age} {unit_map.get(age_unit, 'Years')}" if age != "N/A" else "N/A"
        
        if len(event_summaries) < 5: # Capture up to 5 events
            event_summaries.append({
                "idx": idx,
                "safety_report": ev.get("safetyreportid", "N/A"),
                "reactions": reactions_str,
                "serious": "Yes" if seriousness == "1" else "No",
                "death": "Yes" if outcomes == "1" else "No",
                "demographics": f"Age: {age_str}, Sex: {sex_str}"
            })
            
    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("="*80 + "\n")
            out.write(f"OPENFDA DRUG SAFETY & LABEL SUMMARY REPORT\n")
            out.write(f"Query Drug Name: {drug_name.upper()}\n")
            out.write(f"Brand Name     : {brand_name}\n")
            out.write(f"Generic Name   : {generic_name}\n")
            out.write(f"Manufacturer   : {manufacturer}\n")
            out.write("="*80 + "\n\n")
            
            out.write("--- FDA APPROVED INDICATIONS & USAGE ---\n")
            out.write(indications[:1500] + ("..." if len(indications) > 1500 else "") + "\n\n")
            
            out.write("--- BOXED WARNINGS (CRITICAL TOXICITIES) ---\n")
            out.write(boxed_warning[:1500] + ("..." if len(boxed_warning) > 1500 else "") + "\n\n")
            
            out.write("--- ADVERSE REACTIONS / LABLED TOXICITIES ---\n")
            out.write(adverse_reactions[:1500] + ("..." if len(adverse_reactions) > 1500 else "") + "\n\n")
            
            out.write("--- RECENT SAFETY EVENTS & EVENTS AUDIT ---\n")
            out.write(f"Total Adverse Event Records Fetched: {len(events)}\n")
            out.write(f"  Serious Events Count             : {serious_count}\n")
            out.write(f"  Fatal Events (Death) Count       : {deaths_count}\n\n")
            
            out.write("Representative Patient Cases:\n")
            if event_summaries:
                for ev in event_summaries:
                    out.write(f"Case #{ev['idx']} (ID: {ev['safety_report']})\n")
                    out.write(f"  Reactions   : {ev['reactions']}\n")
                    out.write(f"  Serious     : {ev['serious']}\n")
                    out.write(f"  Fatal Outcome: {ev['death']}\n")
                    out.write(f"  Patient Info: {ev['demographics']}\n\n")
            else:
                out.write("No adverse event cases found in recent openFDA registries.\n")
                
            out.write("="*80 + "\n")
            
        print(f"Successfully generated summary report at: {args.output}")
        
    except Exception as e:
        print(f"Error writing summary report: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
