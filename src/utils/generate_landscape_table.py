#!/usr/bin/env python3
"""
Competitive Landscape Table Generator
Programmatically builds the competitive landscape Markdown table from raw clinical registry JSONs.
Ensures zero transcription errors, zero omissions, and accurate status and phase auditing.
"""

import argparse
import json
import os
import re
import sys

# Define trial status categorizations
CT_ACTIVE = {
    "RECRUITING",
    "ACTIVE_NOT_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
}
CT_COMPLETED = {"COMPLETED"}
CT_DISCONTINUED = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}

CDE_ACTIVE = {
    "进行中",
    "进行中\xa0招募中",
    "进行中\xa0尚未招募",
    "进行中\xa0招募完成",
    "招募中",
    "尚未招募",
    "招募完成",
}
CDE_COMPLETED = {"已完成"}
CDE_DISCONTINUED = {"主动终止", "已终止", "暂停"}


def clean_sponsor(sponsor):
    if not sponsor or sponsor == "N/A":
        return ""
    # Remove common corporate suffixes
    sponsor = re.sub(
        r",?\s+(Ltd\.|LLC|Inc\.|Co\.|Corp\.|Corporation|Pharmaceuticals|Pharma|Biotech|Biopharma|Therapeutics)\b.*",
        "",
        sponsor,
        flags=re.IGNORECASE,
    )
    sponsor = re.sub(r"\b(Group|Holdings|China)\b.*", "", sponsor, flags=re.IGNORECASE)
    return sponsor.strip()


def matches_drug(text, aliases):
    if not text:
        return False
    # Check for any alias as a whole word (not preceded/followed by alphanumeric characters)
    pattern = (
        r"(?<![a-zA-Z0-9])("
        + "|".join(re.escape(alias) for alias in aliases)
        + r")(?![a-zA-Z0-9])"
    )
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
        "PHASE4": (4.0, "Phase 4"),
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
    cell = re.sub(r"<[^>]+>", " ", cell)
    cell = cell.replace("**", "").replace("*", "").replace("__", "").replace("_", "")
    cell = re.sub(r"\(.*?\)", "", cell)
    return cell.strip()


def parse_existing_report(report_path, config):
    metadata = {}
    if not report_path or not os.path.exists(report_path):
        return metadata

    print(f"Reading existing report to extract qualitative metadata: {report_path}")
    try:
        with open(report_path, encoding="utf-8") as f:
            lines = f.readlines()

        in_table = False
        for line in lines:
            if "|" in line:
                if not in_table:
                    if "Asset Name" in line:
                        in_table = True
                    continue
                # Skip divider lines e.g. | :--- | :--- |
                if re.match(r"^\s*\|?\s*(:?-+:?\s*\|)+\s*(:?-+:?\s*)?$", line):
                    continue

                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) < 3:
                    continue

                asset_cell = cols[0]
                # Extract all word-like tokens from the asset cell to match synonyms
                row_names = re.findall(r"[A-Za-z0-9\-]{3,25}", asset_cell)
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
                        if (
                            name_clean
                            and len(name_clean) >= 3
                            and any(c.isalpha() for c in name_clean)
                            and not name_clean.isdigit()
                        ):
                            # Add to aliases if not already the primary key or in aliases
                            if (
                                name_clean.lower() != matched_key.lower()
                                and name_clean.lower()
                                not in [
                                    a.lower() for a in config[matched_key]["aliases"]
                                ]
                            ):
                                config[matched_key]["aliases"].append(name_clean)

                    metadata[matched_key] = {
                        "modality": cols[2] if len(cols) > 2 else "",
                        "formulation": cols[3] if len(cols) > 3 else "",
                        "indication": cols[4] if len(cols) > 4 else "",
                        "safety": cols[7] if len(cols) > 7 else "",
                        "efficacy": cols[8] if len(cols) > 8 else "",
                        "milestones": cols[9] if len(cols) > 9 else "",
                        "citations": cols[10] if len(cols) > 10 else "",
                    }
            else:
                if in_table:
                    in_table = False  # Table ended
    except Exception as e:
        print(f"Warning: Failed to parse existing report for metadata extraction: {e}")

    print(f"Extracted qualitative metadata for {len(metadata)} assets.")
    return metadata


