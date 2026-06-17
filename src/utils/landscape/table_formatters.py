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

    # Penalize combination regimens, trial titles, or messy parentheticals by shifting priority class
    has_combo_chars = any(c in name for c in (",", "+", "/", "(", ")", "（", "）"))
    has_combo_words = any(
        w in name_lower for w in ["combined", "combination", "plus", "and", "with"]
    )
    is_too_long = len(name) > 30

    penalty = 3 if (has_combo_chars or has_combo_words or is_too_long) else 0

    has_letter = any(c.isalpha() for c in name)
    has_digit = any(c.isdigit() for c in name)

    if has_letter and has_digit:
        return (0 + penalty, -len(name), name)

    usan_stems = ("mab", "tib", "cept", "mig", "can", "bart", "vir", "kin")
    if any(name_lower.endswith(s) for s in usan_stems):
        return (1 + penalty, -len(name), name)

    return (2 + penalty, -len(name), name)


def normalize_drug_name(name: str) -> str:
    """Normalize a drug name: lowercase, strip punctuation/spaces/hyphens."""
    if not name:
        return ""
    return re.sub(r"[\s\-_\.,/\\]", "", name).lower()


# ---------------------------------------------------------------------------
# Static noise cleansing and filtering blocklists
# ---------------------------------------------------------------------------

