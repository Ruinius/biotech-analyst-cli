"""
Reconciliation Mapper — §1: Database Result Reconciliation.

Aggregates raw JSON outputs from all 8 supported registries/databases into a
unified, asset-centric reconciled.json immediately after the Database Search phase.

Entry point: reconcile_all_sources(target_dir, folder_safe_name)
  → writes {target_dir}/database_json/reconciled.json
  → writes {target_dir}/database_json/reconciliation_log.json
"""

import glob
import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Typed record structures (dataclass-lite dicts for simplicity)
# ---------------------------------------------------------------------------


def _asset_record(
    name: str,
    source: str,
    record_id: str | None = None,
    status: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Create a normalized AssetRecord dict."""
    return {
        "name": name,
        "source": source,
        "record_id": record_id,
        "status": status,
        **(extra or {}),
    }


# ---------------------------------------------------------------------------
# Source mapper functions
# ---------------------------------------------------------------------------


def map_clinicaltrials(raw_data: dict) -> list:
    """
    Extract asset name candidates from merged ClinicalTrials.gov / ANZCTR JSON.

    Returns list of AssetRecord dicts, one per intervention name found.
    Each record carries the source trial ID and status for later assignment.
    """
    records = []
    for nct_id, study in raw_data.items():
        proto = study.get("protocolSection", {})
        status_mod = proto.get("statusModule", {})
        arms_mod = proto.get("armsInterventionsModule", {})
        status = status_mod.get("overallStatus", "UNKNOWN")

        for intv in arms_mod.get("interventions", []):
            intv_type = intv.get("type", "").upper()
            if intv_type not in ["DRUG", "BIOLOGICAL", "GENETIC"]:
                continue

            name = intv.get("name", "").strip()
            if name:
                records.append(
                    _asset_record(
                        name=name,
                        source="clinicaltrials",
                        record_id=nct_id,
                        status=status,
                        extra={
                            "other_names": intv.get("otherNames", []),
                            "phase": study.get("protocolSection", {})
                            .get("designModule", {})
                            .get("phases", []),
                        },
                    )
                )
            for other_name in intv.get("otherNames", []):
                other_name = other_name.strip()
                if other_name:
                    records.append(
                        _asset_record(
                            name=other_name,
                            source="clinicaltrials",
                            record_id=nct_id,
                            status=status,
                            extra={"is_alias": True},
                        )
                    )
    return records


def map_anzctr_ctis(raw_data: dict) -> list:
    """
    Extract asset name candidates from ANZCTR/CTIS JSON.
    Cross-references NCT IDs when available.
    """
    records = []
    for item in raw_data.get("results", []):
        title = item.get("title", "")
        status = "Recruiting" if not item.get("pubYear") else "Completed"

        # Extract NCT cross-reference if available
        nct_id = None
        nct_match = re.search(r"\bNCT\d{8}\b", title)
        if nct_match:
            nct_id = nct_match.group(0)

        mesh = item.get("meshHeadingList", {})
        drug_names = mesh.get("descriptorName", []) if mesh else []

        for drug_name in drug_names:
            if drug_name and drug_name != "N/A":
                records.append(
                    _asset_record(
                        name=drug_name,
                        source="anzctr_ctis",
                        record_id=item.get("id") or nct_id,
                        status=status,
                        extra={"title": title},
                    )
                )

        # Also pass the raw title for LLM extraction
        if title:
            records.append(
                _asset_record(
                    name=title,
                    source="anzctr_ctis",
                    record_id=item.get("id") or nct_id,
                    status=status,
                    extra={"is_raw_title": True},
                )
            )
    return records


def map_china_cde(raw_data: dict) -> list:
    """
    Extract asset name candidates from NMPA CDE (China Direct) JSON.
    Records have structured drug_name and acceptance_number fields.
    """
    records = []
    for rec in raw_data.get("records", []):
        drug_name = rec.get("drug_name", "").strip()
        if drug_name:
            records.append(
                _asset_record(
                    name=drug_name,
                    source="china_cde",
                    record_id=rec.get("acceptance_number"),
                    status=rec.get("status"),
                    extra={
                        "company": rec.get("company", ""),
                    },
                )
            )
    return records


def map_chinese_registries(raw_data: dict) -> list:
    """
    Extract asset name candidates from Chinese WHO Registries JSON.
    Drug names are embedded in free-text titles — raw title passed for LLM extraction.
    """
    records = []
    for item in raw_data.get("results", []):
        title = item.get("title", "").strip()
        if title:
            records.append(
                _asset_record(
                    name=title,
                    source="chinese_registries",
                    record_id=item.get("id"),
                    status=None,
                    extra={"is_raw_title": True},
                )
            )
    return records


def map_conferences(raw_data: dict) -> list:
    """
    Extract conference abstract title strings.
    Raw titles are passed to the LLM for drug name extraction.
    """
    records = []
    for item in raw_data.get("results", []):
        title = item.get("title", "").strip()
        event = item.get("event", "")
        abstract_id = item.get("abstract_id", "")
        if title:
            records.append(
                _asset_record(
                    name=title,
                    source="conferences",
                    record_id=abstract_id or None,
                    status=None,
                    extra={"event": event, "is_raw_title": True},
                )
            )
    return records


def map_patents(raw_data: dict) -> list:
    """
    Extract patent titles and assignees from Lens.org JSON.
    """
    records = []
    for item in raw_data.get("results", []):
        title = item.get("title", "").strip()
        assignee = item.get("assignee", "")
        patent_id = item.get("id", "")
        if title:
            records.append(
                _asset_record(
                    name=title,
                    source="patents",
                    record_id=patent_id or None,
                    status=None,
                    extra={"assignee": assignee, "is_raw_title": True},
                )
            )
    return records


def map_pubchem(raw_data: dict) -> dict:
    """
    Extract PubChem compound metadata. Returns a single PubChemRecord dict.
    """
    return {
        "cid": raw_data.get("cid"),
        "bioassays": raw_data.get("bioassays", 0),
        "molecular_formula": raw_data.get("molecular_formula", ""),
        "compound_name": raw_data.get("compound_name", ""),
    }


def map_openfda(raw_data: dict) -> dict:
    """
    Extract openFDA adverse event and label metadata. Returns a single OpenFDARecord dict.
    """
    return {
        "adverse_events": raw_data.get("adverse_events", 0),
        "labels": raw_data.get("labels", []),
    }


# ---------------------------------------------------------------------------
# Helper: extract all "flat" candidate names from source records for LLM input
# ---------------------------------------------------------------------------


def _extract_candidate_names(records: list) -> list:
    """
    Extract unique candidate drug names from a list of AssetRecord dicts.

    For raw-title records: extract alphanumeric drug codes via regex pre-filter
    (the LLM will still process the full title text during classification).
    For structured records: use the name field directly.
    """
    names = []
    for rec in records:
        if rec.get("is_raw_title"):
            # Extract alphanumeric codes from title (quick pre-filter)
            codes = re.findall(r"\b[A-Za-z]{2,6}-?\d{2,6}[A-Za-z]?\b", rec["name"])
            names.extend(codes)
            # Also add the full title for LLM context — classifier handles it
            names.append(rec["name"])
        else:
            names.append(rec["name"])
    return names


# ---------------------------------------------------------------------------
# Core reconciliation entry point
# ---------------------------------------------------------------------------


def reconcile_all_sources(target_dir: Path, folder_safe_name: str) -> None:
    """
    Full §1 reconciliation pipeline.

    1. Globs {target_dir}/database_json/*_*.json for all raw source files
    2. Runs each source-specific mapper to extract raw names and records
    3. Batches all unique names through classify_interventions() for LLM grouping
    4. Assigns records to canonical asset entries based on LLM synonym clusters
    5. Writes reconciled.json and reconciliation_log.json

    Falls back gracefully if no database_json files are found.
    """
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,  # noqa: PLC0415
    )
    from src.utils.landscape.table_formatters import (  # noqa: PLC0415
        EXCLUDE_LOWER,
        _name_priority,
        clean_drug_name,
        cluster_synonym_groups,
    )

    db_dir = target_dir / "database_json"
    if not db_dir.exists():
        print(
            f"[Reconciliation] No database_json/ directory found at {db_dir}. Skipping."
        )
        return

    reconciled_path = db_dir / "reconciled.json"
    log_path = db_dir / "reconciliation_log.json"

    # -----------------------------------------------------------------------
    # Step 1: Load raw source files and run mappers
    # -----------------------------------------------------------------------
    all_asset_records: list = []
    pubchem_record: dict = {}
    openfda_record: dict = {}
    source_file_map: dict = {}

    patterns = {
        "clinicaltrials": f"{folder_safe_name}_clinicaltrials.json",
        "anzctr_ctis": f"{folder_safe_name}_anzctr_*.json",
        "china_cde": f"{folder_safe_name}_cdirect_*.json",
        "chinese_registries": f"{folder_safe_name}_chreg_*.json",
        "conferences": f"{folder_safe_name}_conf_*.json",
        "patents": f"{folder_safe_name}_lens_*.json",
        "pubchem": f"{folder_safe_name}_pubchem_*.json",
        "openfda": f"{folder_safe_name}_openfda_*.json",
    }

    for source_key, pattern in patterns.items():
        matched_files = glob.glob(str(db_dir / pattern))
        if not matched_files:
            print(
                f"[Reconciliation] No files found for {source_key} (pattern: {pattern})"
            )
            continue

        for filepath in matched_files:
            try:
                with open(filepath, encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception as e:
                print(f"[Reconciliation] Warning: Failed to load {filepath}: {e}")
                continue

            source_file_map[source_key] = filepath

            if source_key == "clinicaltrials":
                records = map_clinicaltrials(raw)
                all_asset_records.extend(records)
            elif source_key == "anzctr_ctis":
                records = map_anzctr_ctis(raw)
                all_asset_records.extend(records)
            elif source_key == "china_cde":
                records = map_china_cde(raw)
                all_asset_records.extend(records)
            elif source_key == "chinese_registries":
                records = map_chinese_registries(raw)
                all_asset_records.extend(records)
            elif source_key == "conferences":
                records = map_conferences(raw)
                all_asset_records.extend(records)
            elif source_key == "patents":
                records = map_patents(raw)
                all_asset_records.extend(records)
            elif source_key == "pubchem":
                pubchem_record = map_pubchem(raw)
            elif source_key == "openfda":
                openfda_record = map_openfda(raw)

    if not all_asset_records:
        print(
            "[Reconciliation] No asset records extracted from any source. Skipping reconciliation."
        )
        return

    # -----------------------------------------------------------------------
    # Step 2: Collect and clean synonym sets programmatically
    # -----------------------------------------------------------------------
    target_name = folder_safe_name.replace("_", " ").replace("-", " ")
    synonym_sets: list[set[str]] = []

    # Build synonym groups by record_id
    id_to_names = {}
    for rec in all_asset_records:
        rec_id = rec.get("record_id")
        name = rec.get("name")
        if not name:
            continue
        cleaned = clean_drug_name(name, target_name)
        if cleaned and cleaned.lower() not in EXCLUDE_LOWER:
            if rec_id:
                if rec_id not in id_to_names:
                    id_to_names[rec_id] = set()
                id_to_names[rec_id].add(cleaned)
            else:
                synonym_sets.append({cleaned})

    for names_set in id_to_names.values():
        synonym_sets.append(names_set)

    # Include any direct otherNames from clinicaltrials
    for rec in all_asset_records:
        if rec.get("source") == "clinicaltrials":
            other = rec.get("other_names") or []
            cleaned_others = []
            for o in other:
                cleaned_o = clean_drug_name(o, target_name)
                if cleaned_o and cleaned_o.lower() not in EXCLUDE_LOWER:
                    cleaned_others.append(cleaned_o)
            primary_cleaned = clean_drug_name(rec["name"], target_name)
            if primary_cleaned and primary_cleaned.lower() not in EXCLUDE_LOWER:
                cleaned_others.append(primary_cleaned)
            if cleaned_others:
                synonym_sets.append(set(cleaned_others))

    # Run the programmatic DSU clustering
    groups = cluster_synonym_groups(synonym_sets)

    # -----------------------------------------------------------------------
    # Step 3: LLM-based classification of candidate canonical assets
    # -----------------------------------------------------------------------
    candidate_map = {}  # name_lower -> group_set
    candidate_list = []
    for g in groups:
        sorted_names = sorted(g, key=_name_priority)
        primary = sorted_names[0]
        candidate_list.append(primary)
        candidate_map[primary.lower()] = g
        for alias in sorted_names[1:]:
            candidate_map[alias.lower()] = g

    if not candidate_list:
        print("[Reconciliation] No candidate drug names found after pre-filtering.")
        reconciled_path.write_text(
            json.dumps({}, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log_path.write_text(
            json.dumps({"info": "No candidates"}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return

    try:
        print(
            f"[Reconciliation] Querying LLM to classify {len(candidate_list)} candidate assets..."
        )
        classified_assets = classify_interventions(
            names=candidate_list,
            target_name=target_name,
        )
    except RuntimeError as e:
        print(f"[Reconciliation] LLM classification failed: {e}")
        print("[Reconciliation] Writing empty reconciliation artifacts.")
        reconciled_path.write_text(
            json.dumps({}, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log_path.write_text(
            json.dumps({"error": str(e)}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return

    # -----------------------------------------------------------------------
    # Step 4: Map synonyms and initialize reconciled entry structure
    # -----------------------------------------------------------------------
    canonical_map: dict[str, str] = {}  # any_name_lower → canonical
    reconciled: dict = {}

    for entry in classified_assets:
        canon = entry["canonical_name"]
        aliases = set(entry.get("aliases", []))

        # Merge in the programmatic group synonyms
        prog_group = candidate_map.get(canon.lower())
        if prog_group:
            aliases.update(prog_group)

        aliases.discard(canon)
        filtered_aliases = [a for a in aliases if a.lower() not in EXCLUDE_LOWER]

        sorted_aliases = sorted(filtered_aliases, key=_name_priority)

        for name in [canon] + sorted_aliases:
            canonical_map[name.lower()] = canon

        reconciled[canon] = {
            "canonical_name": canon,
            "aliases": sorted_aliases,
            "sponsors": [],
            "modality": entry.get("modality", "N/A"),
            "lead_indication": "N/A",
            "trials": {
                "clinicaltrials": [],
                "china_cde": [],
                "anzctr_ctis": [],
                "chinese_registries": [],
            },
            "patents": [],
            "conferences": [],
            "pubchem": pubchem_record if pubchem_record else {},
            "openfda": openfda_record if openfda_record else {},
        }

    # Assign structured records to canonical entries
    background_log: list = []

    for rec in all_asset_records:
        name_key = rec["name"].lower()
        cleaned_name = clean_drug_name(rec["name"], target_name)
        cleaned_key = cleaned_name.lower() if cleaned_name else ""

        canonical = None
        if name_key in canonical_map:
            canonical = canonical_map[name_key]
        elif cleaned_key in canonical_map:
            canonical = canonical_map[cleaned_key]

        if not canonical and rec.get("is_raw_title"):
            # Skip raw title records that weren't matched
            continue

        if not canonical:
            # Background term — log it
            background_log.append(
                {
                    "name": rec["name"],
                    "source": rec["source"],
                    "reason": "Programmatic cleansing filter or LLM background classification",
                }
            )
            continue

        entry = reconciled[canonical]
        source = rec["source"]

        if source == "clinicaltrials" and not rec.get("is_alias"):
            trial = {
                "id": rec["record_id"],
                "status": rec["status"],
                "phase": rec.get("phase", []),
            }
            existing_ids = {t["id"] for t in entry["trials"]["clinicaltrials"]}
            if rec["record_id"] and rec["record_id"] not in existing_ids:
                entry["trials"]["clinicaltrials"].append(trial)
            # Collect sponsor from study (not available at this level — kept for §2)

        elif source == "china_cde":
            trial = {
                "id": rec["record_id"],
                "status": rec["status"],
                "drug_name": rec["name"],
                "company": rec.get("company", ""),
            }
            existing_ids = {t["id"] for t in entry["trials"]["china_cde"]}
            if rec["record_id"] and rec["record_id"] not in existing_ids:
                entry["trials"]["china_cde"].append(trial)

        elif source == "anzctr_ctis" and not rec.get("is_raw_title"):
            trial = {
                "id": rec["record_id"],
                "status": rec["status"],
                "title": rec.get("title", ""),
            }
            existing_ids = {t["id"] for t in entry["trials"]["anzctr_ctis"]}
            if rec["record_id"] and rec["record_id"] not in existing_ids:
                entry["trials"]["anzctr_ctis"].append(trial)

        elif source == "chinese_registries" and not rec.get("is_raw_title"):
            trial = {"id": rec["record_id"], "status": rec["status"]}
            existing_ids = {t["id"] for t in entry["trials"]["chinese_registries"]}
            if rec["record_id"] and rec["record_id"] not in existing_ids:
                entry["trials"]["chinese_registries"].append(trial)

        elif source == "conferences":
            conf = {
                "title": rec["name"],
                "event": rec.get("event", ""),
                "abstract_id": rec["record_id"],
            }
            if conf not in entry["conferences"]:
                entry["conferences"].append(conf)

        elif source == "patents":
            patent = {
                "id": rec["record_id"],
                "title": rec["name"],
                "assignee": rec.get("assignee", ""),
            }
            existing_ids = {p["id"] for p in entry["patents"]}
            if rec["record_id"] and rec["record_id"] not in existing_ids:
                entry["patents"].append(patent)

    # -----------------------------------------------------------------------
    # Step 5: Write outputs
    # -----------------------------------------------------------------------
    reconciled_path.write_text(
        json.dumps(reconciled, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"[Reconciliation] Wrote reconciled.json with {len(reconciled)} canonical assets."
    )

    log_data = {
        "background_terms": background_log,
        "source_files": source_file_map,
        "total_records_processed": len(all_asset_records),
        "classified_assets_count": len(classified_assets),
        "background_count": len(background_log),
    }
    log_path.write_text(
        json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"[Reconciliation] Wrote reconciliation_log.json ({len(background_log)} background terms logged)."
    )
