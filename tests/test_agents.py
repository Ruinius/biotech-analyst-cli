import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.bdscan_orchestrator import run_bdscan_pipeline
from src.core.deepdive_orchestrator import run_deepdive_pipeline

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
from src.agents.bdscan_agents.intervention_classifier_agent import (
    classify_interventions,
)
from src.agents.bdscan_agents.synthesis_agent import SynthesisAgent
from src.core.config import Settings
from src.core.exceptions import PipelineError


@pytest.fixture(autouse=True)
def mock_config_env(tmp_path):
    temp_file = tmp_path / ".env"
    with patch("src.core.config.CONFIG_FILE_PATH", temp_file):
        yield temp_file


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
@pytest.mark.parametrize(
    "llm_output",
    [
        None,
        "",
        "Error: API key is invalid",
        "Failed to call OpenRouter API after retries",
    ],
)
def test_context_agent_failure(mock_query, settings, target_dir, llm_output):
    mock_query.return_value = llm_output

    with pytest.raises(PipelineError) as exc_info:
        generate_context(
            settings=settings,
            target_name="TestPathway",
            en_list=["Test1"],
            zh_list=["测试1"],
            modality="ADC",
            target_dir=target_dir,
        )

    assert "LLM context generation failed or returned error" in str(exc_info.value)


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


def test_db_search_agent_learnings(settings, target_dir):
    # Setup a mock learning.md
    learning_path = target_dir / "learning.md"
    learning_path.write_text(
        "# Pipeline Learnings\n\n"
        "## database-search\n"
        "- Learnings item A\n"
        "- Learnings item B\n\n"
        "## web-search\n"
        "- Web item 1\n",
        encoding="utf-8",
    )

    agent = DatabaseSearchAgent(settings, "testpathway", target_dir)
    agent.learning_filepath = learning_path

    # Verify _load_learnings loads correct section
    db_learnings = agent._load_learnings("database-search")
    assert "- Learnings item A" in db_learnings
    assert "- Learnings item B" in db_learnings
    assert "- Web item 1" not in db_learnings

    # Mock the LLM client query to verify that the query was called with the correct learnings in the system instruction
    with (
        patch("src.services.llm_client.LLMClient.query") as mock_query,
        patch(
            "src.agents.bdscan_agents.db_search_agent.search_clinicaltrials"
        ) as mock_search,
    ):
        mock_search.return_value = "Success"
        mock_query.return_value = "Mock result. [FINALIZE]"

        agent.run_loop_for_source(
            idx=1,
            source_name="ClinicalTrials.gov",
            tool_name="search_clinicaltrials",
            synonyms=["TestPathway"],
            target_name="TestPathway",
            modality="ADC",
        )

        assert mock_query.call_count == 1
        args, kwargs = mock_query.call_args
        system_instruction = kwargs.get("system_instruction")
        if not system_instruction and len(args) > 1:
            system_instruction = args[1]
        assert "Learnings item A" in system_instruction
        assert "Learnings item B" in system_instruction


