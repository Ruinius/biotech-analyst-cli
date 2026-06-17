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
        _name_priority,
        normalize_drug_name,
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
    # Step 2: Trivial exact-dedup (preprocessing only — case-insensitive)
    # -----------------------------------------------------------------------
    all_candidate_names = _extract_candidate_names(all_asset_records)

    seen_lower: dict = {}
    for n in all_candidate_names:
        stripped = n.strip()
        key = stripped.lower()
        if stripped and key not in seen_lower:
            seen_lower[key] = stripped
    unique_names = list(seen_lower.values())

    print(
        f"[Reconciliation] {len(unique_names)} unique candidate names extracted from {len(all_asset_records)} records."
    )

    # -----------------------------------------------------------------------
    # Step 3: LLM-based classification and grouping
    # NOTE: classify_interventions returns set[str] in §3; extended to list[dict] in §2.
    # We infer target_name from the folder_safe_name as a rough proxy here.
    # The orchestrator will pass the real target_name once §1 is wired in fully.
    # -----------------------------------------------------------------------
    target_name = folder_safe_name.replace("_", " ").replace("-", " ")

    try:
        classified_assets = classify_interventions(
            names=unique_names,
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

    classified_lower = set()
    for entry in classified_assets:
        classified_lower.add(entry["canonical_name"].lower())
        for a in entry.get("aliases", []):
            classified_lower.add(a.lower())

    # -----------------------------------------------------------------------
    # Step 4: Group synonyms and assign records to canonical entries
    # -----------------------------------------------------------------------
    groups: list[set] = []
    modality_map: dict[str, str] = {}
    for entry in classified_assets:
        canon = entry["canonical_name"]
        aliases = entry.get("aliases", [])
        names_set = {canon} | set(aliases)
        modality_map[canon.lower()] = entry.get("modality", "N/A")
        for alias in aliases:
            modality_map[alias.lower()] = entry.get("modality", "N/A")

        merged_indices = []
        for i, g in enumerate(groups):
            g_norms = {normalize_drug_name(x) for x in g}
            if any(
                normalize_drug_name(n) in g_norms or n.lower() in {x.lower() for x in g}
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

    # Choose canonical name per group
    canonical_map: dict[str, str] = {}  # any_name_lower → canonical
    reconciled: dict = {}

    for g in groups:
        sorted_names = sorted(g, key=_name_priority)
        canonical = sorted_names[0]
        aliases = sorted_names[1:]

        for n in g:
            canonical_map[n.lower()] = canonical

        reconciled[canonical] = {
            "canonical_name": canonical,
            "aliases": aliases,
            "sponsors": [],
            "modality": modality_map.get(canonical.lower(), "N/A"),
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
        canonical = canonical_map.get(name_key) or canonical_map.get(
            normalize_drug_name(rec["name"])
        )

        if not canonical and rec.get("is_raw_title"):
            # Skip raw title records that weren't matched
            continue

        if not canonical:
            # Background term — log it
            background_log.append(
                {
                    "name": rec["name"],
                    "source": rec["source"],
                    "reason": "LLM classified as background",
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
