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
    EXCLUDE_LOWER,
    _name_priority,
    clean_drug_name,
    cluster_synonym_groups,
    extract_china_drug,
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
                licensing_idx = col_indices.get(
                    "Web Licensing Status & Partners",
                    col_indices.get(
                        "Licensing Status & Partners", 10 if "#" in col_indices else 9
                    ),
                )
                milestones_idx = col_indices.get(
                    "Web Upcoming Milestones",
                    col_indices.get(
                        "Upcoming Milestones", 11 if "#" in col_indices else 10
                    ),
                )
                citations_idx = col_indices.get(
                    "Web Citations / Sources",
                    col_indices.get("Citations", 12 if "#" in col_indices else 11),
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
                        "licensing": cols[licensing_idx]
                        if licensing_idx < len(cols)
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

        # Get modality from original config
        modality = "N/A"
        for name in g:
            for old_p, old_det in config.items():
                if old_p.lower() == name.lower() or name.lower() in [
                    a.lower() for a in old_det.get("aliases", [])
                ]:
                    if old_det.get("modality") and old_det.get("modality") != "N/A":
                        modality = old_det.get("modality")
                        break
            if modality != "N/A":
                break

        new_config[new_primary] = {
            "aliases": new_aliases,
            "modality": modality,
        }

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
    Discover pipeline assets from raw registry data using local pre-filtering,
    Disjoint-Set Union (Union-Find) clustering, and targeted LLM classification.

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
                    config[primary] = {
                        "aliases": details.get("aliases", []),
                        "modality": details.get("modality", "N/A"),
                    }

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
    # 1. Collect and clean synonym sets programmatically
    # -----------------------------------------------------------------------
    synonym_sets: list[set[str]] = []

    # Process ClinicalTrials.gov
    for _nct_id, study in ct_data.items():
        proto = study.get("protocolSection", {})
        arms_mod = proto.get("armsInterventionsModule", {})
        for intv in arms_mod.get("interventions", []):
            intv_type = intv.get("type", "").upper()
            if intv_type in ["DRUG", "BIOLOGICAL", "GENETIC"]:
                name = intv.get("name", "").strip()
                other_names = intv.get("otherNames", [])

                names_to_clean = [name] + [o.strip() for o in other_names if o.strip()]
                cleansed_names = []
                for n in names_to_clean:
                    cleaned = clean_drug_name(n, target_name, target_synonyms)
                    if cleaned and cleaned.lower() not in EXCLUDE_LOWER:
                        cleansed_names.append(cleaned)
                if cleansed_names:
                    synonym_sets.append(set(cleansed_names))

    # Process China CDE direct
    for rec in china_data:
        drug_name = rec.get("drug_name", "").strip()
        if drug_name:
            extracted = extract_china_drug(drug_name, target_name, target_synonyms)
            if extracted and extracted.lower() not in EXCLUDE_LOWER:
                synonym_sets.append({extracted})

    # Process conferences
    if database_json_dir and os.path.exists(database_json_dir):
        for filepath in glob.glob(
            os.path.join(database_json_dir, "*conferences*.json")
        ):
            try:
                with open(filepath, encoding="utf-8") as f:
                    conf_data = json.load(f)
                for item in conf_data.get("results", []):
                    title = item.get("title", "")
                    cleaned_title_asset = clean_drug_name(
                        title, target_name, target_synonyms
                    )
                    if (
                        cleaned_title_asset
                        and cleaned_title_asset.lower() not in EXCLUDE_LOWER
                    ):
                        synonym_sets.append({cleaned_title_asset})
            except Exception as e:
                print(f"Warning: Failed to process conference file {filepath}: {e}")

    # Load global master_config.json if it exists
    master_config = {}
    master_lookup = {}
    try:
        from src.core.config import load_config

        settings = load_config()
        if settings and settings.base_folder:
            from pathlib import Path

            master_path = Path(settings.expanded_base_folder) / "master_config.json"
            if master_path.exists():
                with open(master_path, encoding="utf-8") as f:
                    master_config = json.load(f)
                print(
                    f"[config_builder] Loaded master_config.json with {len(master_config)} entries from {master_path}"
                )
                # Build lowercase alias mapping
                for canon, details in master_config.items():
                    aliases = details.get("aliases", [])
                    entry = {
                        "canonical_name": canon,
                        "aliases": aliases,
                        "modality": details.get("modality", "N/A"),
                        "targets": details.get("targets", []),
                    }
                    master_lookup[canon.lower()] = entry
                    for alias in aliases:
                        master_lookup[alias.lower()] = entry
    except Exception as e:
        print(f"[config_builder] Note: Could not load global master_config.json: {e}")

    # Run the programmatic DSU clustering
    groups = cluster_synonym_groups(synonym_sets)

    # -----------------------------------------------------------------------
    # 2. Pick candidate canonical names and classify via LLM
    # -----------------------------------------------------------------------
    candidate_map = {}  # candidate_name_lower -> group_set
    candidate_list = []
    pre_classified_assets = []

    for g in groups:
        # Check if any name in group g is in master_config
        matched_entry = None
        for name in g:
            if name.lower() in master_lookup:
                matched_entry = master_lookup[name.lower()]
                break

        if matched_entry:
            # Found in master_config! Pre-classify this group
            canon = matched_entry["canonical_name"]
            # Merge all aliases from both the programmatic group and the master_config
            merged_aliases = set(g)
            merged_aliases.update(matched_entry.get("aliases", []))
            if canon in merged_aliases:
                merged_aliases.remove(canon)

            # Save pre-classified entry
            pre_classified_assets.append(
                {
                    "canonical_name": canon,
                    "aliases": list(merged_aliases),
                    "modality": matched_entry.get("modality", "N/A"),
                    "targets": matched_entry.get("targets", []),
                }
            )
            # Map all names in the group to this canonical name
            for name in g:
                candidate_map[name.lower()] = g
            # Also register the canonical name under candidate_map
            candidate_map[canon.lower()] = g
            print(
                f"[config_builder] Pre-classified asset '{canon}' using master_config (bypassing LLM)"
            )
        else:
            # Not found in master_config, send to LLM
            sorted_names = sorted(g, key=_name_priority)
            primary = sorted_names[0]
            candidate_list.append(primary)
            candidate_map[primary.lower()] = g
            for alias in sorted_names[1:]:
                candidate_map[alias.lower()] = g

    classified_assets = []
    if candidate_list:
        print(
            f"[config_builder] Querying LLM to classify {len(candidate_list)} candidate assets..."
        )
        classified_assets = classify_interventions(
            candidate_list, target_name, target_synonyms
        )

    # Combine pre-classified assets and LLM-classified assets
    all_classified = pre_classified_assets + classified_assets

    print(
        f"\nClassification complete: {len(all_classified)} pipeline asset(s) "
        f"identified (LLM classified: {len(classified_assets)}, pre-classified: {len(pre_classified_assets)})."
    )

    # -----------------------------------------------------------------------
    # 3. Build final config mapping canonical name -> aliases
    # -----------------------------------------------------------------------
    config: dict = {}
    for entry in all_classified:
        canon = entry["canonical_name"]
        aliases = set(entry.get("aliases", []))

        # Merge in the programmatically clustered aliases
        prog_group = candidate_map.get(canon.lower())
        if prog_group:
            aliases.update(prog_group)

        # Remove canonical name itself from aliases
        aliases.discard(canon)

        # Strip any background exclusions that might have snuck back in
        filtered_aliases = [a for a in aliases if a.lower() not in EXCLUDE_LOWER]

        sorted_aliases = sorted(filtered_aliases, key=_name_priority)
        config[canon] = {
            "aliases": sorted_aliases,
            "modality": entry.get("modality", "N/A"),
        }

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
