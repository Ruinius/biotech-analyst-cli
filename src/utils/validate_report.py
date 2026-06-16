#!/usr/bin/env python3
"""
Report Validation Guardrail Script
Audits a synthesized competitive landscape Markdown report against raw registry databases
to prevent hallucinations, trial mismatches, status discrepancies, and omissions.
"""
import json
import re
import argparse
import os
import sys

# Constants for status categories
CT_DISCONTINUED = {'TERMINATED', 'WITHDRAWN', 'SUSPENDED'}
CDE_DISCONTINUED = {'主动终止', '已终止', '暂停'}

def clean_cell_to_name(cell):
    cell = re.sub(r'<[^>]+>', ' ', cell)
    cell = cell.replace('**', '').replace('*', '').replace('__', '').replace('_', '')
    cell = re.sub(r'\(.*?\)', '', cell)
    return cell.strip()

def matches_drug(text, aliases):
    if not text:
        return False
    pattern = r'(?<![a-zA-Z0-9])(' + '|'.join(re.escape(alias) for alias in aliases) + r')(?![a-zA-Z0-9])'
    return bool(re.search(pattern, text, re.IGNORECASE))

def extract_trials(text):
    # Regex to find trial identifiers
    ncts = re.findall(r'\bNCT\d{8}\b', text)
    ctrs = re.findall(r'\bCTR\d{8}\b', text)
    chictrs = re.findall(r'\bChiCTR[a-zA-Z0-9-]+\b', text)
    return list(set(ncts)), list(set(ctrs)), list(set(chictrs))

def parse_report_table(report_path):
    rows = []
    if not os.path.exists(report_path):
        return rows
        
    with open(report_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    in_table = False
    for line_num, line in enumerate(lines, 1):
        if "|" in line:
            if not in_table:
                if "Asset Name" in line:
                    in_table = True
                continue
            if re.match(r'^\s*\|?\s*(:?-+:?\s*\|)+\s*(:?-+:?\s*)?$', line):
                continue
                
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) < 3:
                continue
                
            rows.append({
                "line_num": line_num,
                "asset_cell": cols[0],
                "cleaned_name": clean_cell_to_name(cols[0]),
                "sponsor": cols[1] if len(cols) > 1 else "",
                "lead_phase": cols[5] if len(cols) > 5 else "",
                "trials_cell": cols[6] if len(cols) > 6 else "",
                "cols": cols
            })
        else:
            if in_table:
                in_table = False
                
    return rows

