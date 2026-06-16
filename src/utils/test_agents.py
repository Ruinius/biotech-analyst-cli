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
        if "Turn 1" in prompt:
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
        if "Turn 1" in prompt:
            return '[TOOL_CALL: web_search(query="Mock Drug safety")]'
        elif "Turn 2" in prompt:
            return '[TOOL_CALL: edit_landscape_table(safety="Mild nausea", efficacy="ORR 60%", milestones="Readout 2027", citations="ASCO 2026")]'
        else:
            return "Finished research. [FINALIZE]"
    elif "synthesis agent" in sys_lower:
        if "Turn 1" in prompt:
            return '[TOOL_CALL: web_search(query="Mock Drug market")]'
        else:
            return "## Executive Summary\nReconciled landscape shows positive trends. [FINALIZE]"
    elif "curation agent" in sys_lower or "curator" in sys_lower:
        return "- Learning item 1\n- Learning item 2"
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
                headers = "| Asset Name | Sponsor | MoA / Modality | Formulation | Lead Indication | Development Phase | Key Trials / Registry / Patent IDs | Selectivity & Safety Profile | Key Efficacy / Biomarker Data | Upcoming Milestones | Citations |"
                divider = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
                row = "| **Mock Drug** | Mock Sponsor | mAb | IV | Gastric | Phase 2 | NCT00000000 | safety | efficacy | milestones | citations |"
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

    from src.utils.generate_landscape_table import classify_interventions

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
    mock_query.assert_called_once()


@patch("src.services.llm_client.LLMClient.query")
def test_classify_interventions_llm_failure_raises(mock_query):
    """classify_interventions raises RuntimeError on LLM failure — no silent fallback."""
    from src.utils.generate_landscape_table import classify_interventions

    mock_query.return_value = "Error: Gemini API key not configured."

    with pytest.raises(RuntimeError, match="LLM intervention classification failed"):
        classify_interventions(
            names=["SHR-A1904", "Zolbetuximab"],
            target_name="Claudin-18.2",
        )


@patch("src.services.llm_client.LLMClient.query")
def test_classify_interventions_invalid_json_raises(mock_query):
    """classify_interventions raises RuntimeError if LLM returns non-JSON."""
    from src.utils.generate_landscape_table import classify_interventions

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

    from src.utils.generate_landscape_table import classify_interventions

    mock_query.return_value = _json.dumps(
        {"asset": ["SHR-A1904"], "background": ["Placebo"]}
    )

    classify_interventions(
        # 4 names but only 2 unique (case-insensitive)
        names=["SHR-A1904", "shr-a1904", "Placebo", "placebo"],
        target_name="Claudin-18.2",
    )

    # LLM should have been called with only 2 unique entries
    call_args = mock_query.call_args[0][0]  # prompt positional arg
    import json as _json2

    # Find the JSON array in the prompt
    import re as _re

    match = _re.search(r"\[.*?\]", call_args, _re.DOTALL)
    assert match, "No JSON array found in prompt"
    sent_names = _json2.loads(match.group())
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


if __name__ == "__main__":
    import subprocess
    import sys

    sys.exit(subprocess.run(["pytest", __file__, "-v"], check=False).returncode)
