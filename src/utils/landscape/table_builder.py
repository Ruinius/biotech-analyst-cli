"""
Core table construction loop for the competitive landscape table.

Moved from generate_landscape_table.py main() (§3 decomposition).
Exposed as build_landscape_table() for direct Python import — no subprocess.
"""

import json
import os
from pathlib import Path

from src.utils.landscape.config_builder import (
    discover_config,
    merge_config_duplicates,
    parse_existing_report,
)
from src.utils.landscape.exporters import md_table_to_text_table
from src.utils.landscape.table_formatters import (
    CDE_DISCONTINUED,
    CT_ACTIVE,
    CT_COMPLETED,
    CT_DISCONTINUED,
    clean_sponsor,
    detect_formulation,
    matches_drug,
    parse_ct_phase,
    parse_text_phase,
)


def build_landscape_table(
    ct_data: dict,
    china_data: list,
    config: dict,
    existing_meta: dict,
    output_path: str | Path,
) -> str:
    """
    Build the competitive landscape Markdown table and write it to output_path.

    Args:
        ct_data:       Merged {nct_id: study_dict} from ClinicalTrials.gov + ANZCTR/CTIS.
        china_data:    List of China CDE records (each a dict with 'drug_name', etc.).
        config:        Asset config dict {canonical_name: {"aliases": [...]}}.
        existing_meta: Qualitative metadata dict from parse_existing_report().
        output_path:   Destination path for the landscape_table.md output.

    Returns the aligned Markdown content as a string.
    """
    asset_rows = []

    for asset_name, details in config.items():
        aliases = details.get("aliases", [])
        search_names = [asset_name] + aliases

        matched_ct = []
        matched_china = []

        sponsors: set = set()
        formulation_texts = []
        phases = []

        # -----------------------------------------------------------------------
        # 1. Scan ClinicalTrials.gov
        # -----------------------------------------------------------------------
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

            interventions = arms_mod.get("interventions", [])
            int_texts = []
            for intv in interventions:
                int_texts.append(intv.get("name", ""))
                int_texts.extend(intv.get("otherNames", []))
                int_texts.append(intv.get("description", ""))

            all_text_to_search = " | ".join(
                [brief_title, official_title, acronym, summary, description] + int_texts
            )

            if matches_drug(all_text_to_search, search_names):
                status = status_mod.get("overallStatus", "UNKNOWN")
                if status.upper() in ["UNKNOWN", "UNKNOWN_STATUS"] and status_mod.get(
                    "lastKnownStatus"
                ):
                    status = status_mod.get("lastKnownStatus")
                matched_ct.append(
                    {
                        "id": nct_id,
                        "status": status,
                        "phase": design_mod.get("phases", []),
                    }
                )

                sp = sponsor_mod.get("leadSponsor", {}).get("name")
                if sp:
                    sponsors.add(clean_sponsor(sp))

                formulation_texts.append(all_text_to_search)

                p_str, p_val = parse_ct_phase(design_mod.get("phases", []))
                if p_val > 0:
                    phases.append((p_val, p_str, status))

        # -----------------------------------------------------------------------
        # 2. Scan ChinaDrugTrials (China Direct)
        # -----------------------------------------------------------------------
        for rec in china_data:
            reg_num = rec.get("acceptance_number", "")
            drug_name = rec.get("drug_name", "")
            company = rec.get("company", "")
            status = rec.get("status", "")

            all_text_to_search = f"{drug_name} | {company}"

            if matches_drug(all_text_to_search, search_names):
                matched_china.append(
                    {"id": reg_num, "status": status, "phase_text": drug_name}
                )
                formulation_texts.append(all_text_to_search)
                p_str, p_val = parse_text_phase(drug_name)
                if p_val > 0:
                    phases.append((p_val, p_str, status))

        # -----------------------------------------------------------------------
        # 3. Determine Lead Phase and Development Status
        # -----------------------------------------------------------------------
        lead_phase = "Pre-clinical"
        lead_val = 0.0

        active_phases = []
        discontinued_phases = []

        for p_val, p_str, status in phases:
            status_upper = status.upper()
            is_active = (
                status_upper in CT_ACTIVE
                or status_upper in CT_COMPLETED
                or any(
                    k in status
                    for k in ["进行中", "招募中", "已完成", "招募完成", "尚未招募"]
                )
            )
            is_discontinued = status_upper in CT_DISCONTINUED or any(
                k in status for k in ["主动终止", "已终止", "暂停"]
            )

            if is_active:
                active_phases.append((p_val, p_str))
            elif is_discontinued:
                discontinued_phases.append((p_val, p_str))

        is_discontinued_globally = False
        if len(phases) > 0 and len(active_phases) == 0 and len(discontinued_phases) > 0:
            is_discontinued_globally = True
            max_p = max(discontinued_phases, key=lambda x: x[0])
            lead_phase = f"{max_p[1]} (Discontinued)"
            lead_val = max_p[0]
        elif len(active_phases) > 0:
            max_p = max(active_phases, key=lambda x: x[0])
            lead_phase = max_p[1]
            lead_val = max_p[0]
        else:
            meta_val = details.get("phase")
            if meta_val:
                lead_phase = meta_val
            elif asset_name in ["DR-30310"]:
                lead_phase = "Pre-clinical"
            elif asset_name in ["BNT141", "AMG 910"]:
                lead_phase = "Phase 1 (Discontinued)"
                is_discontinued_globally = True

        # Fallback for drugs with matched trials but lead_val is still 0
        if lead_val == 0.0:
            if len(matched_ct) > 0 or len(matched_china) > 0:
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

        # -----------------------------------------------------------------------
        # 4. Format columns
        # -----------------------------------------------------------------------
        detected_forms = detect_formulation(formulation_texts)
        if len(detected_forms) > 0:
            formulation_str = ", ".join(detected_forms)
        else:
            formulation_str = (
                details.get("formulation")
                or existing_meta.get(asset_name, {}).get("formulation")
                or "Intravenous"
            )

        if "Subcutaneous" in formulation_str and "Intravenous" in formulation_str:
            formulation_str = "Intravenous & Subcutaneous"
        elif "Subcutaneous" in formulation_str:
            formulation_str = "Subcutaneous"
        elif "Intravenous" in formulation_str:
            formulation_str = "Intravenous"

        sponsor_str = ""
        if len(sponsors) > 0:
            sponsor_str = " / ".join(sorted(sponsors))
        else:
            sponsor_str = (
                details.get("sponsor")
                or existing_meta.get(asset_name, {}).get("sponsor")
                or ""
            )

        if not sponsor_str:
            sponsor_str = "N/A"

        trial_links = []
        ct_sorted = sorted(
            matched_ct,
            key=lambda x: (
                0
                if x["status"].upper() in CT_ACTIVE
                or x["status"].upper() in CT_COMPLETED
                else 1
            ),
        )
        for ct in ct_sorted:
            trial_links.append(
                f"[{ct['id']}](https://clinicaltrials.gov/study/{ct['id']})"
            )

        for ch in matched_china:
            trial_links.append(
                f"[{ch['id']}](http://www.chinadrugtrials.org.cn/clinicaltrials.searchlistdetail.dhtml?reg_no={ch['id']})"
            )

        trials_str = "<br>".join(trial_links) if trial_links else "N/A"

        old_data = existing_meta.get(asset_name, {})
        modality = details.get("modality") or old_data.get("modality") or "N/A"
        indication = (
            details.get("indication")
            or old_data.get("indication")
            or "Gastric / GEJ Adenocarcinoma"
        )

        alias_str = " / ".join(aliases)
        name_cell = f"**{asset_name}**"
        if alias_str:
            name_cell += f"<br>*( {alias_str} )*"

        asset_rows.append(
            {
                "name": asset_name,
                "lead_val": lead_val,
                "is_discontinued": is_discontinued_globally,
                "row_markdown": f"| {name_cell} | {sponsor_str} | {modality} | {formulation_str} | {indication} | {lead_phase} | {trials_str} |",
            }
        )

    # Sort assets: active before discontinued, highest phase first
    asset_rows.sort(
        key=lambda x: (1 if x["is_discontinued"] else 0, -x["lead_val"], x["name"])
    )

    # Build Markdown table
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    md_lines = [
        "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for idx, row in enumerate(asset_rows, start=1):
        md_lines.append(row["row_markdown"].replace("| ", f"| {idx} | ", 1))

    md_content = "\n".join(md_lines) + "\n"
    aligned_content = md_table_to_text_table(md_content)

    output_path.write_text(aligned_content, encoding="utf-8")
    print(f"Successfully compiled column-aligned landscape table at: {output_path}")

    return aligned_content


def load_and_build_from_files(
    clinicaltrials_path: str | None,
    china_direct_path: str | None,
    config_path: str | None,
    existing_report_path: str | None,
    output_path: str,
    target_name: str = "",
    target_synonyms: list | None = None,
    database_json_dir: str | None = None,
) -> str:
    """
    High-level entry point: load raw JSON files and run build_landscape_table().

    Used by the CLI shim (__main__.py) and landscape_compiler_agent.py.
    """
    import glob as _glob

    # Load ClinicalTrials.gov data
    ct_data = {}
    if clinicaltrials_path and os.path.exists(clinicaltrials_path):
        print(f"Loading ClinicalTrials.gov data: {clinicaltrials_path}")
        with open(clinicaltrials_path, encoding="utf-8") as f:
            ct_data = json.load(f)

    # Glob-search and merge auxiliary trial JSON files
    search_dirs = []
    if clinicaltrials_path:
        search_dirs.append(os.path.dirname(os.path.abspath(clinicaltrials_path)))
    if database_json_dir and os.path.exists(database_json_dir):
        search_dirs.append(database_json_dir)

    seen_paths: set = set()
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for filepath in _glob.glob(os.path.join(s_dir, "*_trial*.json")):
            abs_path = os.path.abspath(filepath)
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)
            print(f"Merging auxiliary trials from: {filepath}")
            try:
                with open(filepath, encoding="utf-8") as f:
                    aux_data = json.load(f)
                if isinstance(aux_data, dict):
                    for nct_id, study in aux_data.items():
                        if nct_id.startswith("NCT"):
                            ct_data[nct_id] = study
            except Exception as e:
                print(f"Warning: Failed to merge auxiliary trials from {filepath}: {e}")

    # Load China CDE data
    china_data = []
    if china_direct_path and os.path.exists(china_direct_path):
        print(f"Loading ChinaDrugTrials direct data: {china_direct_path}")
        with open(china_direct_path, encoding="utf-8") as f:
            raw_china = json.load(f)
            china_data = raw_china.get("records", [])

    # Load or discover config
    config = {}
    if config_path:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with open(config_path, encoding="utf-8") as f:
            config_data = json.load(f)
        for k, v in config_data.items():
            if isinstance(v, list):
                config[k] = {"aliases": v}
            else:
                config[k] = v
    else:
        print(
            "No config file provided. Dynamically discovering assets from raw registries..."
        )
        target_synonyms_list = target_synonyms or []
        config = discover_config(
            ct_data,
            china_data,
            target_name,
            target_synonyms_list,
            database_json_dir=database_json_dir,
        )

    print(f"Total discovered/mapped assets: {len(config)}")

    existing_meta = parse_existing_report(existing_report_path, config)
    config, existing_meta = merge_config_duplicates(config, existing_meta)

    return build_landscape_table(
        ct_data, china_data, config, existing_meta, output_path
    )