EXCLUDE_LOWER = {
    "placebo",
    "chemotherapy",
    "chemo",
    "standard of care",
    "investigator choice",
    "investigator's choice",
    "paclitaxel",
    "docetaxel",
    "nab-paclitaxel",
    "gemcitabine",
    "oxaliplatin",
    "capecitabine",
    "cisplatin",
    "carboplatin",
    "pembrolizumab",
    "nivolumab",
    "sintilimab",
    "toripalimab",
    "dostarlimab",
    "ramucirumab",
    "leucovorin",
    "fluorouracil",
    "5-fluorouracil",
    "5-fu",
    "irinotecan",
    "liposomal irinotecan",
    "folflri",
    "folfiri",
    "folfox",
    "mfolfox6",
    "folfirinox",
    "mfolfirinox",
    "capox",
    "flot",
    "radiation",
    "surgery",
    "saline",
    "dexamethasone",
    "prednisone",
    "ondansetron",
    "aprepitant",
    "normal saline",
    "control",
    "chemotherapies",
    "placebos",
    "combination",
    "combo",
    "regimen",
    "antibody",
    "cart",
    "car-t",
    "adc",
    "bi-specific",
    "bispecific",
    "monoclonal",
    "recombinant",
    "infusion",
    "injection",
    "therapy",
    "cell",
    "cells",
    "autologous",
    "vaccine",
    "dendritic",
    "peptides",
    "peptide",
    "vector",
    "plasmid",
    "imaging",
    "agent",
    "agents",
    "pet",
    "tracer",
    "redirected",
    "engineered",
    "chimeric",
    "targeting",
    "positive",
    "expressing",
    "negative",
    "expression",
    "high-expressing",
    "low-expressing",
    "positive-expression",
    "durvalumab",
    "atezolizumab",
    "avelumab",
    "ipilimumab",
    "tremelimumab",
    "penpulimab",
    "camrelizumab",
    "adebrelimab",
    "retifanlimab",
    "zimberelimab",
    "serplulimab",
    "pucoclimab",
    "adegrelimab",
    "tislelizumab",
    "cadonilimab",
    "cardonilizumab",
    "trastuzumab",
    "pertuzumab",
    "bevacizumab",
    "cetuximab",
    "panitumumab",
    "erlotinib",
    "gefitinib",
    "afatinib",
    "osimertinib",
    "lapatinib",
    "neratinib",
    "tucatinib",
    "folinic",
    "folinic acid",
    "l-leucovorin",
    "leucovorin calcium",
    "folic acid",
    "folate",
    "zoledronic",
    "zoledronic acid",
    "denosumab",
    "fosaprepitant",
    "granisetron",
    "palonosetron",
    "pegfilgrastim",
    "filgrastim",
    "tancolux",
    "epirubicin",
    "doxorubicin",
    "methotrexate",
    "cyclophosphamide",
    "fludarabine",
    "etoposide",
    "vincristine",
    "vinblastine",
    "vinorelbine",
    "temozolomide",
    "dacarbazine",
    "procarbazine",
    "carmustine",
    "lomustine",
    "streptozocin",
    "mitomycin",
    "bleomycin",
    "dactinomycin",
    "daunorubicin",
    "idarubicin",
    "mitoxantrone",
    "plicamycin",
    "hydroxyurea",
    "asparaginase",
    "pegaspargase",
    "bortezomib",
    "carfilzomib",
    "ixazomib",
    "thalidomide",
    "lenalidomide",
    "pomalidomide",
    "olaparib",
    "rucaparib",
    "niraparib",
    "talazoparib",
    "veliparib",
    "fruquintinib",
    "surufatinib",
    "donafenib",
    "regorafenib",
    "sorafenib",
    "sunitinib",
    "pazopanib",
    "axitinib",
    "cabozantinib",
    "lenvatinib",
    "vandetanib",
    "nintedanib",
    "tivozanib",
    "alectinib",
    "crizotinib",
    "ceritinib",
    "brigatinib",
    "lorlatinib",
    "dabrafenib",
    "vemurafenib",
    "encorafenib",
    "trametinib",
    "cobimetinib",
    "binimetinib",
    "selumetinib",
    "everolimus",
    "temsirolimus",
    "sirolimus",
    "sox",
    "xelox",
    "folfoxiri",
    "folfox4",
    "folfox6",
    "mfolfox",
    "gemcitabine+albumin-bound",
    "gemcitabine+nab-paclitaxel",
    "gem/nab-paclitaxel",
    "gem-abx",
    "albumin-bound",
    "abraxane",
    "keytruda",
    "opdivo",
    "tecentriq",
    "imfinzi",
    "libtayo",
    "jemperli",
    "erbitux",
    "vectibix",
    "avastin",
    "cyramza",
    "herceptin",
    "perjeta",
    "kadcyla",
    "enhertu",
    "alunbrig",
    "alecensa",
    "xalkori",
    "zykadia",
    "lorbrena",
    "tafinlar",
    "zelboraf",
    "braftovi",
    "mekinist",
    "cotellic",
    "mektovi",
    "koselugo",
    "afinitor",
    "torisel",
    "rapamune",
    "inlyta",
    "sutent",
    "votrient",
    "nexavar",
    "stivarga",
    "caprelsa",
    "lartruvo",
    "portrazza",
    "xofigo",
    "ziga",
    "yondelis",
    "halaven",
    "ixempra",
    "elsparc",
    "erwinase",
    "oncaspar",
    "velcade",
    "kyprolis",
    "ninlaro",
    "thalomid",
    "revlimid",
    "pomalyst",
    "lynparza",
    "rubraca",
    "zejula",
    "talzenna",
    "eluate",
    "support",
    "care",
    "assignment",
    "single",
    "group",
    "open-label",
    "dose-escalation",
    "escalation",
    "expansion",
    "dose",
    "cohort",
    "arm",
    "randomized",
    "double-blind",
    "efficacy",
    "safety",
    "tolerability",
    "pharmacokinetics",
    "bioavailability",
    "pharmacodynamics",
    "immunogenicity",
    "maximum",
    "tolerated",
    "dose-limiting",
    "toxicity",
    "toxicities",
    "adverse",
    "events",
    "reaction",
    "reactions",
    "syndicated",
    "registry",
    "scraped",
    "scrape",
    "scraping",
    "scrub",
    "clean",
    "format",
    "report",
    "document",
    "file",
    "json",
    "txt",
    "md",
    "pdf",
    "html",
    "xml",
    "csv",
    "insulin",
    "lispro",
    "humalog",
    "novolog",
    "apidra",
    "fiasp",
    "lyumjev",
    "admelog",
}

GENERIC_WORDS = {
    "placebo",
    "chemotherapy",
    "standard of care",
    "investigator choice",
    "investigator's choice",
    "radiation",
    "surgery",
    "saline",
    "control",
    "combination",
    "combo",
    "regimen",
    "antibody",
    "cart",
    "car-t",
    "adc",
    "bi-specific",
    "bispecific",
    "monoclonal",
    "recombinant",
    "infusion",
    "injection",
    "therapy",
    "cell",
    "cells",
    "autologous",
    "vaccine",
    "dendritic",
    "peptides",
    "peptide",
    "vector",
    "plasmid",
    "imaging",
    "agent",
    "agents",
    "pet",
    "tracer",
    "redirected",
    "engineered",
    "chimeric",
    "targeting",
    "positive",
    "expressing",
    "negative",
    "expression",
    "high-expressing",
    "low-expressing",
    "positive-expression",
    "support",
    "care",
    "assignment",
    "single",
    "group",
    "open-label",
    "dose-escalation",
    "escalation",
    "expansion",
    "dose",
    "cohort",
    "arm",
    "randomized",
    "double-blind",
    "efficacy",
    "safety",
    "tolerability",
    "pharmacokinetics",
    "bioavailability",
    "pharmacodynamics",
    "immunogenicity",
    "chemo",
    "placebos",
    "comb",
    "regim",
}


