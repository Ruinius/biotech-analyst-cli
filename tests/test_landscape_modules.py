"""
§3 — Landscape Module Decomposition Tests

Verifies:
1. All submodules import without error
2. Key utility functions produce identical output to monolith reference values
3. md_table_to_text_table round-trip formatting
4. The re-export shim in generate_landscape_table.py works

All tests use local fixtures — no LLM or network calls.
"""

import sys
import tempfile
from pathlib import Path

# Ensure project root is on path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ---------------------------------------------------------------------------
# 1. Submodule import smoke tests
# ---------------------------------------------------------------------------


def test_import_table_formatters():
    from src.utils.landscape import table_formatters  # noqa: F401


def test_import_exporters():
    from src.utils.landscape import exporters  # noqa: F401


def test_import_config_builder():
    # config_builder imports classify_interventions from src.tools
    # We just want to verify the import chain resolves
    import importlib

    spec = importlib.util.find_spec("src.utils.landscape.config_builder")
    assert spec is not None


def test_import_table_builder():
    import importlib

    spec = importlib.util.find_spec("src.utils.landscape.table_builder")
    assert spec is not None


def test_import_reconciliation():
    from src.utils.landscape import reconciliation  # noqa: F401

    assert hasattr(reconciliation, "reconcile_all_sources")


def test_import_classify_interventions_agent():
    import importlib

    spec = importlib.util.find_spec(
        "src.agents.bdscan_agents.intervention_classifier_agent"
    )
    assert spec is not None


def test_shim_reexports():
    """The generate_landscape_table.py shim must re-export all key symbols."""
    import importlib

    shim = importlib.import_module("src.utils.generate_landscape_table")
    required_symbols = [
        "clean_sponsor",
        "matches_drug",
        "parse_ct_phase",
        "parse_text_phase",
        "detect_formulation",
        "parse_asset_and_aliases",
        "clean_cell_to_name",
        "normalize_drug_name",
        "_name_priority",
        "parse_existing_report",
        "discover_config",
        "merge_config_duplicates",
        "_strip_md",
        "md_table_to_text_table",
        "md_table_to_csv",
        "build_landscape_table",
        "classify_interventions",
        "CT_ACTIVE",
        "CT_COMPLETED",
        "CT_DISCONTINUED",
        "CDE_ACTIVE",
        "CDE_COMPLETED",
        "CDE_DISCONTINUED",
    ]
    for sym in required_symbols:
        assert hasattr(shim, sym), f"Shim missing symbol: {sym}"


# ---------------------------------------------------------------------------
# 2. Utility function correctness (fixture-based, no LLM)
# ---------------------------------------------------------------------------


def test_clean_sponsor_strips_suffixes():
    from src.utils.landscape.table_formatters import clean_sponsor

    assert clean_sponsor("AstraZeneca Pharmaceuticals") == "AstraZeneca"
    assert clean_sponsor("BioNTech SE") == "BioNTech SE"
    assert clean_sponsor("N/A") == ""
    assert clean_sponsor("") == ""
    assert clean_sponsor("Astellas Pharma") == "Astellas"


def test_parse_ct_phase_basic():
    from src.utils.landscape.table_formatters import parse_ct_phase

    assert parse_ct_phase(["PHASE3"]) == ("Phase 3", 3.0)
    assert parse_ct_phase(["PHASE1", "PHASE2"]) == ("Phase 1/2", 1.5)
    assert parse_ct_phase([]) == ("N/A", 0)
    assert parse_ct_phase(["PHASE4"]) == ("Phase 4", 4.0)


def test_parse_text_phase():
    from src.utils.landscape.table_formatters import parse_text_phase

    assert parse_text_phase("Phase 3 clinical trial")[0] == "Phase 3"
    assert parse_text_phase("iii期临床试验")[0] == "Phase 3"
    # Phase 2 text with i/ii combo → Phase 1/2
    assert parse_text_phase("Phase 2 i/ii dose escalation study")[0] == "Phase 1/2"
    # Plain "Phase 1/2 study" hits the Phase 1 branch first (preserved original behavior)
    assert parse_text_phase("Phase 1/2 study")[0] == "Phase 1"
    assert parse_text_phase("")[0] == "N/A"


def test_normalize_drug_name():
    from src.utils.landscape.table_formatters import normalize_drug_name

    assert normalize_drug_name("Zolbetuximab") == "zolbetuximab"
    assert normalize_drug_name("AMG-910") == "amg910"
    assert normalize_drug_name("SHR A1904") == "shra1904"
    assert normalize_drug_name("") == ""


def test_parse_asset_and_aliases_bold_primary():
    from src.utils.landscape.table_formatters import parse_asset_and_aliases

    cell = "**Zolbetuximab**<br>*( Vyloy / IMAB362 )*"
    primary, aliases = parse_asset_and_aliases(cell)
    assert primary == "Zolbetuximab"
    assert "Vyloy" in aliases
    assert "IMAB362" in aliases


def test_parse_asset_and_aliases_filters_modalities():
    from src.utils.landscape.table_formatters import parse_asset_and_aliases

    cell = "**TST001**<br>*( Chemotherapy / HER2 )*"
    primary, aliases = parse_asset_and_aliases(cell)
    assert primary == "TST001"
    # Chemotherapy and HER2 must be filtered out
    assert "Chemotherapy" not in aliases
    assert "HER2" not in aliases
    assert "chemotherapy" not in [a.lower() for a in aliases]
    assert "her2" not in [a.lower() for a in aliases]


