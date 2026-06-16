import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure console handles Chinese characters and unicode correctly on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.agents.bdscan_agents.asset_research_agent import (
    AssetResearchAgent,
    clean_cell_to_name,
    extract_names_from_cell,
)
from src.agents.bdscan_agents.context_agent import generate_context
from src.agents.bdscan_agents.curator_agent import CuratorAgent
from src.agents.bdscan_agents.db_search_agent import DatabaseSearchAgent
from src.agents.bdscan_agents.synthesis_agent import SynthesisAgent
from src.core.config import Settings


@pytest.fixture
def settings():
    return Settings(
        full_name="Test Scout",
        email="scout@test.com",
        base_folder=tempfile.gettempdir(),
    )


@pytest.fixture
def target_dir():
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tdir = Path(tmp_dir_name) / "test_run"
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "research").mkdir(exist_ok=True)
        (tdir / "final_output").mkdir(exist_ok=True)
        yield tdir


@patch("src.services.llm_client.LLMClient.query")
def test_context_agent(mock_query, settings, target_dir):
    mock_query.return_value = (
        "## 1. Biology and Scientific Rationale\n"
        "Mock target biology details.\n\n"
        "## 2. Clinical Settings and Disease Areas\n"
        "Mock target clinical settings.\n\n"
        "## 3. Modality Considerations\n"
        "Mock target modalities."
    )

    context_path = generate_context(
        settings=settings,
        target_name="TestPathway",
        en_list=["Test1"],
        zh_list=["测试1"],
        modality="ADC",
        target_dir=target_dir,
    )

    assert context_path.exists()
    content = context_path.read_text(encoding="utf-8")
    assert "# Context Overview: TestPathway Sourcing" in content
    assert "Mock target biology details." in content


@patch("src.services.llm_client.LLMClient.query")
@patch("src.agents.bdscan_agents.db_search_agent.search_clinicaltrials")
def test_db_search_agent_loop(mock_search, mock_query, settings, target_dir):
    mock_search.return_value = "Success. Found 5 trials."
    # Turn 1 tool call, Turn 2 finalize
    mock_query.side_effect = [
        '[TOOL_CALL: search_clinicaltrials(term="TestPathway", limit=50)]',
        "Completed clinical trials research log content. [FINALIZE]",
    ]

    agent = DatabaseSearchAgent(settings, "testpathway", target_dir)
    agent.run_loop_for_source(
        idx=1,
        source_name="ClinicalTrials.gov",
        tool_name="search_clinicaltrials",
        synonyms=["TestPathway"],
        target_name="TestPathway",
        modality="ADC",
    )

    log_path = target_dir / "research" / "research_log_01_clinicaltrials.md"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "Completed clinical trials research log content." in content


def test_name_cleaner_and_extractor():
    cell_val = "**Zolbetuximab**<br>*(Vyloy / IMAB362 / IMAB-362)*"
    assert clean_cell_to_name(cell_val) == "Zolbetuximab"
    extracted = extract_names_from_cell(cell_val)
    assert "Zolbetuximab" in extracted
    assert "Vyloy" in extracted
    assert "IMAB362" in extracted
    assert "IMAB-362" in extracted


@patch("src.services.llm_client.LLMClient.query")
@patch("src.agents.bdscan_agents.asset_research_agent.web_search")
def test_asset_research_agent_loop(mock_web_search, mock_query, settings, target_dir):
    mock_web_search.return_value = (
        "Title: Study\nURL: http://test.com\nSnippet: Good results\n---"
    )
    # Turn 1 search, Turn 2 update table and finalize
    mock_query.side_effect = [
        '[TOOL_CALL: web_search(query="Zolbetuximab efficacy")]',
        '[TOOL_CALL: edit_landscape_table(safety="Mild nausea", efficacy="ORR 60%", milestones="Readout 2027", citations="ASCO 2026")]',
        "All completed [FINALIZE]",
    ]

    # Write dummy landscape table first
    table_path = target_dir / "research" / "landscape_table.md"
    headers = "| Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Selectivity & Safety Profile | Key Efficacy / Biomarker Data | Upcoming Milestones | Citations | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |"
    divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    row = "| **Zolbetuximab** | Astellas | mAb | IV | Gastric | Approved | NCT03504397 | safety placeholder | efficacy placeholder | milestones placeholder | citations placeholder | Web research pending. | Web research pending. | Web research pending. | N/A |"
    table_path.write_text(f"{headers}\n{divider}\n{row}\n", encoding="utf-8")

    agent = AssetResearchAgent(settings, target_dir)
    agent.research_all_assets()

    # Check updated table
    content = table_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert len(lines) == 3
    cols = [c.strip() for c in lines[2].split("|")]
    assert cols[12] == "Mild nausea"
    assert cols[13] == "ORR 60%"
    assert cols[14] == "Readout 2027"
    assert cols[15] == "ASCO 2026"


@patch("src.services.llm_client.LLMClient.query")
def test_synthesis_agent(mock_query, settings, target_dir):
    mock_query.return_value = (
        "## Executive Summary\n"
        "Reconciled landscape shows positive trends.\n\n"
        "## BD Takeaways\n"
        "Opportunity is high. [FINALIZE]"
    )

    table_path = target_dir / "research" / "landscape_table.md"
    table_path.write_text(
        "| Asset | Phase |\n| :--- | :--- |\n| TestDrug | Phase 1 |\n", encoding="utf-8"
    )

    agent = SynthesisAgent(settings, "testpathway", target_dir)
    report_file, table_file = agent.generate_synthesis("TestPathway")

    assert report_file.exists()
    assert table_file.exists()
    assert "Reconciled landscape shows positive trends." in report_file.read_text(
        encoding="utf-8"
    )
    assert "TestDrug" in table_file.read_text(encoding="utf-8")


@patch("src.services.llm_client.LLMClient.query")
def test_curator_agent(mock_query, settings, target_dir):
    # Setup log files
    db_log = target_dir / "research" / "research_log_01_clinicaltrials.md"
    db_log.write_text("Mock database search log content.", encoding="utf-8")

    web_log = target_dir / "research" / "web_research_log_testdrug.md"
    web_log.write_text("Mock web search log content.", encoding="utf-8")

    agent = CuratorAgent(settings)
    # Redirect learning filepath to temporary test directory
    test_learning_path = target_dir / "learning.md"
    agent.learning_filepath = test_learning_path

    # Define a mock response that returns more than 20 bullets to test programmatic limit
    mock_query.return_value = "\n".join([f"- Learning item {i}" for i in range(1, 26)])

    # Curate database search
    agent.curate_database_search(target_dir)

    # Verify content and limits
    assert test_learning_path.exists()
    content = test_learning_path.read_text(encoding="utf-8")
    assert "## database-search" in content

    # Extract the database-search section lines
    lines = content.splitlines()
    db_start = lines.index("## database-search")
    db_end = lines.index("## web-search") if "## web-search" in lines else len(lines)
    db_section_lines = [l for l in lines[db_start + 1 : db_end] if l.strip().startswith("-")]

    # Assert programmatic limit of 20 was enforced
    assert len(db_section_lines) == 20
    assert "- Learning item 1" in db_section_lines
    assert "- Learning item 20" in db_section_lines
    assert "- Learning item 21" not in db_section_lines

    # Curate web search
    mock_query.return_value = "- Web lesson A\n- Web lesson B"
    agent.curate_web_search(target_dir)

    content_updated = test_learning_path.read_text(encoding="utf-8")
    assert "## web-search" in content_updated
    assert "- Web lesson A" in content_updated
    assert "- Web lesson B" in content_updated

