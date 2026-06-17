"""
Asset discovery, synonym grouping, and report metadata extraction.

Functions moved from generate_landscape_table.py (§3 decomposition).
classify_interventions() is imported from src.tools.classify_interventions.
"""

import glob
import json
import os
import re

from src.agents.bdscan_agents.intervention_classifier_agent import (
    classify_interventions,
)
from src.utils.landscape.table_formatters import (
    _name_priority,
    normalize_drug_name,
    parse_asset_and_aliases,
)


def parse_existing_report(report_path: str | None, config: dict) -> dict:
    """
    Extract qualitative metadata (modality, formulation, indication, safety,
    efficacy, milestones, citations) from an existing landscape table Markdown file.

    Updates `config` in-place with any new alias names found in the report cells.
    Returns a dict keyed by canonical asset name.
    """
    metadata = {}
    if not report_path or not os.path.exists(report_path):
        return metadata

    print(f"Reading existing report to extract qualitative metadata: {report_path}")
    try:
        with open(report_path, encoding="utf-8") as f:
            lines = f.readlines()

        in_table = False
        col_indices = {}
        for line in lines:
            if "|" in line:
                if not in_table:
                    if "Asset Name" in line:
                        in_table = True
                        cols = [c.strip() for c in line.split("|")[1:-1]]
                        for i, col_name in enumerate(cols):
                            col_indices[col_name] = i
                    continue
                if re.match(
                    r"^\s*\|?\s*(?:\s*:?-+:?\s*\|)+\s*(?:\s*:?-+:?\s*)?$", line
                ):
                    continue

                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) < 3:
                    continue

                # Get column indices dynamically
                asset_idx = col_indices.get(
                    "Asset Name", 1 if "#" in col_indices else 0
                )
                modality_idx = col_indices.get(
                    "MoA / Modality", 3 if "#" in col_indices else 2
                )
                formulation_idx = col_indices.get(
                    "Formulation", 4 if "#" in col_indices else 3
                )
                indication_idx = col_indices.get(
                    "Lead Indication", 5 if "#" in col_indices else 4
                )
                safety_idx = col_indices.get(
                    "Web Selectivity & Safety Profile",
                    col_indices.get(
                        "Selectivity & Safety Profile", 8 if "#" in col_indices else 7
                    ),
                )
                efficacy_idx = col_indices.get(
                    "Web Key Efficacy Data",
                    col_indices.get(
                        "Key Efficacy / Biomarker Data", 9 if "#" in col_indices else 8
                    ),
                )
                milestones_idx = col_indices.get(
                    "Web Upcoming Milestones",
                    col_indices.get(
                        "Upcoming Milestones", 10 if "#" in col_indices else 9
                    ),
                )
                citations_idx = col_indices.get(
                    "Web Citations / Sources",
                    col_indices.get("Citations", 11 if "#" in col_indices else 10),
                )

                if asset_idx >= len(cols):
                    continue

                asset_cell = cols[asset_idx]
                primary_name, extracted_aliases = parse_asset_and_aliases(asset_cell)
                row_names = [primary_name] + extracted_aliases
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
                        if name.lower() != matched_key.lower():
                            if name.lower() not in [
                                a.lower() for a in config[matched_key]["aliases"]
                            ]:
                                config[matched_key]["aliases"].append(name)

                    metadata[matched_key] = {
                        "modality": cols[modality_idx]
                        if modality_idx < len(cols)
                        else "",
                        "formulation": cols[formulation_idx]
                        if formulation_idx < len(cols)
                        else "",
                        "indication": cols[indication_idx]
                        if indication_idx < len(cols)
                        else "",
                        "safety": cols[safety_idx] if safety_idx < len(cols) else "",
                        "efficacy": cols[efficacy_idx]
                        if efficacy_idx < len(cols)
                        else "",
                        "milestones": cols[milestones_idx]
                        if milestones_idx < len(cols)
                        else "",
                        "citations": cols[citations_idx]
                        if citations_idx < len(cols)
                        else "",
                    }
            else:
                if in_table:
                    in_table = False  # Table ended
    except Exception as e:
        print(f"Warning: Failed to parse existing report for metadata extraction: {e}")

    print(f"Extracted qualitative metadata for {len(metadata)} assets.")
    return metadata


