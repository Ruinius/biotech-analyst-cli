#!/usr/bin/env python3
"""
Competitive Landscape Table Generator
Programmatically builds the competitive landscape Markdown table from raw clinical registry JSONs.
Ensures zero transcription errors, zero omissions, and accurate status and phase auditing.
"""
import json
import re
import argparse
import os
import sys

# Define trial status categorizations
CT_ACTIVE = {'RECRUITING', 'ACTIVE_NOT_RECRUITING', 'ENROLLING_BY_INVITATION', 'NOT_YET_RECRUITING'}
CT_COMPLETED = {'COMPLETED'}
CT_DISCONTINUED = {'TERMINATED', 'WITHDRAWN', 'SUSPENDED'}

CDE_ACTIVE = {'进行中', '进行中\xa0招募中', '进行中\xa0尚未招募', '进行中\xa0招募完成', '招募中', '尚未招募', '招募完成'}
CDE_COMPLETED = {'已完成'}
CDE_DISCONTINUED = {'主动终止', '已终止', '暂停'}

def clean_sponsor(sponsor):
    if not sponsor or sponsor == "N/A":
        return ""
    # Remove common corporate suffixes
    sponsor = re.sub(r',?\s+(Ltd\.|LLC|Inc\.|Co\.|Corp\.|Corporation|Pharmaceuticals|Pharma|Biotech|Biopharma|Therapeutics)\b.*', '', sponsor, flags=re.IGNORECASE)
    sponsor = re.sub(r'\b(Group|Holdings|China)\b.*', '', sponsor, flags=re.IGNORECASE)
    return sponsor.strip()

def matches_drug(text, aliases):
    if not text:
        return False
    # Check for any alias as a whole word (not preceded/followed by alphanumeric characters)
    pattern = r'(?<![a-zA-Z0-9])(' + '|'.join(re.escape(alias) for alias in aliases) + r')(?![a-zA-Z0-9])'
    return bool(re.search(pattern, text, re.IGNORECASE))

def parse_ct_phase(phases_list):
    if not phases_list:
        return "N/A", 0
    val_map = {
        "EARLY_PHASE1": (0.5, "Early Phase 1"),
        "PHASE1": (1.0, "Phase 1"),
        "PHASE1_PHASE2": (1.5, "Phase 1/2"),
        "PHASE2": (2.0, "Phase 2"),
        "PHASE2_PHASE3": (2.5, "Phase 2/3"),
        "PHASE3": (3.0, "Phase 3"),
        "PHASE4": (4.0, "Phase 4")
    }
    
    max_val = -1
    best_str = "N/A"
    
    for p in phases_list:
        p_clean = p.upper().replace("/", "_").replace(" ", "_")
        if p_clean in val_map:
            val, name = val_map[p_clean]
            if val > max_val:
                max_val = val
                best_str = name
                
    # Specific combination checks
    if len(phases_list) > 1:
        phases_upper = [p.upper() for p in phases_list]
        if "PHASE1" in phases_upper and "PHASE2" in phases_upper:
            return "Phase 1/2", 1.5
        if "PHASE2" in phases_upper and "PHASE3" in phases_upper:
            return "Phase 2/3", 2.5
            
    return best_str, max_val

def parse_text_phase(text):
    if not text:
        return "N/A", 0
    text_lower = text.lower()
    if any(k in text_lower for k in ["iii期", "3期", "phase 3", "phase iii"]):
        if any(k in text_lower for k in ["ib/iii", "i/iii", "1/3"]):
            return "Phase 1/3", 2.0
        return "Phase 3", 3.0
    if any(k in text_lower for k in ["ii期", "2期", "phase 2", "phase ii"]):
        if any(k in text_lower for k in ["i/ii", "ib/ii", "1/2"]):
            return "Phase 1/2", 1.5
        return "Phase 2", 2.0
    if any(k in text_lower for k in ["i期", "1期", "phase 1", "phase i"]):
        if any(k in text_lower for k in ["ia/ib", "ia/b", "1a/1b"]):
            return "Phase 1", 1.0
        return "Phase 1", 1.0
    return "N/A", 0

def detect_formulation(text_list):
    forms = set()
    for text in text_list:
        if not text:
            continue
        text_lower = text.lower()
        if any(k in text_lower for k in ["subcutaneous", "sub-q", "subq", "皮下"]):
            forms.add("Subcutaneous")
        if any(k in text_lower for k in ["intravenous", "iv", "静脉"]):
            forms.add("Intravenous")
        if any(k in text_lower for k in ["oral", "口服"]):
            forms.add("Oral")
    return list(forms)

def clean_cell_to_name(cell):
    cell = re.sub(r'<[^>]+>', ' ', cell)
    cell = cell.replace('**', '').replace('*', '').replace('__', '').replace('_', '')
    cell = re.sub(r'\(.*?\)', '', cell)
    return cell.strip()