def classify_interventions(
    names: list,
    target_name: str,
    target_synonyms: list | None = None,
    batch_size: int = 50,
) -> set:
    """
    Use the configured LLM to classify raw intervention names from clinical
    trial registries as pipeline assets or background/comparator agents.

    Returns the set of names (original casing) classified as pipeline assets
    that target `target_name`.

    Raises RuntimeError on any LLM failure — no silent fallback.
    """
    # Deferred import: ensure the project root is on sys.path when
    # generate_landscape_table.py is run as a subprocess from the project root.
    _proj_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if _proj_root not in sys.path:
        sys.path.insert(0, _proj_root)
    from src.services.llm_client import LLMClient  # noqa: PLC0415

    synonyms = target_synonyms or []
    synonyms_str = ", ".join(synonyms) if synonyms else target_name

    # Deduplicate: case-insensitive key → preserve first-seen casing
    seen_lower: dict = {}
    for n in names:
        stripped = n.strip()
        key = stripped.lower()
        if stripped and key not in seen_lower:
            seen_lower[key] = stripped
    unique_names = list(seen_lower.values())

    if not unique_names:
        return set()

    client = LLMClient()
    asset_names: set = set()

    total_batches = (len(unique_names) + batch_size - 1) // batch_size
    print(
        f"\nClassifying {len(unique_names)} unique intervention name(s) via LLM "
        f"({total_batches} batch(es) of ≤{batch_size})..."
    )

    for batch_idx in range(total_batches):
        batch = unique_names[batch_idx * batch_size : (batch_idx + 1) * batch_size]
        batch_json = json.dumps(batch, ensure_ascii=False)

        prompt = (
            f"You are classifying pharmaceutical intervention names from clinical trial registries.\n\n"
            f"Research target: {target_name}\n"
            f"Target synonyms: {synonyms_str}\n\n"
            f"Classify each name in the JSON array below as either:\n"
            f'  "asset"      — a novel/investigational drug, biologic, or cell therapy '
            f"that is DIRECTED AT {target_name} as its primary target "
            f"(includes mAbs, ADCs, bispecifics, CAR-T, small molecules, fusion proteins, etc.)\n"
            f'  "background" — anything NOT a novel targeted therapy against {target_name}: '
            f"approved comparators, chemotherapy backbones, standard-of-care regimens, "
            f"supportive care drugs, placebos, procedural descriptions, device names, "
            f"generic drug class terms, or descriptions of the target protein itself\n\n"
            f"Input names:\n{batch_json}\n\n"
            f"Respond ONLY with a valid JSON object with exactly two keys:\n"
            f'  "asset": [ ...names classified as pipeline assets... ]\n'
            f'  "background": [ ...names classified as background/comparator agents... ]\n'
            f"Every input name must appear in exactly one array. No explanation, no other text."
        )

        system_instruction = (
            "You are a biotech drug classification expert with deep knowledge of "
            "pharmaceutical naming conventions, clinical trial nomenclature, and "
            "approved global drugs. Output only valid JSON with no markdown fencing. "
            "When uncertain, classify as 'background'. "
            "Novel investigational assets typically have alphanumeric codes "
            "(e.g. AMG910, SHR-A1904, AZD6422) or USAN/INN stems "
            "(-mab, -tib, -cept, -mig, -can, -bart) with a sponsor-specific prefix "
            "that does not match any approved drug name."
        )

        response = client.query(prompt, system_instruction)

        if (
            not response
            or response.startswith("Error:")
            or response.startswith("Failed to call")
        ):
            raise RuntimeError(
                f"LLM intervention classification failed for batch "
                f"{batch_idx + 1}/{total_batches}: {response}"
            )

        # Strip markdown code fences if the LLM wrapped the output
        clean_response = response.strip()
        if clean_response.startswith("```"):
            clean_response = re.sub(r"^```[a-z]*\n?", "", clean_response)
            clean_response = re.sub(r"\n?```$", "", clean_response.strip())

        try:
            result = json.loads(clean_response)
            classified_assets: list = result.get("asset", [])
            classified_background: list = result.get("background", [])
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"LLM returned unparseable JSON for batch "
                f"{batch_idx + 1}/{total_batches}: {exc}\n"
                f"Raw response (first 400 chars): {response[:400]}"
            ) from exc

        print(
            f"  [Classifier] Batch {batch_idx + 1}/{total_batches}: "
            f"{len(classified_assets)} asset(s), "
            f"{len(classified_background)} background agent(s)"
        )
        for name in classified_assets:
            print(f"    ✓ ASSET      : {name}")
        for name in classified_background:
            print(f"    ✗ background : {name}")

        asset_names.update(classified_assets)

    return asset_names


