#!/usr/bin/env python3
"""
ClinicalTrials.gov Trial Summarizer Utility
Parses raw JSON trial databases and exports clean, readable text summaries.
Ensures UTF-8 encoding is used to prevent Windows console or encoding crashes.
"""
import json
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Summarize ClinicalTrials.gov JSON data")
    parser.add_argument("--input", required=True, help="Path to the fetched trials JSON database")
    parser.add_argument("--output", required=True, help="Path to write the text summary report")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            trials = json.load(f)
    except Exception as e:
        print(f"Error reading JSON from '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)
        
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("="*80 + "\n")
            out.write(f"CLINICAL TRIALS SUMMARY REPORT\n")
            out.write(f"Source Database: {args.input}\n")
            out.write(f"Total Trials Evaluated: {len(trials)}\n")
            out.write("="*80 + "\n\n")
            
            for idx, (nct_id, study) in enumerate(trials.items(), 1):
                proto = study.get("protocolSection", {})
                id_mod = proto.get("identificationModule", {})
                status_mod = proto.get("statusModule", {})
                sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
                design_mod = proto.get("designModule", {})
                elig_mod = proto.get("eligibilityModule", {})
                
                brief_title = id_mod.get("briefTitle", "N/A")
                official_title = id_mod.get("officialTitle", "N/A")
                status = status_mod.get("overallStatus", "N/A")
                
                start_date_dict = status_mod.get("startDateStruct", {})
                start_date = start_date_dict.get("date", "N/A")
                
                enrollment_dict = status_mod.get("enrollmentStruct", {})
                enrollment = enrollment_dict.get("value", "N/A")
                enrollment_type = enrollment_dict.get("type", "N/A")
                
                sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "N/A")
                phases = design_mod.get("phases", [])
                phase_str = ", ".join(phases) if phases else "N/A"
                
                out.write(f"--- STUDY #{idx}: {nct_id} ---\n")
                out.write(f"Brief Title   : {brief_title}\n")
                out.write(f"Official Title: {official_title}\n")
                out.write(f"Sponsor       : {sponsor}\n")
                out.write(f"Status        : {status}\n")
                out.write(f"Phase         : {phase_str}\n")
                out.write(f"Start Date    : {start_date}\n")
                out.write(f"Enrollment    : {enrollment} ({enrollment_type})\n\n")
                
                criteria = elig_mod.get("eligibilityCriteria", "No criteria listed.")
                out.write("Eligibility Criteria:\n")
                out.write(criteria + "\n")
                out.write("-" * 80 + "\n\n")
                
        print(f"Successfully generated summary report at: {args.output}")
        
    except Exception as e:
        print(f"Error writing summary report: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