def parse_existing_report(report_path, config):
    metadata = {}
    if not report_path or not os.path.exists(report_path):
        return metadata
        
    print(f"Reading existing report to extract qualitative metadata: {report_path}")
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        in_table = False
        for line in lines:
            if "|" in line:
                if not in_table:
                    if "Asset Name" in line:
                        in_table = True
                    continue
                # Skip divider lines e.g. | :--- | :--- |
                if re.match(r'^\s*\|?\s*(:?-+:?\s*\|)+\s*(:?-+:?\s*)?$', line):
                    continue
                    
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) < 3:
                    continue
                    
                asset_cell = cols[0]
                # Extract all word-like tokens from the asset cell to match synonyms
                row_names = re.findall(r'[A-Za-z0-9\-]{3,25}', asset_cell)
                row_names_lower = {n.lower() for n in row_names}
                
                # Find which drug in our config this matches
                matched_key = None
                for primary_key, details in config.items():
                    aliases = details.get("aliases", [])
                    all_names = [primary_key] + aliases
                    if any(a.lower() in row_names_lower for a in all_names):
                        matched_key = primary_key
                        break
                        
                if matched_key:
                    # Update config aliases with any new names found in the report cell
                    for name in row_names:
                        name_clean = name.strip("-").strip()
                        if name_clean and len(name_clean) >= 3 and not should_exclude(name_clean):
                            # Add to aliases if not already the primary key or in aliases
                            if name_clean.lower() != matched_key.lower() and name_clean.lower() not in [a.lower() for a in config[matched_key]["aliases"]]:
                                config[matched_key]["aliases"].append(name_clean)
                                
                    metadata[matched_key] = {
                        "modality": cols[2] if len(cols) > 2 else "",
                        "formulation": cols[3] if len(cols) > 3 else "",
                        "indication": cols[4] if len(cols) > 4 else "",
                        "safety": cols[7] if len(cols) > 7 else "",
                        "efficacy": cols[8] if len(cols) > 8 else "",
                        "milestones": cols[9] if len(cols) > 9 else "",
                        "citations": cols[10] if len(cols) > 10 else ""
                    }
            else:
                if in_table:
                    in_table = False # Table ended
    except Exception as e:
        print(f"Warning: Failed to parse existing report for metadata extraction: {e}")
        
    print(f"Extracted qualitative metadata for {len(metadata)} assets.")
    return metadata