def test_asset_research_agent_learnings(settings, target_dir):
    learning_path = target_dir / "learning.md"
    learning_path.write_text(
        "# Pipeline Learnings\n\n"
        "## database-search\n"
        "- Learnings item A\n"
        "- Learnings item B\n\n"
        "## web-search\n"
        "- Web item 1\n"
        "- Web item 2\n",
        encoding="utf-8",
    )

    agent = AssetResearchAgent(settings, target_dir)
    agent.learning_filepath = learning_path

    # Verify _load_learnings loads correct section
    web_learnings = agent._load_learnings("web-search")
    assert "- Web item 1" in web_learnings
    assert "- Web item 2" in web_learnings
    assert "- Learnings item A" not in web_learnings

    # Mock the LLM client query to verify that the query was called with the correct learnings in the system instruction
    with (
        patch("src.services.llm_client.LLMClient.query") as mock_query,
        patch(
            "src.agents.bdscan_agents.asset_research_agent.web_search"
        ) as mock_web_search,
    ):
        mock_web_search.return_value = "Success"
        mock_query.return_value = "Mock result. [FINALIZE]"

        # Write dummy landscape table first
        table_path = target_dir / "research" / "landscape_table.md"
        headers = "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |"
        divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        row = "| 1 | **Zolbetuximab** | Astellas | mAb | IV | Gastric | Approved | NCT03504397 | Web research pending. | Web research pending. | Web research pending. | N/A |"
        table_path.write_text(f"{headers}\n{divider}\n{row}\n", encoding="utf-8")

        agent.research_all_assets()

        # The query should contain the learnings in the system instruction
        assert mock_query.call_count > 0
        # Check first query call
        args, kwargs = mock_query.call_args_list[0]
        system_instruction = kwargs.get("system_instruction")
        if not system_instruction and len(args) > 1:
            system_instruction = args[1]
        assert "Web item 1" in system_instruction
        assert "Web item 2" in system_instruction


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
    headers = "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |"
    divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    row = "| 1 | **Zolbetuximab** | Astellas | mAb | IV | Gastric | Approved | NCT03504397 | Web research pending. | Web research pending. | Web research pending. | N/A |"
    table_path.write_text(f"{headers}\n{divider}\n{row}\n", encoding="utf-8")

    agent = AssetResearchAgent(settings, target_dir)
    agent.research_all_assets()

    # Check updated table
    content = table_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert len(lines) == 3
    cols = [c.strip() for c in lines[2].split("|")]
    assert cols[9] == "Mild nausea"
    assert cols[10] == "ORR 60%"
    assert cols[11] == "Readout 2027"
    assert cols[12] == "ASCO 2026"


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
    db_section_lines = [
        l for l in lines[db_start + 1 : db_end] if l.strip().startswith("-")
    ]

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


def mock_query_fn(prompt, system_instruction=None):
    if not system_instruction:
        return "## 1. Biology and Scientific Rationale\nMock biology.\n\n## 2. Clinical Settings and Disease Areas\nMock clinical.\n\n## 3. Modality Considerations\nMock modality."

    sys_lower = system_instruction.lower()
    # Use prompt without history to avoid checking old turns
    current_prompt = prompt.split("History:")[0]

    if "context" in sys_lower or "molecular biologist" in sys_lower:
        return (
            "## 1. Biology and Scientific Rationale\n"
            "Mock biology.\n\n"
            "## 2. Clinical Settings and Disease Areas\n"
            "Mock clinical.\n\n"
            "## 3. Modality Considerations\n"
            "Mock modality."
        )
    elif "database search agent" in sys_lower:
        if "Turn 1" in current_prompt:
            tool_name = "search_clinicaltrials"
            for t in [
                "search_clinicaltrials",
                "search_anzctr_ctis",
                "search_conferences",
                "search_chinese_registries",
                "search_china_direct",
                "search_ip_lens",
                "search_pubchem",
                "search_openfda",
            ]:
                if t in system_instruction:
                    tool_name = t
                    break
            return f'[TOOL_CALL: {tool_name}(term="TestPathway")]'
        else:
            return "Mock database search results summary. [FINALIZE]"
    elif "asset research agent" in sys_lower:
        if "Turn 1" in current_prompt:
            return '[TOOL_CALL: web_search(query="Mock Drug safety")]'
        elif "Turn 2" in current_prompt:
            return '[TOOL_CALL: edit_landscape_table(safety="Mild nausea", efficacy="ORR 60%", milestones="Readout 2027", citations="ASCO 2026")]'
        else:
            return "Finished research. [FINALIZE]"
    elif "synthesis agent" in sys_lower:
        if "Turn 1" in current_prompt:
            return '[TOOL_CALL: web_search(query="Mock Drug market")]'
        else:
            return "## Executive Summary\nReconciled landscape shows positive trends. [FINALIZE]"
    elif "curation agent" in sys_lower or "curator" in sys_lower:
        return "- Learning item 1\n- Learning item 2"
    elif "classification" in sys_lower or "expert" in sys_lower:
        return json.dumps({"asset": ["Mock Drug"], "background": ["Placebo"]})
    return "Mock LLM Response"


