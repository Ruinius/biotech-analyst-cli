"""
Pure string / parsing utilities for competitive landscape table generation.

Functions moved from the generate_landscape_table.py monolith (§3 decomposition).
"""

import re

# ---------------------------------------------------------------------------
# Trial status categorizations
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# String utility helpers
# ---------------------------------------------------------------------------


def clean_sponsor(sponsor: str) -> str:
    """Strip common corporate suffixes from sponsor name."""
    if not sponsor or sponsor == "N/A":
        return ""
    sponsor = re.sub(
        r",?\s+(Ltd\.|LLC|Inc\.|Co\.|Corp\.|Corporation|Pharmaceuticals|Pharma|Biotech|Biopharma|Therapeutics)\b.*",
        "",
        sponsor,
        flags=re.IGNORECASE,
    )
    sponsor = re.sub(r"\b(Group|Holdings|China)\b.*", "", sponsor, flags=re.IGNORECASE)
    return sponsor.strip()


def matches_drug(text: str, aliases: list) -> bool:
    """Return True if any alias appears as a whole word in text."""
    if not text:
        return False
    pattern = (
        r"(?<![a-zA-Z0-9])("
        + "|".join(re.escape(alias) for alias in aliases)
        + r")(?![a-zA-Z0-9])"
    )
    return bool(re.search(pattern, text, re.IGNORECASE))


def parse_ct_phase(phases_list: list) -> tuple:
    """Parse ClinicalTrials.gov phase list into (display_string, numeric_value)."""
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


def parse_text_phase(text: str) -> tuple:
    """Parse a free-text phase description into (display_string, numeric_value)."""
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


def detect_formulation(text_list: list) -> list:
    """Detect administration route keywords from a list of text strings."""
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


def parse_asset_and_aliases(cell: str) -> tuple:
    """
    Extract primary asset name and alias list from a Markdown/HTML table cell.

    Kept as a fallback regex parser per the backward-compatibility contract (§3).
    Will be superseded by LLM-based resolution in §2.
    """
    # Clean HTML tags
    cell_clean = re.sub(r"<[^>]+>", " ", cell)

    # Extract primary name (typically bolded like **Zolbetuximab**)
    primary_match = re.search(r"\*\*(.*?)\*\*", cell)
    if primary_match:
        primary_name = primary_match.group(1).strip()
    else:
        primary_name = re.split(r"[\(（<]", cell_clean)[0].strip()
        primary_name = (
            primary_name.replace("**", "")
            .replace("*", "")
            .replace("__", "")
            .replace("_", "")
            .strip()
        )

    aliases = []
    paren_matches = re.findall(r"[\(（](.*?)[\)）]", cell_clean)
    for match in paren_matches:
        parts = re.split(r"[/,]", match)
        for part in parts:
            part_clean = part.replace("*", "").replace("_", "").strip()
            if not part_clean:
                continue

            part_lower = part_clean.lower()
            rejected_words = {
                "with",
                "plus",
                "and",
                "or",
                "chemotherapy",
                "immunotherapy",
                "placebo",
                "regimen",
                "therapy",
                "standard of care",
                "soc",
                "combination",
                "cohort",
                "dose",
                "mg",
                "kg",
                "group",
                "study",
                "trial",
                "active",
                "comparator",
                "control",
                "monotherapy",
                "treatment",
                "investigational",
                "drug",
                "biologic",
                "cell",
                "her2",
                "cldn18.2",
                "egfr",
                "claudin",
                "claudin-18.2",
                "cldn",
                "claudin18.2",
                "target",
                "directed",
            }

            words = re.findall(r"[a-z0-9\-]+", part_lower)
            if any(w in rejected_words for w in words):
                continue

            if len(part_clean) >= 3 and not part_clean.isdigit():
                if part_clean.lower() != primary_name.lower():
                    if part_clean not in aliases:
                        aliases.append(part_clean)

    return primary_name, aliases


def clean_cell_to_name(cell: str) -> str:
    """Extract just the primary name from a table cell."""
    primary, _ = parse_asset_and_aliases(cell)
    return primary


def _name_priority(name: str) -> tuple:
    """
    Sorting key for selecting the canonical primary name from a synonym group.

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


def normalize_drug_name(name: str) -> str:
    """Normalize a drug name: lowercase, strip punctuation/spaces/hyphens."""
    if not name:
        return ""
    return re.sub(r"[\s\-_\.,/\\]", "", name).lower()