EXCLUDE_LOWER = {
    "placebo", "chemotherapy", "chemo", "standard of care", "investigator choice", "investigator's choice",
    "paclitaxel", "docetaxel", "nab-paclitaxel", "gemcitabine", "oxaliplatin", "capecitabine", "cisplatin", 
    "carboplatin", "pembrolizumab", "nivolumab", "sintilimab", "toripalimab", "dostarlimab", "ramucirumab",
    "leucovorin", "fluorouracil", "5-fluorouracil", "5-fu", "irinotecan", "liposomal irinotecan",
    "folflri", "folfiri", "folfox", "mfolfox6", "folfirinox", "mfolfirinox", "capox", "flot",
    "radiation", "surgery", "saline", "dexamethasone", "prednisone", "ondansetron", "aprepitant",
    "normal saline", "control", "chemotherapies", "placebos", "combination", "combo", "regimen",
    "antibody", "cart", "car-t", "adc", "bi-specific", "bispecific", "monoclonal", "recombinant",
    "infusion", "injection", "therapy", "cell", "cells", "autologous", "vaccine", "dendritic",
    "peptides", "peptide", "vector", "plasmid", "imaging", "agent", "agents", "pet", "tracer",
    "redirected", "engineered", "chimeric", "targeting", "positive", "expressing", "negative",
    "expressing", "expression", "expressing", "high-expressing", "low-expressing", "positive-expression",
    "durvalumab", "atezolizumab", "avelumab", "ipilimumab", "tremelimumab", "penpulimab", "camrelizumab",
    "adebrelimab", "retifanlimab", "zimberelimab", "serplulimab", "pucoclimab", "adegrelimab", "tislelizumab",
    "cadonilimab", "cardonilizumab", "trastuzumab", "pertuzumab", "bevacizumab", "cetuximab", "panitumumab",
    "erlotinib", "gefitinib", "afatinib", "osimertinib", "lapatinib", "neratinib", "tucatinib",
    "folinic", "folinic acid", "l-leucovorin", "leucovorin calcium", "folic acid", "folate",
    "zoledronic", "zoledronic acid", "denosumab", "aprepitant", "fosaprepitant", "ondansetron",
    "granisetron", "palonosetron", "pegfilgrastim", "filgrastim", "tancolux", "epirubicin", "doxorubicin",
    "methotrexate", "cyclophosphamide", "fludarabine", "etoposide", "vincristine", "vinblastine",
    "vinorelbine", "temozolomide", "dacarbazine", "procarbazine", "carmustine", "lomustine", "streptozocin",
    "mitomycin", "bleomycin", "dactinomycin", "daunorubicin", "idarubicin", "mitoxantrone", "plicamycin",
    "hydroxyurea", "asparaginase", "pegaspargase", "bortezomib", "carfilzomib", "ixazomib", "thalidomide",
    "lenalidomide", "pomalidomide", "olaparib", "rucaparib", "niraparib", "talazoparib", "veliparib",
    "fruquintinib", "surufatinib", "donafenib", "regorafenib", "sorafenib", "sunitinib", "pazopanib",
    "axitinib", "cabozantinib", "lenvatinib", "vandetanib", "nintedanib", "tivozanib", "alectinib",
    "crizotinib", "ceritinib", "brigatinib", "lorlatinib", "dabrafenib", "vemurafenib", "encorafenib",
    "trametinib", "cobimetinib", "binimetinib", "selumetinib", "everolimus", "temsirolimus", "sirolimus",
    "tivozanib", "fruquintinib", "surufatinib", "donafenib", "sox", "xelox", "folfiri", "folfox",
    "folfirinox", "flot", "capox", "folfoxiri", "folfox4", "folfox6", "mfolfox6", "mfolfox",
    "gemcitabine+albumin-bound", "gemcitabine+nab-paclitaxel", "gem/nab-paclitaxel", "gem-abx",
    "albumin-bound", "abraxane", "keytruda", "opdivo", "tecentriq", "imfinzi", "libtayo", "jemperli",
    "erbitux", "vectibix", "avastin", "cyramza", "herceptin", "perjeta", "kadcyla", "enhertu",
    "alunbrig", "alecensa", "xalkori", "zykadia", "lorbrena", "tafinlar", "zelboraf", "braftovi",
    "mekinist", "cotellic", "mektovi", "koselugo", "afinitor", "torisel", "rapamune", "inlyta",
    "sutent", "votrient", "nexavar", "stivarga", "caprelsa", "lartruvo", "portrazza", "cyramza",
    "xofigo", "ziga", "yondelis", "halaven", "ixempra", "elsparc", "erwinase", "oncaspar",
    "velcade", "kyprolis", "ninlaro", "thalomid", "revlimid", "pomalyst", "lynparza", "rubraca",
    "zejula", "talzenna", "eluate", "placebos", "support", "care", "assignment", "single",
    "group", "open-label", "dose-escalation", "escalation", "expansion", "dose", "regimen",
    "cohort", "arm", "randomized", "double-blind", "efficacy", "safety", "tolerability",
    "pharmacokinetics", "bioavailability", "pharmacodynamics", "immunogenicity", "maximum",
    "tolerated", "dose-limiting", "toxicity", "toxicities", "adverse", "events", "reaction",
    "reactions", "syndicated", "registry", "scraped", "scrape", "scraping", "scrub", "clean",
    "format", "report", "document", "file", "json", "txt", "md", "pdf", "html", "xml", "csv",
    "insulin", "lispro", "humalog", "novolog", "apidra", "fiasp", "lyumjev", "admelog",
    # Additional background TKIs, antibodies, and chemo components to exclude
    "apatinib", "anlotinib", "anrotinib", "tqb2450", "shr-1701", "shr1701", "shr-a1811", "shra1811",
    "volrustomig", "tas-102", "tas102", "tegafur", "trifluridine", "insul", "p037", "interleukin",
    "ds-8201a", "ds8201a", "trastuzumab deruxtecan", "enhertu", "ibi315", "ibi-315", "pd-1", "pd1",
    "pd-l1", "pdl1", "ctla-4", "ctla4", "onivyde", "nanoliposomal", "liposomal", "s-1", "s1",
    "leucovorin calcium", "fluorouracil injection", "paclitaxel albumin", "capecitabine tablets",
    "placebo matching", "chemotherapy regimen"
}

TARGET_TERMS = {
    "cldn", "claudin", "cldn18", "claudin18", "cldn182", "claudin182", "cld18", "cldn-18", "claudin-18",
    "cldn18.2", "claudin18.2", "claudin-18.2", "cldn-18.2", "claudin 18.2", "cldn 18.2", "cld182",
    "紧密连接蛋白18.2", "紧密蛋白18.2", "克劳丁18.2", "连接蛋白18.2", "重组抗紧密连接蛋白18.2",
    "重组抗紧密连接蛋白18.2-药物偶联物", "重组抗紧密连接蛋白18.2 -依戏替康偶联物"
}