@patch("src.services.llm_client.LLMClient.query", side_effect=mock_query_fn)
@patch("subprocess.run")
def test_bdscan_pipeline_integration(mock_run, mock_query, settings, target_dir):
    # Setup mock CuratorAgent learning path
    test_learning_path = target_dir / "learning.md"
    original_init = CuratorAgent.__init__

    def mock_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.learning_filepath = test_learning_path

    # Setup mock subprocess runs
    def global_run_side_effect(cmd, *args, **kwargs):
        cmd_str = str(cmd[1]) if len(cmd) > 1 else ""
        if "fetch_" in cmd_str or "summarize_" in cmd_str:
            output_idx = cmd.index("--output") if "--output" in cmd else -1
            if output_idx != -1:
                out_path = str(cmd[output_idx + 1])
                if out_path.endswith(".json"):
                    if "ct_" in out_path or "clinicaltrials" in out_path:
                        with open(out_path, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "NCT00000000": {
                                        "protocolSection": {
                                            "identificationModule": {
                                                "nctId": "NCT00000000",
                                                "briefTitle": "Mock Trial",
                                            },
                                            "statusModule": {
                                                "overallStatus": "RECRUITING"
                                            },
                                            "sponsorCollaboratorsModule": {
                                                "leadSponsor": {"name": "Mock Sponsor"}
                                            },
                                            "designModule": {"phases": ["PHASE2"]},
                                            "armsInterventionsModule": {
                                                "interventions": [{"name": "Mock Drug"}]
                                            },
                                        }
                                    }
                                },
                                f,
                            )
                    elif "cdirect_" in out_path or "china_direct" in out_path:
                        with open(out_path, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "records": [
                                        {
                                            "acceptance_number": "CTR20200000",
                                            "drug_name": "Mock Drug",
                                            "company": "Mock Sponsor",
                                            "status": "进行中",
                                        }
                                    ]
                                },
                                f,
                            )
                    else:
                        with open(out_path, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "results": [
                                        {"title": "Mock Title", "id": "ChiCTR2000"}
                                    ]
                                },
                                f,
                            )
                elif out_path.endswith(".txt"):
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(
                            "CLINICAL TRIALS SUMMARY REPORT\nSponsor: Mock Sponsor\nEligibility Criteria:"
                        )
        elif "generate_landscape_table.py" in cmd_str:
            output_idx = cmd.index("--output") if "--output" in cmd else -1
            if output_idx != -1:
                out_path = str(cmd[output_idx + 1])
                headers = "| Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs |"
                divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
                row = "| **Mock Drug** | Mock Sponsor | mAb | IV | Gastric | Phase 2 | NCT00000000 |"
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"{headers}\n{divider}\n{row}\n")
        elif "convert_md_to_pdf.py" in cmd_str:
            pdf_path = str(cmd[-1])
            with open(pdf_path, "w", encoding="utf-8") as f:
                f.write("%PDF-1.4 mock pdf")

        class MockCompletedProcess:
            returncode = 0
            stdout = "Mock Success"
            stderr = ""

        return MockCompletedProcess()

    mock_run.side_effect = global_run_side_effect

    with patch.object(CuratorAgent, "__init__", mock_init):
        # Run the pipeline
        pdf_out = run_bdscan_pipeline(
            settings=settings,
            action="new",
            target_name="TestPathway",
            folder_safe_name="testpathway",
            target_dir=target_dir,
            en_list=["TestPathway"],
            zh_list=["TestPathway"],
            modality="ADC",
        )

        assert pdf_out.exists()
        assert (target_dir / "research" / "landscape_table.md").exists()
        assert (target_dir / "context.md").exists()
        assert test_learning_path.exists()