def clean_drug_name(
    name: str, target_name: str = "", target_synonyms: list | None = None
) -> str:
    """
    Clean a raw intervention or drug name programmatically by removing HTML, splitting
    combinations, checking exclusions/stems/generic terms, and isolating the asset code/name.
    """
    if not name:
        return ""

    # Build target terms for exclusion checks (we don't want target name itself as an asset)
    target_terms = set()
    if target_name:
        target_terms.add(target_name.lower())
        target_terms.add(re.sub(r"[^a-z0-9]", "", target_name.lower()))
    if target_synonyms:
        for ts in target_synonyms:
            target_terms.add(ts.lower())
            target_terms.add(re.sub(r"[^a-z0-9]", "", ts.lower()))

    # Strip HTML tags
    name = re.sub(r"<[^>]+>", " ", name)

    # Split by common combinators, preserving hyphenated names
    parts = re.split(
        r"[\+\/]|联合|和|\bcombined with\b|\bplus\b|\band\b", name, flags=re.IGNORECASE
    )
    for part in parts:
        part_clean = part.strip()
        # Find alphanumeric patterns
        codes = re.findall(r"[A-Za-z0-9\-]{3,15}", part_clean)
        valid_codes = []
        for c in codes:
            c_lower = c.lower()
            c_alnum = re.sub(r"[^a-z0-9]", "", c_lower)
            if c_lower in EXCLUDE_LOWER or c_alnum in EXCLUDE_LOWER:
                continue
            if c_lower in target_terms or c_alnum in target_terms:
                continue
            if any(gw in c_lower for gw in GENERIC_WORDS):
                continue
            if len(c) < 3:
                continue

            has_letter = any(char.isalpha() for char in c)
            has_digit = any(char.isdigit() for char in c)

            # Check USAN/INN stems
            usan_stems = (
                "mab",
                "tug",
                "mig",
                "bart",
                "tib",
                "cept",
                "can",
                "parib",
                "ciclib",
                "degib",
            )
            is_stem = len(c) >= 5 and any(c_lower.endswith(s) for s in usan_stems)

            # Known biotech assets for early validation
            is_known_name = any(
                k in c_lower
                for k in [
                    "zolbet",
                    "osem",
                    "vyloy",
                    "spevat",
                    "givas",
                    "greson",
                    "sones",
                    "satric",
                    "satri",
                    "ribomab",
                    "paxalisib",
                    "erasca",
                    "medicinova",
                ]
            )

            if (has_letter and has_digit) or is_stem or is_known_name:
                c_clean = c.strip("-").strip()
                c_clean_lower = c_clean.lower()
                c_clean_alnum = re.sub(r"[^a-z0-9]", "", c_clean_lower)
                if (
                    c_clean
                    and c_clean_lower not in EXCLUDE_LOWER
                    and c_clean_lower not in target_terms
                    and c_clean_alnum not in target_terms
                ):
                    if not any(gw in c_clean_lower for gw in GENERIC_WORDS):
                        valid_codes.append(c_clean)

        if valid_codes:
            return valid_codes[0]

    # Fallback to cleaning the first split part
    first_part = parts[0].strip()
    first_part = re.sub(r"\(.*?\)", "", first_part)
    first_part = re.sub(r"（.*?）", "", first_part)
    for prefix in [
        "注射用",
        "重组人源化",
        "单克隆抗体",
        "自体",
        "细胞",
        "注射液",
        "注射用重组",
    ]:
        first_part = first_part.replace(prefix, "")
    first_part = first_part.replace("抗体", "")
    first_part_clean = first_part.strip()

    first_part_lower = first_part_clean.lower()
    first_part_alnum = re.sub(r"[^a-z0-9]", "", first_part_lower)

    if (
        first_part_lower not in EXCLUDE_LOWER
        and first_part_lower not in target_terms
        and first_part_alnum not in target_terms
    ):
        if not any(gw in first_part_lower for gw in GENERIC_WORDS):
            # Try to extract English words if Chinese characters are present
            eng_words = re.findall(r"[A-Za-z0-9\-]{3,15}", first_part_clean)
            if eng_words:
                ret = eng_words[0]
                ret_lower = ret.lower()
                ret_alnum = re.sub(r"[^a-z0-9]", "", ret_lower)
                if (
                    ret_lower not in EXCLUDE_LOWER
                    and ret_lower not in target_terms
                    and ret_alnum not in target_terms
                ):
                    if not any(gw in ret_lower for gw in GENERIC_WORDS):
                        return ret
            return first_part_clean

    return ""


