"""
§4 — Pipeline Concurrency Tests

Verifies:
1. Thread pool completes with partial source failures (mock one source to raise).
2. Duplicate protection: same asset is not researched twice under different aliases.
3. _registry_lock prevents race condition under ThreadPoolExecutor(max_workers=4).
"""

import json
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is on path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.agents.bdscan_agents.asset_research_agent import (  # noqa: E402
    AssetResearchAgent,
)
from src.agents.bdscan_agents.db_search_agent import DatabaseSearchAgent  # noqa: E402
from src.core.config import Settings  # noqa: E402


@pytest.fixture
def settings():
    return Settings(
        full_name="Test Concurrency Analyst",
        email="concurrency@test.com",
        base_folder=tempfile.gettempdir(),
    )


@patch(
    "src.agents.bdscan_agents.db_search_agent.DatabaseSearchAgent.run_loop_for_source"
)
@patch(
    "src.agents.bdscan_agents.db_search_agent.DatabaseSearchAgent.deterministic_merge"
)
def test_db_search_concurrency_with_partial_failure(
    mock_merge, mock_run_loop, settings
):
    """
    Verify that the search pipeline continues if non-core sources fail,
    but fails if both core sources fail.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)
        db_agent = DatabaseSearchAgent(
            settings, "CLDN18_2_Scan", target_dir, sequential=False
        )

        # 1. Partial failure scenario: non-core source fails
        def mock_run(idx, source_name, tool_name, synonyms, target_name, modality):
            if source_name == "EU CTIS & Australian ANZCTR":
                raise RuntimeError("ANZCTR Scraper Timeout!")
            return

        mock_run_loop.side_effect = mock_run

        # This should complete successfully because ClinicalTrials.gov and NMPA CDE Direct Search did not fail
        db_agent.execute_search_pipeline("CLDN18.2", ["CLDN18.2"], ["CLDN18.2"])
        assert mock_merge.call_count == 1

        # 2. Critical failure scenario: both core sources fail
        mock_run_loop.reset_mock()
        mock_merge.reset_mock()

        def mock_run_core_fail(
            idx, source_name, tool_name, synonyms, target_name, modality
        ):
            if source_name in ("ClinicalTrials.gov", "NMPA CDE Direct Search"):
                raise RuntimeError("Core Database Unavailable!")
            return

        mock_run_loop.side_effect = mock_run_core_fail

        with pytest.raises(RuntimeError, match="Critical sources failed"):
            db_agent.execute_search_pipeline("CLDN18.2", ["CLDN18.2"], ["CLDN18.2"])


@patch(
    "src.agents.bdscan_agents.asset_research_agent.AssetResearchAgent.run_loop_for_asset"
)
def test_asset_research_duplicate_protection(mock_run_loop, settings):
    """
    Verify that duplicate assets (aliases) are skipped and linked to parent
    without running duplicate web research loops.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Setup folders
        research_dir = target_dir / "research"
        research_dir.mkdir(parents=True)
        db_json_dir = target_dir / "database_json"
        db_json_dir.mkdir()

        # Create dummy landscape_table.md
        table_path = research_dir / "landscape_table.md"
        table_content = (
            "| # | Asset Name | Developer | Modality | Phase | Trial IDs | Web Selectivity & Safety Profile | Web Key Efficacy Data | Web Upcoming Milestones | Web Citations / Sources |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| 1 | **Zolbetuximab** | Astellas | mAb | Phase 3 | NCT03504397 | N/A | N/A | N/A | N/A |\n"
            "| 2 | **IMAB362** | Ganymed | mAb | Phase 3 | NCT03504397 | N/A | N/A | N/A | N/A |\n"
        )
        table_path.write_text(table_content, encoding="utf-8")

        # Create asset_config.json containing aliases
        asset_config = {
            "Zolbetuximab": {
                "aliases": ["IMAB362", "Vyloy"],
                "modality": "Monoclonal Antibody",
                "targets": ["CLDN18.2"],
                "filtered_terms": [],
            }
        }
        (db_json_dir / "asset_config.json").write_text(
            json.dumps(asset_config), encoding="utf-8"
        )

        agent = AssetResearchAgent(settings, target_dir)

        def mock_research(table_p, asset_name, cols):
            # Write some dummy info so link_duplicate_asset can copy it
            content = table_p.read_text(encoding="utf-8")
            # Replace Zolbetuximab row with dummy values
            lines = content.splitlines()
            for idx, line in enumerate(lines):
                if "Zolbetuximab" in line:
                    cols = line.split("|")
                    cols[7] = " Zolbetuximab Safety "
                    cols[8] = " Zolbetuximab Efficacy "
                    cols[9] = " Zolbetuximab Milestones "
                    cols[10] = " Zolbetuximab Citations "
                    lines[idx] = "|".join(cols)
            table_p.write_text("\n".join(lines) + "\n", encoding="utf-8")

        mock_run_loop.side_effect = mock_research

        agent.research_all_assets()

        # Zolbetuximab and IMAB362 are aliases. Only ONE should be researched.
        # The other should be registered and linked.
        assert mock_run_loop.call_count == 1

        # Check table contents
        final_table = table_path.read_text(encoding="utf-8")
        assert "Zolbetuximab Safety" in final_table
        # The duplicate (IMAB362) should have copied parent values
        assert final_table.count("Zolbetuximab Safety") == 2


def test_asset_research_registry_lock_prevents_race(settings):
    """
    Verify that _registry_lock prevents concurrent race conditions where two threads
    try to register alias variations of the same asset.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)
        agent = AssetResearchAgent(settings, target_dir)

        # Simulate two concurrent threads discovering aliases
        errors = []

        def thread_1_work():
            try:
                # Thread 1 registers canonical Zolbetuximab
                agent.register_alias_mid_research("Zolbetuximab", "IMAB362")
            except Exception as e:
                errors.append(e)

        def thread_2_work():
            try:
                # Thread 2 concurrently registers same alias under Vyloy
                agent.register_alias_mid_research("Vyloy", "IMAB-362")
            except Exception as e:
                errors.append(e)

        # Pre-populate Vyloy and Zolbetuximab claims
        agent._claimed_assets["zolbetuximab"] = "Zolbetuximab"
        agent._claimed_assets["vyloy"] = "Vyloy"

        t1 = threading.Thread(target=thread_1_work)
        t2 = threading.Thread(target=thread_2_work)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
        # Check that the merge queue has captured the alias collision correctly
        # "IMAB362" and "IMAB-362" normalize to the same "imab362"
        # Thus, registering both should result in a collision
        assert len(agent._merge_queue) == 1
        collision = agent._merge_queue[0]
        assert "Zolbetuximab" in collision
        assert "Vyloy" in collision