@patch("src.core.deepdive_orchestrator.subprocess.run")
def test_deepdive_pipeline_integration(mock_deep_run, settings, target_dir):
    def deep_run_side_effect(cmd, *args, **kwargs):
        output_idx = cmd.index("--output") if "--output" in cmd else -1
        if output_idx != -1:
            out_path = str(cmd[output_idx + 1])
            if out_path.endswith(".json"):
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump({"dummy": "data"}, f)
            elif out_path.endswith(".txt") or out_path.endswith(".md"):
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(
                        "CLINICAL TRIALS SUMMARY REPORT\nSponsor: Mock Sponsor\nEligibility Criteria:"
                    )

        if len(cmd) > 2 and str(cmd[-1]).endswith(".pdf"):
            with open(cmd[-1], "w", encoding="utf-8") as f:
                f.write("%PDF-1.4 mock deepdive pdf")

        class MockCompletedProcess:
            returncode = 0
            stdout = "Mock Success"
            stderr = ""

        return MockCompletedProcess()

    mock_deep_run.side_effect = deep_run_side_effect

    pdf_out = run_deepdive_pipeline(
        settings=settings,
        action="new",
        asset_name="Osemitamab",
        folder_safe_name="osemitamab",
        target_dir=target_dir,
        developer="Transcenta",
        trial_id="NCT04818671",
    )

    assert pdf_out.exists()
    assert (target_dir / "context.md").exists()
    assert (target_dir / "research" / "osemitamab_ct.md").exists()


# ---------------------------------------------------------------------------
# Unit tests for the new LLM-based intervention classifier
# ---------------------------------------------------------------------------


@patch("src.services.llm_client.LLMClient.query")
def test_classify_interventions_happy_path(mock_query):
    """classify_interventions correctly parses a valid LLM JSON response."""
    import json as _json

    mock_query.return_value = _json.dumps(
        {
            "asset": ["SHR-A1904", "Zolbetuximab"],
            "background": ["pembrolizumab", "FOLFOX", "Placebo"],
        }
    )

    result = classify_interventions(
        names=["SHR-A1904", "Zolbetuximab", "pembrolizumab", "FOLFOX", "Placebo"],
        target_name="Claudin-18.2",
        target_synonyms=["CLDN18.2", "Claudin 18.2"],
    )

    assert "SHR-A1904" in result
    assert "Zolbetuximab" in result
    assert "pembrolizumab" not in result
    assert "FOLFOX" not in result
    assert "Placebo" not in result
    assert mock_query.call_count == 3


@patch("src.services.llm_client.LLMClient.query")
def test_classify_interventions_llm_failure_raises(mock_query):
    """classify_interventions raises RuntimeError on LLM failure — no silent fallback."""

    mock_query.return_value = "Error: Gemini API key not configured."

    with pytest.raises(RuntimeError, match="LLM intervention classification failed"):
        classify_interventions(
            names=["SHR-A1904", "Zolbetuximab"],
            target_name="Claudin-18.2",
        )


@patch("src.services.llm_client.LLMClient.query")
def test_classify_interventions_invalid_json_raises(mock_query):
    """classify_interventions raises RuntimeError if LLM returns non-JSON."""

    mock_query.return_value = "Sure, here are the assets: SHR-A1904, Zolbetuximab."

    with pytest.raises(RuntimeError, match="unparseable JSON"):
        classify_interventions(
            names=["SHR-A1904", "Zolbetuximab"],
            target_name="Claudin-18.2",
        )


@patch("src.services.llm_client.LLMClient.query")
def test_classify_interventions_deduplicates_input(mock_query):
    """classify_interventions deduplicates names before calling the LLM."""
    import json as _json

    mock_query.return_value = _json.dumps(
        {"asset": ["SHR-A1904"], "background": ["Placebo"]}
    )

    classify_interventions(
        # 4 names but only 2 unique (case-insensitive)
        names=["SHR-A1904", "shr-a1904", "Placebo", "placebo"],
        target_name="Claudin-18.2",
    )

    # LLM should have been called with only 2 unique entries in the first call (primary classification)
    first_call_args = mock_query.call_args_list[0][0][
        0
    ]  # First call positional arg (prompt)
    import json as _json2

    # Find the JSON array in the prompt after 'Input names:'
    import re as _re

    match = _re.search(r"Input names:\s*(\[.*?\])", first_call_args, _re.DOTALL)
    assert match, "No JSON array found in prompt"
    sent_names = _json2.loads(match.group(1))
    assert len(sent_names) == 2