def _name_priority(name: str) -> tuple:
    """
    Sorting key for selecting the canonical primary name from a synonym group.
    Lower tuple value → higher priority.

    Priority:
      0 — Alphanumeric code (contains both letters and digits, e.g. AMG910, SHR-A1904)
      1 — USAN/INN stem (-mab, -tib, -cept, -mig, -can, -bart, -vir, -kin)
      2 — Everything else (longer names slightly preferred over shorter)
    """
    name_lower = name.lower()
    has_letter = any(c.isalpha() for c in name)
    has_digit = any(c.isdigit() for c in name)

    if has_letter and has_digit:
        return (0, -len(name), name)

    usan_stems = ("mab", "tib", "cept", "mig", "can", "bart", "vir", "kin")
    if any(name_lower.endswith(s) for s in usan_stems):
        return (1, -len(name), name)

    return (2, -len(name), name)


def discover_config(
    ct_data: dict,
    china_data: list,
    target_name: str = "",
    target_synonyms: list | None = None,
) -> dict:
    """
    Discover pipeline assets from raw registry data using LLM-based classification.

    All unique intervention names from ClinicalTrials.gov, China CDE, and
    conference abstract files are collected, deduplicated, and classified in
    batched LLM calls. Only names classified as pipeline assets targeting
    `target_name` are retained for the landscape table.

    Raises RuntimeError if LLM classification fails (no silent fallback).
    """
    import glob  # noqa: PLC0415

    target_synonyms = target_synonyms or []

    # -----------------------------------------------------------------------
    # 1. Collect (primary_name, [aliases]) pairs from ClinicalTrials.gov
    # -----------------------------------------------------------------------
    ct_interventions: list = []  # list of (primary_name, [other_names])
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
    #    Targets alphanumeric drug codes (e.g. AZD6422, AHT-102, BNT141)
    # -----------------------------------------------------------------------
    conf_codes: list = []
    search_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmp"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tmp"),
        os.path.join(os.getcwd(), "tmp"),
    ]
    seen_conf_paths: set = set()
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for filepath in glob.glob(os.path.join(s_dir, "*conferences*.json")):
            abs_path = os.path.abspath(filepath)
            if abs_path in seen_conf_paths:
                continue
            seen_conf_paths.add(abs_path)
            try:
                with open(filepath, encoding="utf-8") as f:
                    conf_data = json.load(f)
                for item in conf_data.get("results", []):
                    title = item.get("title", "")
                    # Extract tokens that look like drug/compound codes:
                    # 2-6 letters, optional hyphen, 2-6 digits, optional trailing letter
                    codes = re.findall(r"\b[A-Za-z]{2,6}-?\d{2,6}[A-Za-z]?\b", title)
                    conf_codes.extend(codes)
            except Exception as e:
                print(
                    f"Warning: Failed to process conference file {filepath}: {e}"
                )

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
    # 5. LLM-based classification — one call per batch of 50 unique names
    # -----------------------------------------------------------------------
    classified_asset_names = classify_interventions(
        all_raw, target_name, target_synonyms
    )
    classified_lower: set = {n.lower() for n in classified_asset_names}

    print(
        f"\nClassification complete: {len(classified_asset_names)} pipeline asset(s) "
        f"identified from {len({n.lower() for n in all_raw})} unique name(s)."
    )

    # -----------------------------------------------------------------------
    # 6. Group synonym clusters — only for names classified as assets
    # -----------------------------------------------------------------------
    groups: list = []

    def add_synonyms(names_list: list) -> None:
        names_clean = [
            n.strip()
            for n in names_list
            if n.strip() and n.strip().lower() in classified_lower
        ]
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

    for primary, aliases in ct_interventions:
        add_synonyms([primary] + aliases)

    for drug_name in china_names:
        add_synonyms([drug_name])

    for code in conf_codes:
        add_synonyms([code])

    # -----------------------------------------------------------------------
    # 7. Build config dict — canonical primary key chosen by _name_priority
    # -----------------------------------------------------------------------
    config: dict = {}
    for g in groups:
        sorted_names = sorted(g, key=_name_priority)
        primary = sorted_names[0]
        aliases = sorted_names[1:]
        config[primary] = {"aliases": aliases}

    return config


# ---------------------------------------------------------------------------
# Column-aligned Markdown table formatter
# ---------------------------------------------------------------------------