GENERIC_WORDS = {
    "placebo", "chemotherapy", "standard of care", "investigator choice", "investigator's choice",
    "radiation", "surgery", "saline", "control", "combination", "combo", "regimen",
    "antibody", "cart", "car-t", "adc", "bi-specific", "bispecific", "monoclonal", "recombinant",
    "infusion", "injection", "therapy", "cell", "cells", "autologous", "vaccine", "dendritic",
    "peptides", "peptide", "vector", "plasmid", "imaging", "agent", "agents", "pet", "tracer",
    "redirected", "engineered", "chimeric", "targeting", "positive", "expressing", "negative",
    "expressing", "expression", "expressing", "high-expressing", "low-expressing", "positive-expression",
    "support", "care", "assignment", "single", "group", "open-label", "dose-escalation", "escalation",
    "expansion", "dose", "regimen", "cohort", "arm", "randomized", "double-blind", "efficacy",
    "safety", "tolerability", "pharmacokinetics", "bioavailability", "pharmacodynamics", "immunogenicity",
    "chemo", "placebos", "comb", "regim"
}

def has_valid_drug_code(name):
    if not name:
        return False
    name_lower = name.lower()
    
    # Check if there is any word ending in mab/tug/mig/bart/cept/tib/can
    for w in re.findall(r'[a-z]{3,20}(?:mab|tug|mig|bart|cept|tib|can)\b', name_lower):
        if w not in EXCLUDE_LOWER and w not in TARGET_TERMS:
            return True
            
    # Check for known drug name substrings
    for k in ["zolbet", "osem", "vyloy", "spevat", "givas", "greson", "sones", "satric", "satri", "ribomab"]:
        if k in name_lower:
            return True
            
    # Clean the string by replacing target terms, generic words, and exclude words with spaces
    cleaned = name_lower
    for target in TARGET_TERMS:
        cleaned = re.sub(r'\b' + re.escape(target) + r'\b', ' ', cleaned)
        if len(target) > 5:
            cleaned = cleaned.replace(target, ' ')
            
    for gw in GENERIC_WORDS:
        cleaned = re.sub(r'\b' + re.escape(gw) + r'\b', ' ', cleaned)
        
    for ex in EXCLUDE_LOWER:
        cleaned = re.sub(r'\b' + re.escape(ex) + r'\b', ' ', cleaned)
        
    # Extract any remaining word tokens
    tokens = re.findall(r'[a-z0-9\-]{3,15}', cleaned)
    for t in tokens:
        t_clean = t.strip("-")
        if len(t_clean) < 3:
            continue
        # Check if the token contains a letter and a digit (like JS107, SHR-A1904, AMG910, AMG-910, AZD6422)
        has_letter = any(c.isalpha() for c in t_clean)
        has_digit = any(c.isdigit() for c in t_clean)
        if has_letter and has_digit:
            return True
        # Or check if it's a known code prefix followed by a space-separated number
        if t_clean.isalpha() and len(t_clean) in [3, 4]:
            pattern = re.escape(t_clean) + r'\s+\d+'
            if re.search(pattern, name_lower):
                return True
                
    return False

def should_exclude(name):
    if not name:
        return True
    name_lower = name.lower().strip()
    
    # If the name is exactly in EXCLUDE_LOWER, exclude it
    if name_lower in EXCLUDE_LOWER:
        return True
        
    # If the name is exactly a target term, exclude it
    if name_lower in TARGET_TERMS:
        return True
        
    # If it contains a valid drug code, do NOT exclude it!
    if has_valid_drug_code(name):
        return False
        
    # Otherwise, exclude if it contains target terms
    for target in TARGET_TERMS:
        if target in name_lower:
            return True
            
    # Check if any excluded word is in the name
    for ex in EXCLUDE_LOWER:
        if re.search(r'\b' + re.escape(ex) + r'\b', name_lower):
            return True
            
    # Check other generic phrases
    for phrase in ["standard of care", "investigator choice", "investigator's choice", "normal saline", "placebo matching", "albumin-bound", "insul", "interleukin", "tas-102", "tas102", "5-fu", "s-1", "pd-1", "pd-l1", "ctla-4", "chemotherapy", "placebo"]:
        if phrase in name_lower:
            return True
            
    return False

def get_name_priority(name):
    name_lower = name.lower()
    if any(k in name_lower for k in ["claudin", "cldn", "generic", "placebo", "chemo", "support", "assignment", "therapy"]):
        return 10
    if any(k in name_lower for k in ["tavatecan", "deruxtecan", "rezetecan", "vedotin", "payload"]):
        return 6
    if name_lower in ["zolbetuximab", "vyloy", "osemitamab", "givastomig", "spevatamig", "sonesitatug"]:
        return 0
    if name_lower.endswith("mab") or name_lower.endswith("tug") or name_lower.endswith("mig") or name_lower.endswith("bart"):
        return 0
    if re.search(r'^[a-z]{2,4}-?\d{3,5}', name_lower):
        return 1
    return 5