@patch("src.services.llm_client.LLMClient.query")
def test_discover_config_uses_classifier(mock_query):
    """discover_config returns only LLM-classified assets in the config dict."""
    import json as _json

    from src.utils.generate_landscape_table import discover_config

    mock_query.return_value = _json.dumps(
        {
            "asset": ["SHR-A1904"],
            "background": ["pembrolizumab", "FOLFOX"],
        }
    )

    ct_data = {
        "NCT00000001": {
            "protocolSection": {
                "armsInterventionsModule": {
                    "interventions": [
                        {"type": "DRUG", "name": "SHR-A1904", "otherNames": []},
                        {"type": "DRUG", "name": "pembrolizumab", "otherNames": []},
                        {"type": "DRUG", "name": "FOLFOX", "otherNames": []},
                    ]
                }
            }
        }
    }

    config = discover_config(
        ct_data=ct_data,
        china_data=[],
        target_name="Claudin-18.2",
        target_synonyms=["CLDN18.2"],
    )

    # Only the classified asset should appear in the config
    all_names = set(config.keys())
    for details in config.values():
        all_names.update(details.get("aliases", []))

    assert any("SHR-A1904" in n or "shr-a1904" in n.lower() for n in all_names)
    assert not any("pembrolizumab" in n.lower() for n in all_names)
    assert not any("folfox" in n.lower() for n in all_names)


def test_normalize_drug_name():
    from src.utils.generate_landscape_table import normalize_drug_name

    assert normalize_drug_name("SHR-A1904") == "shra1904"
    assert normalize_drug_name("AMG 910") == "amg910"
    assert normalize_drug_name("Zolbetuximab") == "zolbetuximab"
    assert normalize_drug_name("IMAB-362/IMAB362") == "imab362imab362"
    assert normalize_drug_name(None) == ""
    assert normalize_drug_name("") == ""


def test_merge_config_duplicates():
    from src.utils.generate_landscape_table import merge_config_duplicates

    config = {
        "AMG 910": {"aliases": []},
        "AMG910": {"aliases": []},
        "Zolbetuximab": {"aliases": ["IMAB362"]},
        "Vyloy": {"aliases": ["IMAB-362"]},
    }

    existing_meta = {
        "AMG 910": {"safety": "Safe", "efficacy": "Efficacious"},
        "AMG910": {"safety": "N/A", "milestones": "Phase 1 completion"},
        "Zolbetuximab": {"indication": "Gastric Cancer", "safety": "N/A"},
        "Vyloy": {"safety": "Mild toxicity", "milestones": "N/A"},
    }

    new_config, new_meta = merge_config_duplicates(config, existing_meta)

    # Check that AMG 910 and AMG910 were merged.
    amg_keys = [k for k in new_config if "amg" in k.lower()]
    assert len(amg_keys) == 1
    primary_amg = amg_keys[0]
    assert (
        "AMG910" in new_config[primary_amg]["aliases"]
        or "AMG 910" in new_config[primary_amg]["aliases"]
    )

    # Check that Zolbetuximab/Vyloy were merged (since IMAB-362 and IMAB362 normalize to same)
    zolb_keys = [
        k
        for k in new_config
        if "zolbetuximab" in k.lower() or "vyloy" in k.lower() or "imab" in k.lower()
    ]
    assert len(zolb_keys) == 1
    primary_zolb = zolb_keys[0]

    # Check meta merging
    amg_meta = new_meta[primary_amg]
    assert amg_meta["safety"] == "Safe"
    assert amg_meta["efficacy"] == "Efficacious"
    assert amg_meta["milestones"] == "Phase 1 completion"

    zolb_meta = new_meta[primary_zolb]
    assert zolb_meta["indication"] == "Gastric Cancer"
    assert zolb_meta["safety"] == "Mild toxicity"


def test_parse_asset_and_aliases():
    from src.utils.generate_landscape_table import parse_asset_and_aliases

    primary, aliases = parse_asset_and_aliases(
        "**Zolbetuximab**<br>*(Vyloy / IMAB362 / IMAB-362)*"
    )
    assert primary == "Zolbetuximab"
    assert set(aliases) == {"Vyloy", "IMAB362", "IMAB-362"}

    primary, aliases = parse_asset_and_aliases(
        "**Zolbetuximab**<br>*(with Chemotherapy)*"
    )
    assert primary == "Zolbetuximab"
    assert aliases == []

    primary, aliases = parse_asset_and_aliases(
        "**Zolbetuximab**<br>*(Vyloy / immunotherapy / HER2)*"
    )
    assert primary == "Zolbetuximab"
    assert aliases == ["Vyloy"]