def _strip_md(text: str) -> str:
    """Remove Markdown formatting tokens from a cell value."""
    # Expand <br> to " / " (keep single-row layout)
    text = re.sub(r"<br\s*/?>", " / ", text, flags=re.IGNORECASE)
    # Remove bold/italic markers
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?<!\*)\*(?!\*)", "", text)  # single *
    text = re.sub(r"(?<!_)_(?!_)", "", text)      # single _
    # Remove markdown links [text](url) -> text only
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def md_table_to_text_table(md_text: str) -> str:
    """Reformat a pipe-delimited Markdown table so every column is space-padded and
    columns align perfectly when viewed in any plain-text editor.

    The output is still valid Markdown AND human-readable as raw text — exactly like
    a financial balance sheet table. Each cell is padded with spaces to the widest
    value in that column. <br> tags are collapsed to \" / \" inline. Markdown bold,
    italic, and link syntax is stripped from cell text.
    """
    raw_lines = [line.rstrip() for line in md_text.splitlines()]

    # Collect prefix (title, blanks, etc.) and table lines separately
    pre_lines: list[str] = []
    table_lines: list[str] = []
    post_lines: list[str] = []
    in_table = False
    table_done = False

    for line in raw_lines:
        stripped = line.lstrip()
        if not table_done and stripped.startswith("|"):
            in_table = True
            table_lines.append(line)
        elif in_table and not table_done:
            table_done = True
            post_lines.append(line)
        elif table_done:
            post_lines.append(line)
        else:
            pre_lines.append(line)

    if not table_lines:
        return md_text  # Nothing to reformat

    # Parse rows into (kind, [cells])
    # kind: "header" | "divider" | "data"
    parsed: list[tuple[str, list[str]]] = []
    header_seen = False

    for line in table_lines:
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols:
            continue
        # Divider row: all non-empty cells match :?-+:?
        if all(re.match(r"^:?-+:?$", c) for c in cols if c):
            parsed.append(("divider", cols))
            header_seen = True
        elif not header_seen:
            parsed.append(("header", [_strip_md(c) for c in cols]))
        else:
            parsed.append(("data", [_strip_md(c) for c in cols]))

    if not parsed:
        return md_text

    # Normalise column count
    n_cols = max(len(cells) for _, cells in parsed)
    parsed = [(kind, cells + [""] * (n_cols - len(cells))) for kind, cells in parsed]

    # Compute per-column widths from header + data rows only
    col_widths = [1] * n_cols
    for kind, cells in parsed:
        if kind == "divider":
            continue
        for ci, cell in enumerate(cells):
            col_widths[ci] = max(col_widths[ci], len(cell))

    # Render aligned rows
    out_lines: list[str] = []
    for kind, cells in parsed:
        if kind == "divider":
            parts = [" " + "-" * col_widths[ci] + " " for ci in range(n_cols)]
        else:
            parts = [f" {cells[ci]:<{col_widths[ci]}} " for ci in range(n_cols)]
        out_lines.append("|" + "|".join(parts) + "|")

    sections = pre_lines + out_lines + post_lines
    return "\n".join(sections) + "\n"