def test_matches_drug():
    from src.utils.landscape.table_formatters import matches_drug

    assert matches_drug("Zolbetuximab phase 3 trial", ["Zolbetuximab", "Vyloy"])
    assert matches_drug("Vyloy approval", ["Zolbetuximab", "Vyloy"])
    assert not matches_drug("pembrolizumab study", ["Zolbetuximab", "Vyloy"])
    assert not matches_drug("", ["Zolbetuximab"])


def test_detect_formulation():
    from src.utils.landscape.table_formatters import detect_formulation

    forms = detect_formulation(
        ["IV infusion intravenous weekly", "subcutaneous injection"]
    )
    assert "Intravenous" in forms
    assert "Subcutaneous" in forms
    assert detect_formulation([]) == []


def test_name_priority_ordering():
    from src.utils.landscape.table_formatters import _name_priority

    # Alphanumeric code has highest priority (lowest sort value)
    code_key = _name_priority("AMG910")
    usan_key = _name_priority("zolbetuximab")
    other_key = _name_priority("SomeCompound")
    assert code_key[0] == 0
    assert usan_key[0] == 1
    assert other_key[0] == 2


# ---------------------------------------------------------------------------
# 3. Exporter correctness
# ---------------------------------------------------------------------------


SAMPLE_MD_TABLE = """\
| # | Asset Name | Sponsor | Phase |
| :--- | :--- | :--- | :--- |
| 1 | **Zolbetuximab** | Astellas | Phase 3 |
| 2 | **TST001** | Transcenta | Phase 2 |
"""


def test_md_table_to_text_table_returns_string():
    from src.utils.landscape.exporters import md_table_to_text_table

    result = md_table_to_text_table(SAMPLE_MD_TABLE)
    assert isinstance(result, str)
    assert "Zolbetuximab" in result
    assert "TST001" in result


def test_md_table_to_text_table_alignment():
    from src.utils.landscape.exporters import md_table_to_text_table

    result = md_table_to_text_table(SAMPLE_MD_TABLE)
    lines = [l for l in result.splitlines() if l.strip().startswith("|")]
    # All data lines should have the same number of pipe delimiters
    pipe_counts = [l.count("|") for l in lines if "---" not in l]
    assert len(set(pipe_counts)) == 1, f"Misaligned columns: {pipe_counts}"


def test_md_table_to_csv_round_trip():
    from src.utils.landscape.exporters import md_table_to_csv

    result = md_table_to_csv(SAMPLE_MD_TABLE)
    assert "Zolbetuximab" in result
    assert "TST001" in result
    # Should be CSV — no pipe characters
    assert "|" not in result


def test_strip_md_removes_formatting():
    from src.utils.landscape.exporters import _strip_md

    assert _strip_md("**bold**") == "bold"
    assert _strip_md("[link](http://example.com)") == "link"
    assert _strip_md("text<br/>more") == "text / more"


# ---------------------------------------------------------------------------
# 4. build_landscape_table integration test (no LLM — uses pre-built config)
# ---------------------------------------------------------------------------


FIXTURE_CT_DATA = {
    "NCT03504397": {
        "protocolSection": {
            "identificationModule": {
                "briefTitle": "SPOTLIGHT: Zolbetuximab plus mFOLFOX6",
                "officialTitle": "SPOTLIGHT Study of Zolbetuximab",
                "nctId": "NCT03504397",
            },
            "statusModule": {"overallStatus": "COMPLETED"},
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Astellas Pharma Inc."}
            },
            "designModule": {"phases": ["PHASE3"]},
            "armsInterventionsModule": {
                "interventions": [
                    {
                        "type": "BIOLOGICAL",
                        "name": "Zolbetuximab",
                        "otherNames": ["IMAB362"],
                    }
                ]
            },
            "descriptionModule": {"briefSummary": "", "detailedDescription": ""},
        }
    }
}

FIXTURE_CHINA_DATA = []

FIXTURE_CONFIG = {"Zolbetuximab": {"aliases": ["IMAB362", "Vyloy"]}}

FIXTURE_EXISTING_META = {}


def test_build_landscape_table_creates_file():
    from src.utils.landscape.table_builder import build_landscape_table

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "landscape_table.md"
        build_landscape_table(
            FIXTURE_CT_DATA,
            FIXTURE_CHINA_DATA,
            FIXTURE_CONFIG,
            FIXTURE_EXISTING_META,
            output_path,
        )
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "Zolbetuximab" in content
        assert "NCT03504397" in content
        assert "Astellas" in content
        assert "Phase 3" in content


def test_build_landscape_table_includes_aliases():
    from src.utils.landscape.table_builder import build_landscape_table

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "landscape_table.md"
        build_landscape_table(
            FIXTURE_CT_DATA,
            FIXTURE_CHINA_DATA,
            FIXTURE_CONFIG,
            FIXTURE_EXISTING_META,
            output_path,
        )
        content = output_path.read_text(encoding="utf-8")
        # Aliases should be present in the name cell
        assert "IMAB362" in content or "Vyloy" in content


def test_build_landscape_table_row_count():
    from src.utils.landscape.table_builder import build_landscape_table

    config_two = {
        "Zolbetuximab": {"aliases": ["IMAB362"]},
        "TST001": {"aliases": []},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "landscape_table.md"
        build_landscape_table(
            FIXTURE_CT_DATA, FIXTURE_CHINA_DATA, config_two, {}, output_path
        )
        content = output_path.read_text(encoding="utf-8")
        lines = [l for l in content.splitlines() if l.strip().startswith("|")]
        # header + divider + 2 data rows = 4 lines
        data_rows = [l for l in lines if "---" not in l and "Asset Name" not in l]
        assert len(data_rows) == 2