def merge_config_duplicates(config: dict, existing_meta: dict) -> tuple[dict, dict]:
    """
    Groups and merges keys/aliases in config that normalize to the same name
    or share common synonyms/aliases, ensuring we don't have separate rows
    for different spelling variations of the same asset.
    """
    groups = []
    for old_primary, details in config.items():
        aliases = details.get("aliases", [])
        names_set = {old_primary} | set(aliases)

        merged_indices = []
        for i, g in enumerate(groups):
            g_normalized = {normalize_drug_name(x) for x in g}
            if any(
                normalize_drug_name(n) in g_normalized
                or n.lower() in {x.lower() for x in g}
                for n in names_set
            ):
                merged_indices.append(i)

        if not merged_indices:
            groups.append(names_set)
        else:
            new_group = names_set
            for idx in sorted(merged_indices, reverse=True):
                new_group.update(groups.pop(idx))
            groups.append(new_group)

    new_config = {}
    new_existing_meta = {}
    for g in groups:
        sorted_names = sorted(g, key=_name_priority)
        new_primary = sorted_names[0]
        new_aliases = sorted_names[1:]

        new_config[new_primary] = {"aliases": new_aliases}

        combined_meta: dict = {}
        for name in g:
            if name in existing_meta:
                for mk, mv in existing_meta[name].items():
                    if (
                        mv
                        and mv != "N/A"
                        and mv != "Data not publicly disclosed."
                        and mv != "Safety evaluation ongoing."
                        and mv != "Phase 1 study completion."
                    ):
                        combined_meta[mk] = mv
                    elif mk not in combined_meta:
                        combined_meta[mk] = mv
            for old_p in config:
                if old_p.lower() == name.lower() and old_p in existing_meta:
                    for mk, mv in existing_meta[old_p].items():
                        if (
                            mv
                            and mv != "N/A"
                            and mv != "Data not publicly disclosed."
                            and mv != "Safety evaluation ongoing."
                            and mv != "Phase 1 study completion."
                        ):
                            combined_meta[mk] = mv
                        elif mk not in combined_meta:
                            combined_meta[mk] = mv

        if combined_meta:
            new_existing_meta[new_primary] = combined_meta

    return new_config, new_existing_meta