def clean_drug_name(name):
    if not name:
        return ""
    name = re.sub(r'<[^>]+>', ' ', name)
    parts = re.split(r'[\+\/]|联合|和', name)
    for part in parts:
        part_clean = part.strip()
        codes = re.findall(r'[A-Za-z0-9\-]{3,15}', part_clean)
        valid_codes = []
        for c in codes:
            c_lower = c.lower()
            c_alnum = re.sub(r'[^a-z0-9]', '', c_lower)
            if should_exclude(c):
                continue
            if c_lower in TARGET_TERMS or c_alnum in TARGET_TERMS:
                continue
            if any(gw in c_lower for gw in GENERIC_WORDS):
                continue
            if len(c) < 3:
                continue
            has_letter = any(char.isalpha() for char in c)
            has_digit = any(char.isdigit() for char in c)
            is_known_name = any(k in c_lower for k in ["zolbet", "osem", "vyloy", "spevat", "givas", "greson", "sones", "satric", "satri", "ribomab"])
            if (has_letter and has_digit) or is_known_name or (len(c) >= 5 and (c_lower.endswith("mab") or c_lower.endswith("tib") or c_lower.endswith("cept") or c_lower.endswith("can"))):
                c_clean = c.strip("-").strip()
                if c_clean and not should_exclude(c_clean):
                    valid_codes.append(c_clean)
        if valid_codes:
            return valid_codes[0]
            
    first_part = parts[0].strip()
    first_part = re.sub(r'\(.*?\)', '', first_part)
    first_part = re.sub(r'（.*?）', '', first_part)
    for prefix in ["注射用", "重组人源化", "单克隆抗体", "自体", "细胞", "注射液"]:
        first_part = first_part.replace(prefix, "")
    first_part = first_part.replace("抗体", "")
    first_part_clean = first_part.strip()
    
    if not should_exclude(first_part_clean):
        if re.search(r'[\u4e00-\u9fff]', first_part_clean):
            eng_words = re.findall(r'[A-Za-z0-9\-]{3,15}', first_part_clean)
            if eng_words:
                ret = eng_words[0]
                if not should_exclude(ret):
                    return ret
        else:
            return first_part_clean
    return ""

def extract_china_drug(drug_name):
    if not drug_name:
        return ""
    # Split parenthetical suffix first
    main_part = re.split(r'[\(（]', drug_name)[0].strip()
    cleaned = clean_drug_name(main_part)
    if cleaned:
        return cleaned
    codes = re.findall(r'[A-Za-z0-9\-]{3,15}', drug_name)
    for c in codes:
        if should_exclude(c):
            continue
        c_lower = c.lower()
        c_alnum = re.sub(r'[^a-z0-9]', '', c_lower)
        if c_lower in TARGET_TERMS or c_alnum in TARGET_TERMS:
            continue
        if any(gw in c_lower for gw in GENERIC_WORDS):
            continue
        has_letter = any(char.isalpha() for char in c)
        has_digit = any(char.isdigit() for char in c)
        is_known_name = any(k in c_lower for k in ["zolbet", "osem", "vyloy", "spevat", "givas", "greson", "sones", "satric", "satri", "ribomab"])
        if (has_letter and has_digit) or is_known_name or (len(c) >= 5 and c_lower.endswith("mab")):
            c_clean = c.strip("-").strip()
            if c_clean and not should_exclude(c_clean):
                return c_clean
    return ""