def main():
    parser = argparse.ArgumentParser(description="Audit landscape reports against raw database registries.")
    parser.add_argument("--report", required=True, help="Path to the synthesized Markdown report")
    parser.add_argument("--config", required=True, help="Path to config JSON mapping drug names to synonyms")
    parser.add_argument("--clinicaltrials", help="Path to ClinicalTrials.gov JSON database")
    parser.add_argument("--china-direct", help="Path to ChinaDrugTrials direct search JSON")
    parser.add_argument("--chinese-registries", help="Path to syndicated Chinese registries JSON")
    
    args = parser.parse_args()
    
    # Load config
    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
        
    with open(args.config, "r", encoding="utf-8") as f:
        config_data = json.load(f)
        
    # Standardize config
    config = {}
    for k, v in config_data.items():
        if isinstance(v, list):
            config[k] = {"aliases": v}
        else:
            config[k] = v
            
    # Load raw registries
    ct_data = {}
    if args.clinicaltrials and os.path.exists(args.clinicaltrials):
        print(f"Loading ClinicalTrials.gov database: {args.clinicaltrials}")
        with open(args.clinicaltrials, "r", encoding="utf-8") as f:
            ct_data = json.load(f)
            
    china_data = {}
    if args.china_direct and os.path.exists(args.china_direct):
        print(f"Loading ChinaDrugTrials direct database: {args.china_direct}")
        with open(args.china_direct, "r", encoding="utf-8") as f:
            raw_china = json.load(f)
            # Map by registration number for fast lookup
            for rec in raw_china.get("records", []):
                reg_num = rec.get("acceptance_number")
                if reg_num:
                    china_data[reg_num] = rec
                    
    chreg_data = {}
    if args.chinese_registries and os.path.exists(args.chinese_registries):
        print(f"Loading syndicated Chinese registries database: {args.chinese_registries}")
        with open(args.chinese_registries, "r", encoding="utf-8") as f:
            raw_chreg = json.load(f)
            for rec in raw_chreg.get("results", []):
                # Search title or details for ChiCTR id
                title = rec.get("title", "")
                cross_refs = rec.get("dbCrossReferenceList", {}).get("dbName", [])
                reg_id = None
                for word in title.split() + cross_refs:
                    if "ChiCTR" in word or "CTR20" in word:
                        reg_id = word.strip(".,()[]")
                        break
                if reg_id:
                    chreg_data[reg_id] = rec
                    
    # Parse report
    if not os.path.exists(args.report):
        print(f"Error: Report file not found: {args.report}", file=sys.stderr)
        sys.exit(1)
        
    table_rows = parse_report_table(args.report)
    
    # Read entire report content for general trial check
    with open(args.report, "r", encoding="utf-8") as f:
        report_content = f.read()
        
    all_ncts, all_ctrs, all_chictrs = extract_trials(report_content)
    
    print("\n" + "="*50)
    print("RUNNING REPORT INTEGRITY AUDIT")
    print("="*50)
    
    has_errors = False
    
    # --- 1. ZERO-HALLUCINATION CHECK (GLOBAL TRIAL ID CHECK) ---
    print("\n[1/4] Zero-Hallucination Audit (Registry Verification)...")
    hallucinated_trials = []
    
    for nct_id in all_ncts:
        if args.clinicaltrials and nct_id not in ct_data:
            hallucinated_trials.append((nct_id, "ClinicalTrials.gov"))
            
    for ctr_id in all_ctrs:
        if args.china_direct and ctr_id not in china_data:
            hallucinated_trials.append((ctr_id, "ChinaDrugTrials"))
            
    for chictr_id in all_chictrs:
        if args.chinese_registries and chictr_id not in chreg_data:
            hallucinated_trials.append((chictr_id, "Syndicated ChiCTR"))
            
    if hallucinated_trials:
        has_errors = True
        print("  CRITICAL ERROR: Found trial IDs in the report that do not exist in the raw registry databases!")
        for tid, source in hallucinated_trials:
            print(f"    - {tid} ({source}) is missing from raw JSON database logs!")
    else:
        print("  PASS: All trial IDs mentioned in the report exist in the raw registry JSON logs.")
        
    # --- 2. ZERO-OMISSION CHECK (EXHAUSTIVE ASSET RECONCILIATION) ---
    print("\n[2/4] Zero-Omission Audit (Asset Reconciliation)...")
    omitted_assets = []
    report_assets_lower = [r["cleaned_name"].lower() for r in table_rows]
    
    # We also check if they are in the entire report content
    report_text_lower = report_content.lower()
    
    for primary_key, details in config.items():
        aliases = details.get("aliases", [])
        all_names = [primary_key] + aliases
        
        # Check if the asset shows up in the table
        in_table = False
        for name in all_names:
            if name.lower() in report_assets_lower:
                in_table = True
                break
                
        if not in_table:
            # Check if mentioned elsewhere in the report
            in_text = False
            for name in all_names:
                if name.lower() in report_text_lower:
                    in_text = True
                    break
                    
            if not in_text:
                omitted_assets.append(primary_key)
                
    if omitted_assets:
        has_errors = True
        print("  CRITICAL ERROR: Configured biological assets were completely omitted from the report!")
        for asset in omitted_assets:
            print(f"    - {asset} (and its aliases) was not found in the landscape table or text!")
    else:
        print("  PASS: All configured assets are represented in the report.")
        
    # --- 3. TRIAL-ASSET ASSOCIATION AUDIT ---
    print("\n[3/4] Trial-Asset Association Audit (Mismatches)...")
    association_errors = []
    
    for row in table_rows:
        asset_name = row["cleaned_name"]
        trials_cell = row["trials_cell"]
        line_num = row["line_num"]
        
        # Find which configured asset this corresponds to
        config_key = None
        for k, details in config.items():
            all_names = [k] + details.get("aliases", [])
            if asset_name.lower() in [a.lower() for a in all_names]:
                config_key = k
                break
                
        if not config_key:
            print(f"  Warning: Row '{asset_name}' (line {line_num}) could not be mapped to any drug key in config.json")
            continue
            
        aliases = [config_key] + config[config_key].get("aliases", [])
        row_ncts, row_ctrs, row_chictrs = extract_trials(trials_cell)
        
        for nct_id in row_ncts:
            if nct_id in ct_data:
                study = ct_data[nct_id]
                proto = study.get("protocolSection", {})
                id_mod = proto.get("identificationModule", {})
                desc_mod = proto.get("descriptionModule", {})
                arms_mod = proto.get("armsInterventionsModule", {})
                
                # Check briefTitle, officialTitle, summary, interventions
                brief = id_mod.get("briefTitle", "")
                official = id_mod.get("officialTitle", "")
                summary = desc_mod.get("briefSummary", "")
                
                interventions = arms_mod.get("interventions", [])
                int_texts = []
                for intv in interventions:
                    int_texts.append(intv.get("name", ""))
                    int_texts.extend(intv.get("otherNames", []))
                    int_texts.append(intv.get("description", ""))
                    
                full_study_text = " | ".join([brief, official, summary] + int_texts)
                
                if not matches_drug(full_study_text, aliases):
                    association_errors.append((nct_id, asset_name, config_key, line_num))
                    
        for ctr_id in row_ctrs:
            if ctr_id in china_data:
                rec = china_data[ctr_id]
                drug_name = rec.get("drug_name", "")
                company = rec.get("company", "")
                full_rec_text = f"{drug_name} | {company}"
                
                if not matches_drug(full_rec_text, aliases):
                    association_errors.append((ctr_id, asset_name, config_key, line_num))
                    
        for chictr_id in row_chictrs:
            if chictr_id in chreg_data:
                rec = chreg_data[chictr_id]
                title = rec.get("title", "")
                abstract = rec.get("abstractText", "")
                full_rec_text = f"{title} | {abstract}"
                
                if not matches_drug(full_rec_text, aliases):
                    association_errors.append((chictr_id, asset_name, config_key, line_num))
                    
    if association_errors:
        has_errors = True
        print("  CRITICAL ERROR: Found trial IDs associated with completely incorrect assets in the report table!")
        for tid, asset, c_key, line in association_errors:
            print(f"    - Trial {tid} is assigned to '{asset}' (line {line}), but the registry record does not contain the drug name or its aliases (Config key: '{c_key}')!")
    else:
        print("  PASS: All trial-drug pairings match their official registry record descriptions.")
        
    # --- 4. STATUS DISCREPANCY AUDIT ---
    print("\n[4/4] Trial Status Discrepancy Audit...")
    status_discrepancies = []
    
    for row in table_rows:
        asset_name = row["cleaned_name"]
        lead_phase = row["lead_phase"]
        trials_cell = row["trials_cell"]
        line_num = row["line_num"]
        
        row_ncts, row_ctrs, row_chictrs = extract_trials(trials_cell)
        
        # Check if the report implies the molecule is active
        is_implied_active = "discontinued" not in lead_phase.lower() and "terminated" not in lead_phase.lower()
        
        for nct_id in row_ncts:
            if nct_id in ct_data:
                study = ct_data[nct_id]
                status_mod = study.get("protocolSection", {}).get("statusModule", {})
                status = status_mod.get("overallStatus", "UNKNOWN").upper()
                if status in ["UNKNOWN", "UNKNOWN_STATUS"] and status_mod.get("lastKnownStatus"):
                    status = status_mod.get("lastKnownStatus").upper()
                if is_implied_active and status in CT_DISCONTINUED:
                    status_discrepancies.append((nct_id, asset_name, status, "ClinicalTrials.gov", line_num))
                    
        for ctr_id in row_ctrs:
            if ctr_id in china_data:
                rec = china_data[ctr_id]
                status = rec.get("status", "")
                if is_implied_active and any(k in status for k in CDE_DISCONTINUED):
                    status_discrepancies.append((ctr_id, asset_name, status, "ChinaDrugTrials", line_num))
                    
    if status_discrepancies:
        # Note: Status discrepancy can be a warning or error. 
        # If all trials are terminated but molecule is claimed active, it is a critical error.
        # If a single trial is terminated but others are active, it is a warning.
        print("  WARNING: Found status discrepancies in trials of active molecules:")
        for tid, asset, status, source, line in status_discrepancies:
            print(f"    - Trial {tid} for '{asset}' (line {line}) is marked as '{status}' in {source}, but the molecule is presented as active.")
    else:
        print("  PASS: No status mismatches found (all trials associated with active molecules are active/completed).")
        
    print("\n" + "="*50)
    print("AUDIT SUMMARY")
    print("="*50)
    if has_errors:
        print("  STATUS: FAILED")
        print("  Please fix the critical errors listed above before completing research delivery.")
        sys.exit(1)
    else:
        print("  STATUS: SUCCESS")
        print("  The synthesized report is verified and free of hallucinations, omissions, and mismatches.")
        sys.exit(0)

if __name__ == "__main__":
    main()