def test_parse_existing_report_dynamic_columns(tmp_path):
    from src.utils.generate_landscape_table import parse_existing_report

    # Test table with leading # column
    table_with_hash = (
        "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| 1 | **Zolbetuximab**<br>*(Vyloy / IMAB362)* | Astellas | mAb | IV | Gastric | Approved | NCT03504397 | safety_val | efficacy_val | milestone_val | citation_val |\n"
    )
    report_file = tmp_path / "report_hash.md"
    report_file.write_text(table_with_hash, encoding="utf-8")

    config = {"Zolbetuximab": {"aliases": ["Vyloy", "IMAB362"]}}
    metadata = parse_existing_report(str(report_file), config)

    assert "Zolbetuximab" in metadata
    assert metadata["Zolbetuximab"]["safety"] == "safety_val"
    assert metadata["Zolbetuximab"]["efficacy"] == "efficacy_val"
    assert metadata["Zolbetuximab"]["milestones"] == "milestone_val"
    assert metadata["Zolbetuximab"]["citations"] == "citation_val"

    # Test table without leading # column
    table_no_hash = (
        "| Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| **Zolbetuximab**<br>*(Vyloy / IMAB362)* | Astellas | mAb | IV | Gastric | Approved | NCT03504397 | safety_val2 | efficacy_val2 | milestone_val2 | citation_val2 |\n"
    )
    report_file_no_hash = tmp_path / "report_no_hash.md"
    report_file_no_hash.write_text(table_no_hash, encoding="utf-8")

    metadata2 = parse_existing_report(str(report_file_no_hash), config)
    assert "Zolbetuximab" in metadata2
    assert metadata2["Zolbetuximab"]["safety"] == "safety_val2"
    assert metadata2["Zolbetuximab"]["efficacy"] == "efficacy_val2"


def test_parse_report_table_dynamic_columns(tmp_path):
    from src.utils.validate_report import parse_report_table

    # Test table with leading # column
    table_with_hash = (
        "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| 1 | **Zolbetuximab** | Astellas | mAb | IV | Gastric | Approved | NCT03504397 | safety_val | efficacy_val | milestone_val | citation_val |\n"
    )
    report_file = tmp_path / "report_hash.md"
    report_file.write_text(table_with_hash, encoding="utf-8")

    rows = parse_report_table(str(report_file))
    assert len(rows) == 1
    assert rows[0]["cleaned_name"] == "Zolbetuximab"
    assert rows[0]["trials_cell"] == "NCT03504397"
    assert rows[0]["lead_phase"] == "Approved"
    assert rows[0]["sponsor"] == "Astellas"


def test_db_search_agent_run_cmd_unicode():
    from src.agents.bdscan_agents.db_search_agent import run_cmd

    # Run a python command that outputs Chinese text to stdout
    success, stdout, stderr = run_cmd(["-c", "print('测试中文')"])
    assert success
    assert "测试中文" in stdout


def test_discover_config_reuses_reconciled_json(tmp_path):
    from src.utils.generate_landscape_table import discover_config

    # Create a dummy reconciled.json
    db_json_dir = tmp_path / "database_json"
    db_json_dir.mkdir()
    reconciled_file = db_json_dir / "reconciled.json"
    reconciled_data = {
        "Zolbetuximab": {
            "canonical_name": "Zolbetuximab",
            "aliases": ["Vyloy", "IMAB362"],
            "modality": "Monoclonal Antibody",
        }
    }
    with open(reconciled_file, "w", encoding="utf-8") as f:
        json.dump(reconciled_data, f)

    # Call discover_config and assert it maps from reconciled.json directly
    config = discover_config(
        ct_data={},
        china_data=[],
        target_name="CLDN18.2",
        database_json_dir=str(db_json_dir),
    )

    assert "Zolbetuximab" in config
    assert config["Zolbetuximab"]["aliases"] == ["Vyloy", "IMAB362"]
    # Check that asset_config.json was also written
    config_file = db_json_dir / "asset_config.json"
    assert config_file.exists()