def extract_china_drug(
    drug_name: str, target_name: str = "", target_synonyms: list | None = None
) -> str:
    """Extract and clean drug name from China CDE records."""
    if not drug_name:
        return ""
    main_part = re.split(r"[\(（]", drug_name)[0]
    cleaned = clean_drug_name(main_part, target_name, target_synonyms)
    if cleaned:
        return cleaned

    # Search in parentheticals/codes
    codes = re.findall(r"[A-Za-z0-9\-]{3,15}", drug_name)
    target_terms = set()
    if target_name:
        target_terms.add(target_name.lower())
        target_terms.add(re.sub(r"[^a-z0-9]", "", target_name.lower()))
    if target_synonyms:
        for ts in target_synonyms:
            target_terms.add(ts.lower())
            target_terms.add(re.sub(r"[^a-z0-9]", "", ts.lower()))

    for c in codes:
        c_lower = c.lower()
        c_alnum = re.sub(r"[^a-z0-9]", "", c_lower)
        if c_lower in EXCLUDE_LOWER or c_alnum in EXCLUDE_LOWER:
            continue
        if c_lower in target_terms or c_alnum in target_terms:
            continue
        if any(gw in c_lower for gw in GENERIC_WORDS):
            continue
        has_letter = any(char.isalpha() for char in c)
        has_digit = any(char.isdigit() for char in c)
        usan_stems = (
            "mab",
            "tug",
            "mig",
            "bart",
            "tib",
            "cept",
            "can",
            "parib",
            "ciclib",
            "degib",
        )
        is_stem = len(c) >= 5 and any(c_lower.endswith(s) for s in usan_stems)
        is_known_name = any(
            k in c_lower
            for k in [
                "zolbet",
                "osem",
                "vyloy",
                "spevat",
                "givas",
                "greson",
                "sones",
                "satric",
                "satri",
                "ribomab",
                "paxalisib",
                "erasca",
                "medicinova",
            ]
        )
        if (has_letter and has_digit) or is_stem or is_known_name:
            c_clean = c.strip("-").strip()
            c_clean_lower = c_clean.lower()
            if (
                c_clean
                and c_clean_lower not in EXCLUDE_LOWER
                and c_clean_lower not in target_terms
            ):
                if not any(gw in c_clean_lower for gw in GENERIC_WORDS):
                    return c_clean
    return ""


class UnionFind:
    """Disjoint-Set Union (Union-Find) data structure for clustering synonyms."""

    def __init__(self):
        self.parent = {}

    def find(self, item):
        if item not in self.parent:
            self.parent[item] = item
            return item
        path = []
        while self.parent[item] != item:
            path.append(item)
            item = self.parent[item]
        for node in path:
            self.parent[node] = item
        return item

    def union(self, item1, item2):
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 != root2:
            self.parent[root1] = root2


def cluster_synonym_groups(synonym_sets: list[set[str]]) -> list[set[str]]:
    """
    Cluster synonym sets programmatically using Union-Find.

    If set A and set B share any element (case-insensitively or via normalized name),
    they are merged into the same cluster.
    """
    uf = UnionFind()

    # We map normalized/lowercase names to their exact original name in our vocabulary
    exact_names = {}

    # Helper to canonicalize representation for matching
    def canonical_reprs(name):
        return [name.lower(), normalize_drug_name(name)]

    # First pass: map canonical representations to parent-child references
    all_names = set()
    for s in synonym_sets:
        for val in s:
            if not val:
                continue
            all_names.add(val)
            for rep in canonical_reprs(val):
                exact_names[rep] = val

    # Initialize union-find entries for all exact names
    for name in all_names:
        uf.find(name)

    # Union names within each set
    for s in synonym_sets:
        lst = [val for val in s if val]
        if len(lst) > 1:
            first = lst[0]
            for val in lst[1:]:
                uf.union(first, val)

    # Union names across sets that share normalized representations
    # E.g. "GDC-0084" in Set A and "GDC0084" in Set B should cause a union.
    rep_to_names = {}
    for name in all_names:
        for rep in canonical_reprs(name):
            if rep not in rep_to_names:
                rep_to_names[rep] = []
            rep_to_names[rep].append(name)

    for _rep, names_list in rep_to_names.items():
        if len(names_list) > 1:
            first = names_list[0]
            for other in names_list[1:]:
                uf.union(first, other)

    # Group original names by their union-find root
    groups = {}
    for name in all_names:
        root = uf.find(name)
        if root not in groups:
            groups[root] = set()
        groups[root].add(name)

    return list(groups.values())