def discover_config(
    ct_data: dict,
    china_data: list,
    target_name: str = "",
    target_synonyms: list | None = None,
    database_json_dir: str | None = None,
) -> dict:
    """
    Discover pipeline assets from raw registry data using LLM-based classification.

    All unique intervention names from ClinicalTrials.gov, China CDE, and
    conference abstract files are collected, deduplicated, and classified in
    batched LLM calls. Only names classified as pipeline assets targeting
    `target_name` are retained for the landscape table.

    Args:
        ct_data: Merged ClinicalTrials.gov dict {nct_id: study_dict}
        china_data: List of China CDE records
        target_name: Primary target name for LLM classification
        target_synonyms: Additional target synonyms
        database_json_dir: Optional path to {target_dir}/database_json/ for conference files.

    Raises RuntimeError if LLM classification fails (no silent fallback).
    """
    target_synonyms = target_synonyms or []

    # -----------------------------------------------------------------------
    # 0. Attempt to load from reconciled.json to skip duplicate classification
    # -----------------------------------------------------------------------
    if database_json_dir:
        from pathlib import Path

        reconciled_path = Path(database_json_dir) / "reconciled.json"
        if reconciled_path.exists():
            print(
                f"[config_builder] Found {reconciled_path}. Reusing reconciled asset mapping..."
            )
            try:
                with open(reconciled_path, encoding="utf-8") as f:
                    reconciled = json.load(f)

                # Build config mapping canonical name -> aliases
                config = {}
                for primary, details in reconciled.items():
                    config[primary] = {"aliases": details.get("aliases", [])}

                # Persist config just as before
                config_path = os.path.join(database_json_dir, "asset_config.json")
                os.makedirs(database_json_dir, exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                print(
                    "[config_builder] Successfully compiled config from reconciled.json"
                )
                return config
            except Exception as e:
                print(
                    f"[config_builder] Warning: Failed to parse reconciled.json: {e}. Falling back to LLM classification."
                )

    # -----------------------------------------------------------------------
    # 1. Collect (primary_name, [aliases]) pairs from ClinicalTrials.gov
    # -----------------------------------------------------------------------
    ct_interventions: list = []
    for _nct_id, study in ct_data.items():
        proto = study.get("protocolSection", {})
        arms_mod = proto.get("armsInterventionsModule", {})
        for intv in arms_mod.get("interventions", []):
            intv_type = intv.get("type", "").upper()
            if intv_type in ["DRUG", "BIOLOGICAL", "GENETIC"]:
                name = intv.get("name", "").strip()
                other_names = [
                    n.strip() for n in intv.get("otherNames", []) if n.strip()
                ]
                if name:
                    ct_interventions.append((name, other_names))

    # -----------------------------------------------------------------------
    # 2. Collect raw drug names from China CDE
    # -----------------------------------------------------------------------
    china_names: list = []
    for rec in china_data:
        drug_name = rec.get("drug_name", "").strip()
        if drug_name:
            china_names.append(drug_name)

    # -----------------------------------------------------------------------
    # 3. Collect candidate codes from conference abstract files
    # -----------------------------------------------------------------------
    conf_codes: list = []
    if database_json_dir and os.path.exists(database_json_dir):
        for filepath in glob.glob(
            os.path.join(database_json_dir, "*conferences*.json")
        ):
            try:
                with open(filepath, encoding="utf-8") as f:
                    conf_data = json.load(f)
                for item in conf_data.get("results", []):
                    title = item.get("title", "")
                    codes = re.findall(r"\b[A-Za-z]{2,6}-?\d{2,6}[A-Za-z]?\b", title)
                    conf_codes.extend(codes)
            except Exception as e:
                print(f"Warning: Failed to process conference file {filepath}: {e}")

    # -----------------------------------------------------------------------
    # 4. Build flat list of all unique names for classification
    # -----------------------------------------------------------------------
    all_raw: list = []
    for primary, aliases in ct_interventions:
        all_raw.append(primary)
        all_raw.extend(aliases)
    all_raw.extend(china_names)
    all_raw.extend(conf_codes)

    if not all_raw:
        print("No intervention names found in registry data.")
        return {}

    # -----------------------------------------------------------------------
    # 5. LLM-based classification
    # -----------------------------------------------------------------------
    classified_assets = classify_interventions(all_raw, target_name, target_synonyms)

    print(
        f"\nClassification complete: {len(classified_assets)} pipeline asset(s) "
        f"identified from {len({n.lower() for n in all_raw})} unique name(s)."
    )

    # -----------------------------------------------------------------------
    # 6. Group synonym clusters — only for names classified as assets
    # -----------------------------------------------------------------------
    groups: list[set] = []
    for entry in classified_assets:
        canon = entry["canonical_name"]
        aliases = entry.get("aliases", [])
        names_set = {canon} | set(aliases)

        merged_indices = []
        for i, g in enumerate(groups):
            g_normalized = {normalize_drug_name(x) for x in g}
            if any(
                normalize_drug_name(n) in g_normalized
                or n.lower() in {x.lower() for x in g}
                for n in names_set
            ):
                merged_indices.append(i)

        if not merged_indices:
            groups.append(names_set)
        else:
            new_group = names_set
            for idx in sorted(merged_indices, reverse=True):
                new_group.update(groups.pop(idx))
            groups.append(new_group)

    # -----------------------------------------------------------------------
    # 7. Build config dict — canonical primary key chosen by _name_priority
    # -----------------------------------------------------------------------
    config: dict = {}
    for g in groups:
        sorted_names = sorted(g, key=_name_priority)
        primary = sorted_names[0]
        aliases = sorted_names[1:]
        config[primary] = {"aliases": aliases}

    # Persist asset_config.json to the database_json directory
    if database_json_dir:
        os.makedirs(database_json_dir, exist_ok=True)
        config_path = os.path.join(database_json_dir, "asset_config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"[config_builder] Persisted asset_config.json to {config_path}")
        except Exception as e:
            print(f"[config_builder] Warning: Failed to persist asset_config.json: {e}")

    return config