@patch("src.services.llm_client.LLMClient.query")
@patch("src.agents.bdscan_agents.db_search_agent.search_clinicaltrials")
def test_db_search_agent_final_turn_break(
    mock_search, mock_query, settings, target_dir
):
    mock_query.side_effect = [
        '[TOOL_CALL: search_clinicaltrials(term="TestPathway", limit=50)]',
        '[TOOL_CALL: search_clinicaltrials(term="TestPathway", limit=50)]',
        '[TOOL_CALL: search_clinicaltrials(term="TestPathway", limit=50)]',
        '[TOOL_CALL: search_clinicaltrials(term="TestPathway", limit=50)]',
    ]
    mock_search.return_value = "Success"

    agent = DatabaseSearchAgent(settings, "testpathway", target_dir)
    agent.run_loop_for_source(
        idx=1,
        source_name="ClinicalTrials.gov",
        tool_name="search_clinicaltrials",
        synonyms=["TestPathway"],
        target_name="TestPathway",
        modality="ADC",
    )

    # Since it was the final turn, mock_search should only be called 3 times (Turns 1, 2, 3)
    # On Turn 4 (final turn), it breaks early and doesn't call search_clinicaltrials
    assert mock_search.call_count == 3
    # And the log file should exist
    log_path = target_dir / "research" / "research_log_01_clinicaltrials.md"
    assert log_path.exists()


@patch("src.services.llm_client.LLMClient.query")
@patch("src.agents.bdscan_agents.asset_research_agent.web_search")
def test_asset_research_agent_fallback(
    mock_web_search, mock_query, settings, target_dir
):
    mock_web_search.return_value = "Success"
    # LLM never calls edit_landscape_table, only web_search
    # Mock fallback query response as JSON string
    mock_query.side_effect = [
        '[TOOL_CALL: web_search(query="Zolbetuximab efficacy")]',
        '[TOOL_CALL: web_search(query="Zolbetuximab safety")]',
        '[TOOL_CALL: web_search(query="Zolbetuximab milestones")]',
        '[TOOL_CALL: web_search(query="Zolbetuximab citations")]',
        # Fallback query response
        '{"safety": "Mild toxicity", "efficacy": "PR 45%", "milestones": "Phase 3 readout", "citations": "PubMed 123"}',
    ]

    # Write dummy landscape table first
    table_path = target_dir / "research" / "landscape_table.md"
    headers = "| # | Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |"
    divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    row = "| 1 | **Zolbetuximab** | Astellas | mAb | IV | Gastric | Approved | NCT03504397 | Web research pending. | Web research pending. | Web research pending. | N/A |"
    table_path.write_text(f"{headers}\n{divider}\n{row}\n", encoding="utf-8")

    agent = AssetResearchAgent(settings, target_dir)
    agent.research_all_assets()

    # The table should be updated via fallback
    content = table_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    cols = [c.strip() for c in lines[2].split("|")]
    assert cols[9] == "Mild toxicity"
    assert cols[10] == "PR 45%"
    assert cols[11] == "Phase 3 readout"
    assert cols[12] == "PubMed 123"


@patch("src.services.llm_client.LLMClient.query")
def test_synthesis_agent_final_turn_break_and_extraction(
    mock_query, settings, target_dir
):
    # LLM returns web_search for first 9 turns, then on Turn 10 (final turn) returns a report + [FINALIZE]
    mock_query.side_effect = [
        '[TOOL_CALL: web_search(query="Zolbetuximab efficacy")]'
    ] * 9 + ["My strategic report. [FINALIZE]"]

    table_path = target_dir / "research" / "landscape_table.md"
    table_path.write_text(
        "| Asset | Phase |\n| :--- | :--- |\n| TestDrug | Phase 1 |\n", encoding="utf-8"
    )

    agent = SynthesisAgent(settings, "testpathway", target_dir)
    report_file, table_file = agent.generate_synthesis("TestPathway")

    assert report_file.exists()
    assert table_file.exists()
    report_content = report_file.read_text(encoding="utf-8")
    assert "My strategic report." in report_content
    assert "[FINALIZE]" not in report_content
    assert "TOOL_CALL" not in report_content


if __name__ == "__main__":
    import subprocess
    import sys

    sys.exit(subprocess.run(["pytest", __file__, "-v"], check=False).returncode)