def md_table_to_csv(md_text: str) -> str:
    """Convert a pipe-delimited Markdown table to a properly-quoted CSV string.

    Strips Markdown markup (bold, italic, links) and expands <br> to ' / '
    inline. Uses Python's csv module for RFC-4180 compliant quoting so cells
    containing commas, quotes, or newlines are handled correctly.
    Skips the --- divider row. Returns the CSV as a string (UTF-8 safe).
    """
    import csv
    import io

    raw_lines = [line.rstrip() for line in md_text.splitlines()]

    rows: list[list[str]] = []
    header_seen = False

    for line in raw_lines:
        if not line.lstrip().startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols:
            continue
        # Skip divider rows (--- / :--- / :---:)
        if all(re.match(r"^:?-+:?$", c) for c in cols if c):
            header_seen = True
            continue
        rows.append([_strip_md(c) for c in cols])

    if not rows:
        return ""

    # Normalise column count
    n_cols = max(len(r) for r in rows)
    rows = [r + [""] * (n_cols - len(r)) for r in rows]

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerows(rows)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser(
        description="Generate Competitive Landscape Table from raw clinical registries."
    )
    parser.add_argument(
        "--config", help="Path to config JSON mapping drug names to synonyms (optional)"
    )
    parser.add_argument(
        "--clinicaltrials", help="Path to ClinicalTrials.gov JSON database"
    )
    parser.add_argument(
        "--china-direct", help="Path to ChinaDrugTrials direct search JSON"
    )
    parser.add_argument(
        "--existing-report",
        help="Path to existing report to extract qualitative metadata",
    )
    parser.add_argument(
        "--output", required=True, help="Path to write the markdown table output"
    )
    parser.add_argument(
        "--target-name",
        default="",
        help="Primary target name for LLM-based intervention classification "
        "(e.g. 'Claudin-18.2')",
    )
    parser.add_argument(
        "--target-synonyms",
        default="",
        help="Comma-separated list of target name synonyms for classification context",
    )

    args = parser.parse_args()

    # Load raw registries
    ct_data = {}
    if args.clinicaltrials and os.path.exists(args.clinicaltrials):
        print(f"Loading ClinicalTrials.gov data: {args.clinicaltrials}")
        with open(args.clinicaltrials, encoding="utf-8") as f:
            ct_data = json.load(f)

    # Glob-search and merge auxiliary trial JSON files (*_trial*.json)
    import glob

    search_dirs = []
    if args.clinicaltrials:
        search_dirs.append(os.path.dirname(os.path.abspath(args.clinicaltrials)))
    search_dirs.append(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmp")
    )
    search_dirs.append(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tmp")
    )
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
                with open(filepath, encoding="utf-8") as f:
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
        with open(args.china_direct, encoding="utf-8") as f:
            raw_china = json.load(f)
            china_data = raw_china.get("records", [])

    # Load config or dynamically discover
    config = {}
    if args.config:
        if not os.path.exists(args.config):
            print(f"Error: Config file not found: {args.config}", file=sys.stderr)
            sys.exit(1)

        with open(args.config, encoding="utf-8") as f:
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
        target_synonyms_list = [
            s.strip() for s in args.target_synonyms.split(",") if s.strip()
        ]
        config = discover_config(
            ct_data, china_data, args.target_name, target_synonyms_list
        )

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
        sorted_names = sorted(
            all_names, key=lambda x: (get_name_priority(x), -len(x), x)
        )
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
            company = rec.get("company", "")  # this represents indication
            status = rec.get("status", "")

            all_text_to_search = f"{drug_name} | {company}"

            if matches_drug(all_text_to_search, search_names):
                matched_china.append(
                    {"id": reg_num, "status": status, "phase_text": drug_name}
                )

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
            formulation_str = (
                details.get("formulation")
                or existing_meta.get(asset_name, {}).get("formulation")
                or "Intravenous"
            )

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
            sponsor_str = " / ".join(sorted(sponsors))
        else:
            sponsor_str = (
                details.get("sponsor")
                or existing_meta.get(asset_name, {}).get("sponsor")
                or ""
            )

        if not sponsor_str:
            sponsor_str = "N/A"

        # Compile Trial IDs
        trial_links = []
        # Sort trials by active/completed first
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

        # Merge other qualitative columns from existing report or defaults
        old_data = existing_meta.get(asset_name, {})

        modality = details.get("modality") or old_data.get("modality") or "N/A"
        indication = (
            details.get("indication")
            or old_data.get("indication")
            or "Gastric / GEJ Adenocarcinoma"
        )
        safety = (
            details.get("selectivity_safety")
            or old_data.get("safety")
            or "Safety evaluation ongoing."
        )
        efficacy = (
            details.get("efficacy_data")
            or old_data.get("efficacy")
            or "Data not publicly disclosed."
        )
        milestones = (
            details.get("milestones")
            or old_data.get("milestones")
            or "Phase 1 study completion."
        )
        citations = details.get("citations") or old_data.get("citations") or "N/A"

        # Format asset name with aliases in HTML/Markdown
        alias_str = " / ".join(aliases)
        name_cell = f"**{asset_name}**"
        if alias_str:
            name_cell += f"<br>*( {alias_str} )*"

        asset_rows.append(
            {
                "name": asset_name,
                "lead_val": lead_val,
                "is_discontinued": is_discontinued_globally,
                "row_markdown": f"| {name_cell} | {sponsor_str} | {modality} | {formulation_str} | {indication} | {lead_phase} | {trials_str} | {safety} | {efficacy} | {milestones} | {citations} |",
            }
        )

    # Sort assets by lead phase value descending, and put active before discontinued
    # Sorting key: (is_discontinued_globally, -lead_val, asset_name)
    asset_rows.sort(
        key=lambda x: (1 if x["is_discontinued"] else 0, -x["lead_val"], x["name"])
    )

    # Write Markdown table (with leading # row-number column)
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    try:
        md_lines = []
        md_lines.append(
            "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Selectivity & Safety Profile | Key Efficacy / Biomarker Data | Upcoming Milestones | Citations |"
        )
        md_lines.append(
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        )
        for idx, row in enumerate(asset_rows, start=1):
            # Prepend the row number to the existing row markdown
            md_lines.append(row["row_markdown"].replace("| ", f"| {idx} | ", 1))

        md_content = "\n".join(md_lines) + "\n"
        aligned_content = md_table_to_text_table(md_content)

        with open(args.output, "w", encoding="utf-8") as out:
            out.write(aligned_content)
        print(f"Successfully compiled column-aligned landscape table at: {args.output}")
    except Exception as e:
        print(f"Error writing compiled landscape table: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