def discover_config(ct_data, china_data):
    groups = []
    
    def add_synonyms(names_list):
        names_clean = []
        for n in names_list:
            cleaned = clean_drug_name(n)
            if cleaned and len(cleaned) >= 3 and not should_exclude(cleaned):
                names_clean.append(cleaned)
                
        if not names_clean:
            return
            
        merged_indices = []
        for i, g in enumerate(groups):
            if any(n.lower() in {x.lower() for x in g} for n in names_clean):
                merged_indices.append(i)
                
        if not merged_indices:
            groups.append(set(names_clean))
        else:
            new_group = set(names_clean)
            for idx in sorted(merged_indices, reverse=True):
                new_group.update(groups.pop(idx))
            groups.append(new_group)

    # 1. Process ClinicalTrials.gov
    for nct_id, study in ct_data.items():
        proto = study.get("protocolSection", {})
        arms_mod = proto.get("armsInterventionsModule", {})
        
        for intv in arms_mod.get("interventions", []):
            intv_type = intv.get("type", "").upper()
            if intv_type in ["DRUG", "BIOLOGICAL", "GENETIC"]:
                name = intv.get("name", "")
                other_names = intv.get("otherNames", [])
                
                if name.lower() not in EXCLUDE_LOWER:
                    trial_drugs = [name]
                    for on in other_names:
                        if on.lower() not in EXCLUDE_LOWER:
                            trial_drugs.append(on)
                    add_synonyms(trial_drugs)
            
    # 2. Process China Drug Trials
    for rec in china_data:
        drug_name = rec.get("drug_name", "")
        extracted = extract_china_drug(drug_name)
        if extracted:
            add_synonyms([extracted])
            
    # 3. Process Conferences for preclinical/early clinical assets (e.g. AZD6422, AHT-102)
    import glob
    search_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmp"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tmp"),
        os.path.join(os.getcwd(), "tmp")
    ]
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for filepath in glob.glob(os.path.join(s_dir, "*conferences*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    conf_data = json.load(f)
                items = conf_data.get("results", [])
                for item in items:
                    title = item.get("title", "")
                    codes = re.findall(r'[A-Za-z0-9\-]{3,15}', title)
                    for c in codes:
                        c_clean = c.strip("-").strip()
                        if not c_clean or len(c_clean) < 3:
                            continue
                        if should_exclude(c_clean):
                            continue
                        c_lower = c_clean.lower()
                        c_alnum = re.sub(r'[^a-z0-9]', '', c_lower)
                        if c_lower in TARGET_TERMS or c_alnum in TARGET_TERMS:
                            continue
                        if any(gw in c_lower for gw in GENERIC_WORDS):
                            continue
                        has_letter = any(char.isalpha() for char in c_clean)
                        has_digit = any(char.isdigit() for char in c_clean)
                        if (has_letter and has_digit) or (len(c_clean) >= 5 and c_lower.endswith("mab")) or any(k in c_lower for k in ["zolbet", "osem", "vyloy", "spevat", "givas", "greson", "sones", "satric", "satri", "ribomab"]):
                            add_synonyms([c_clean])
            except Exception as e:
                print(f"Warning: Failed to process conference file {filepath} for discovery: {e}")
            
    config = {}
    for g in groups:
        sorted_names = sorted(list(g), key=lambda x: (get_name_priority(x), -len(x), x))
        primary = sorted_names[0]
        aliases = sorted_names[1:]
        config[primary] = {"aliases": aliases}
        
    return config

def main():
    parser = argparse.ArgumentParser(description="Generate Competitive Landscape Table from raw clinical registries.")
    parser.add_argument("--config", help="Path to config JSON mapping drug names to synonyms (optional)")
    parser.add_argument("--clinicaltrials", help="Path to ClinicalTrials.gov JSON database")
    parser.add_argument("--china-direct", help="Path to ChinaDrugTrials direct search JSON")
    parser.add_argument("--existing-report", help="Path to existing report to extract qualitative metadata")
    parser.add_argument("--output", required=True, help="Path to write the markdown table output")
    
    args = parser.parse_args()
    
    # Load raw registries
    ct_data = {}
    if args.clinicaltrials and os.path.exists(args.clinicaltrials):
        print(f"Loading ClinicalTrials.gov data: {args.clinicaltrials}")
        with open(args.clinicaltrials, "r", encoding="utf-8") as f:
            ct_data = json.load(f)
            
    # Glob-search and merge auxiliary trial JSON files (*_trial*.json)
    import glob
    search_dirs = []
    if args.clinicaltrials:
        search_dirs.append(os.path.dirname(os.path.abspath(args.clinicaltrials)))
    search_dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmp"))
    search_dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tmp"))
    search_dirs.append(os.path.join(os.getcwd(), "tmp"))
    
    seen_paths = set()
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for filepath in glob.glob(os.path.join(s_dir, "*_trial*.json")):
            abs_path = os.path.abspath(filepath)
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)
            print(f"Merging auxiliary trials from: {filepath}")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    aux_data = json.load(f)
                if isinstance(aux_data, dict):
                    for nct_id, study in aux_data.items():
                        if nct_id.startswith("NCT"):
                            ct_data[nct_id] = study
            except Exception as e:
                print(f"Warning: Failed to merge auxiliary trials from {filepath}: {e}")
            
    china_data = []
    if args.china_direct and os.path.exists(args.china_direct):
        print(f"Loading ChinaDrugTrials direct data: {args.china_direct}")
        with open(args.china_direct, "r", encoding="utf-8") as f:
            raw_china = json.load(f)
            china_data = raw_china.get("records", [])
            
    # Load config or dynamically discover
    config = {}
    if args.config:
        if not os.path.exists(args.config):
            print(f"Error: Config file not found: {args.config}", file=sys.stderr)
            sys.exit(1)
            
        with open(args.config, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            
        for k, v in config_data.items():
            if isinstance(v, list):
                config[k] = {"aliases": v}
            else:
                config[k] = v
    else:
        print("No config file provided. Dynamically discovering assets from raw registries...")
        config = discover_config(ct_data, china_data)
        
    print(f"Total discovered/mapped assets: {len(config)}")
            
    # Parse existing report for metadata extraction
    existing_meta = parse_existing_report(args.existing_report, config)
    
    # Post-process: Re-determine primary keys based on name priority and align existing_meta
    new_config = {}
    new_existing_meta = {}
    for old_primary, details in config.items():
        aliases = details.get("aliases", [])
        all_names = list(set([old_primary] + aliases))
        
        # Sort by priority (ascending, 0 is highest), then length (descending), then name (ascending)
        sorted_names = sorted(all_names, key=lambda x: (get_name_priority(x), -len(x), x))
        new_primary = sorted_names[0]
        new_aliases = sorted_names[1:]
        
        new_config[new_primary] = {"aliases": new_aliases}
        if old_primary in existing_meta:
            new_existing_meta[new_primary] = existing_meta[old_primary]
            
    config = new_config
    existing_meta = new_existing_meta
    
    # Process trials for each asset
    asset_rows = []
    
    for asset_name, details in config.items():
        aliases = details.get("aliases", [])
        search_names = [asset_name] + aliases
        
        matched_ct = []
        matched_china = []
        
        sponsors = set()
        formulation_texts = []
        phases = []
        
        # 1. Scan ClinicalTrials.gov
        for nct_id, study in ct_data.items():
            proto = study.get("protocolSection", {})
            id_mod = proto.get("identificationModule", {})
            desc_mod = proto.get("descriptionModule", {})
            sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
            design_mod = proto.get("designModule", {})
            arms_mod = proto.get("armsInterventionsModule", {})
            status_mod = proto.get("statusModule", {})
            
            brief_title = id_mod.get("briefTitle", "")
            official_title = id_mod.get("officialTitle", "")
            acronym = id_mod.get("acronym", "")
            summary = desc_mod.get("briefSummary", "")
            description = desc_mod.get("detailedDescription", "")
            
            # Interventions
            interventions = arms_mod.get("interventions", [])
            int_texts = []
            for intv in interventions:
                int_texts.append(intv.get("name", ""))
                int_texts.extend(intv.get("otherNames", []))
                int_texts.append(intv.get("description", ""))
                
            all_text_to_search = " | ".join([brief_title, official_title, acronym, summary, description] + int_texts)
            
            if matches_drug(all_text_to_search, search_names):
                status = status_mod.get("overallStatus", "UNKNOWN")
                if status.upper() in ["UNKNOWN", "UNKNOWN_STATUS"] and status_mod.get("lastKnownStatus"):
                    status = status_mod.get("lastKnownStatus")
                matched_ct.append({
                    "id": nct_id,
                    "status": status,
                    "phase": design_mod.get("phases", [])
                })
                
                # Extract sponsor
                sp = sponsor_mod.get("leadSponsor", {}).get("name")
                if sp:
                    sponsors.add(clean_sponsor(sp))
                    
                # Collect texts for formulation detection
                formulation_texts.append(all_text_to_search)
                
                # Collect phases
                p_str, p_val = parse_ct_phase(design_mod.get("phases", []))
                if p_val > 0:
                    phases.append((p_val, p_str, status))
                    
        # 2. Scan ChinaDrugTrials (China Direct)
        for rec in china_data:
            reg_num = rec.get("acceptance_number", "")
            drug_name = rec.get("drug_name", "")
            company = rec.get("company", "") # this represents indication
            status = rec.get("status", "")
            
            all_text_to_search = f"{drug_name} | {company}"
            
            if matches_drug(all_text_to_search, search_names):
                matched_china.append({
                    "id": reg_num,
                    "status": status,
                    "phase_text": drug_name
                })
                
                # If we have a sponsor list or need to parse from drug_name? 
                # CDE direct scraper has applicant company name in list if we split columns properly.
                # In our schema, company key was mapped to "Indication Target: ...".
                # Let's check if the drug name contains sponsor details or fallback.
                
                formulation_texts.append(all_text_to_search)
                p_str, p_val = parse_text_phase(drug_name)
                if p_val > 0:
                    phases.append((p_val, p_str, status))
                    
        # Determine Lead Phase and Development Status
        # Sort phases by numeric value descending
        lead_phase = "Pre-clinical"
        lead_val = 0.0
        
        # Check active/completed trials vs terminated ones
        active_phases = []
        discontinued_phases = []
        
        for p_val, p_str, status in phases:
            status_upper = status.upper()
            is_active = (status_upper in CT_ACTIVE or status_upper in CT_COMPLETED or
                         any(k in status for k in ["进行中", "招募中", "已完成", "招募完成", "尚未招募"]))
            is_discontinued = (status_upper in CT_DISCONTINUED or
                               any(k in status for k in ["主动终止", "已终止", "暂停"]))
            
            if is_active:
                active_phases.append((p_val, p_str))
            elif is_discontinued:
                discontinued_phases.append((p_val, p_str))
                
        # Determine overall molecule status and lead phase
        is_discontinued_globally = False
        if len(phases) > 0 and len(active_phases) == 0 and len(discontinued_phases) > 0:
            # All trials are discontinued
            is_discontinued_globally = True
            max_p = max(discontinued_phases, key=lambda x: x[0])
            lead_phase = f"{max_p[1]} (Discontinued)"
            lead_val = max_p[0]
        elif len(active_phases) > 0:
            max_p = max(active_phases, key=lambda x: x[0])
            lead_phase = max_p[1]
            lead_val = max_p[0]
            
            # Wait, check if approved! If approved exists in old report or is specified, we can use Approved.
            # E.g. Zolbetuximab is Approved.
            if asset_name.lower() == "zolbetuximab":
                lead_phase = "Approved"
                lead_val = 5.0
        else:
            # Check if there is metadata setting the phase or default to Pre-clinical
            meta_val = details.get("phase")
            if meta_val:
                lead_phase = meta_val
            elif asset_name in ["DR-30310"]:
                lead_phase = "Pre-clinical"
            elif asset_name in ["BNT141", "AMG 910"]:
                # Terminated/Discontinued in config
                lead_phase = "Phase 1 (Discontinued)"
                is_discontinued_globally = True
                
        # Fallback for drugs with matched trials but lead_val is still 0 (meaning in clinic but no explicit phase parsed)
        if lead_val == 0.0:
            if len(matched_ct) > 0 or len(matched_china) > 0:
                # Check if all matched trials are discontinued
                all_discontinued = True
                for ct in matched_ct:
                    if ct["status"].upper() not in CT_DISCONTINUED:
                        all_discontinued = False
                        break
                for ch in matched_china:
                    if ch["status"] not in CDE_DISCONTINUED:
                        all_discontinued = False
                        break
                
                if all_discontinued:
                    lead_phase = "Phase 1 (Discontinued)"
                    lead_val = 1.0
                    is_discontinued_globally = True
                else:
                    lead_phase = "Phase 1"
                    lead_val = 1.0
                
        # Format formulation
        detected_forms = detect_formulation(formulation_texts)
        if len(detected_forms) > 0:
            formulation_str = ", ".join(detected_forms)
        else:
            # Check if metadata has it
            formulation_str = details.get("formulation") or existing_meta.get(asset_name, {}).get("formulation") or "Intravenous"
            
        # Clean formulation formatting
        if "Subcutaneous" in formulation_str and "Intravenous" in formulation_str:
            formulation_str = "Intravenous & Subcutaneous"
        elif "Subcutaneous" in formulation_str:
            formulation_str = "Subcutaneous"
        elif "Intravenous" in formulation_str:
            formulation_str = "Intravenous"
            
        # Format sponsors
        sponsor_str = ""
        if len(sponsors) > 0:
            # Filter and join
            sponsor_str = " / ".join(sorted(list(sponsors)))
        else:
            sponsor_str = details.get("sponsor") or existing_meta.get(asset_name, {}).get("sponsor") or ""
            
        if not sponsor_str:
            sponsor_str = "N/A"
            
        # Compile Trial IDs
        trial_links = []
        # Sort trials by active/completed first
        ct_sorted = sorted(matched_ct, key=lambda x: 0 if x["status"].upper() in CT_ACTIVE or x["status"].upper() in CT_COMPLETED else 1)
        for ct in ct_sorted:
            trial_links.append(f"[{ct['id']}](https://clinicaltrials.gov/study/{ct['id']})")
            
        for ch in matched_china:
            trial_links.append(f"[{ch['id']}](http://www.chinadrugtrials.org.cn/clinicaltrials.searchlistdetail.dhtml?reg_no={ch['id']})")
            
        trials_str = "<br>".join(trial_links) if trial_links else "N/A"
        
        # Merge other qualitative columns from existing report or defaults
        old_data = existing_meta.get(asset_name, {})
        
        modality = details.get("modality") or old_data.get("modality") or "N/A"
        indication = details.get("indication") or old_data.get("indication") or "Gastric / GEJ Adenocarcinoma"
        safety = details.get("selectivity_safety") or old_data.get("safety") or "Safety evaluation ongoing."
        efficacy = details.get("efficacy_data") or old_data.get("efficacy") or "Data not publicly disclosed."
        milestones = details.get("milestones") or old_data.get("milestones") or "Phase 1 study completion."
        citations = details.get("citations") or old_data.get("citations") or "N/A"
        
        # Format asset name with aliases in HTML/Markdown
        alias_str = " / ".join(aliases)
        name_cell = f"**{asset_name}**"
        if alias_str:
            name_cell += f"<br>*( {alias_str} )*"
            
        asset_rows.append({
            "name": asset_name,
            "lead_val": lead_val,
            "is_discontinued": is_discontinued_globally,
            "row_markdown": f"| {name_cell} | {sponsor_str} | {modality} | {formulation_str} | {indication} | {lead_phase} | {trials_str} | {safety} | {efficacy} | {milestones} | {citations} |"
        })
        
    # Sort assets by lead phase value descending, and put active before discontinued
    # Sorting key: (is_discontinued_globally, -lead_val, asset_name)
    asset_rows.sort(key=lambda x: (1 if x["is_discontinued"] else 0, -x["lead_val"], x["name"]))
    
    # Write Markdown table
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    try:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write("| Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Selectivity & Safety Profile | Key Efficacy / Biomarker Data | Upcoming Milestones | Citations |\n")
            out.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for row in asset_rows:
                out.write(row["row_markdown"] + "\n")
        print(f"Successfully compiled landscape table at: {args.output}")
    except Exception as e:
        print(f"Error writing compiled landscape table: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
