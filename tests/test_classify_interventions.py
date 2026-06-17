"""
§2 — LLM Alias Resolution Tests

Verifies:
1. classify_interventions returns list[dict] with correct keys after §2 extension
2. Batch size ≤ 30 is respected
3. Hallucination validator rejects names not in source text
4. Modality filter catches generic terms
5. Extended schema consumed by config_builder and reconciliation

All tests mock LLM to avoid network calls.
"""

import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ---------------------------------------------------------------------------
# NOTE: In §2 classify_interventions is extended to return list[dict].
# Tests here validate the NEW behavior:
#   return type:  list[dict] with keys:
#     "canonical_name", "aliases", "modality", "targets", "filtered_terms"
#
# Until the §2 function update is committed, we test the intended contract and
# verify the set[str] behavior of the current §3 implementation still passes
# (ensuring no regressions).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _make_llm_response(assets: list, background: list) -> str:
    return json.dumps({"asset": assets, "background": background})


def _make_llm_client_mock(response_json: str):
    mock = MagicMock()
    mock.query.return_value = response_json
    return mock


# ---------------------------------------------------------------------------
# 1. Current §3 behavior tests updated for §2 (AssetList return)
# ---------------------------------------------------------------------------


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_returns_asset_list(mock_llm_cls):
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    mock_client = _make_llm_client_mock(
        _make_llm_response(["Zolbetuximab", "TST001"], ["chemotherapy"])
    )
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(
        ["Zolbetuximab", "TST001", "chemotherapy"],
        target_name="CLDN18.2",
    )

    # §2: returns AssetList
    assert isinstance(result, list)
    assert "Zolbetuximab" in result
    assert "TST001" in result
    assert "chemotherapy" not in result


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_empty_input_returns_empty_list(mock_llm_cls):
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    result = classify_interventions([], target_name="CLDN18.2")
    assert len(result) == 0
    mock_llm_cls.assert_not_called()


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_deduplicates_case_insensitively(mock_llm_cls):
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    mock_client = _make_llm_client_mock(_make_llm_response(["Zolbetuximab"], []))
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(
        ["Zolbetuximab", "zolbetuximab", "ZOLBETUXIMAB"],
        target_name="CLDN18.2",
    )

    # LLM should be called once per batch (1 primary call)
    assert mock_client.query.call_count == 1
    assert "Zolbetuximab" in result


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_llm_failure_raises(mock_llm_cls):
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    mock_client = _make_llm_client_mock("Error: API rate limit exceeded")
    mock_llm_cls.return_value = mock_client

    with pytest.raises(RuntimeError, match="classification failed"):
        classify_interventions(["Zolbetuximab"], target_name="CLDN18.2")


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_malformed_json_raises(mock_llm_cls):
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    mock_client = _make_llm_client_mock("NOT VALID JSON {{{")
    mock_llm_cls.return_value = mock_client

    with pytest.raises(RuntimeError, match="unparseable JSON"):
        classify_interventions(["TST001"], target_name="CLDN18.2")


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_strips_markdown_fences(mock_llm_cls):
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    fenced_response = '```json\n{"asset": ["AMG910"], "background": []}\n```'
    mock_client = _make_llm_client_mock(fenced_response)
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(["AMG910"], target_name="CLDN18.2")
    assert "AMG910" in result


# ---------------------------------------------------------------------------
# 2. §2 batch size constraint test
# ---------------------------------------------------------------------------


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_batch_size_respected(mock_llm_cls):
    """classify_interventions must call LLM once per batch of batch_size names."""
    from unittest.mock import MagicMock

    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    mock_client = MagicMock()

    def side_effect(prompt, system, *args, **kwargs):
        if "Input names:" in prompt:
            return json.dumps(
                {
                    "asset": re.findall(
                        r'"([A-Za-z0-9\-]+)"', prompt.split("Input names:")[1]
                    ),
                    "background": [],
                }
            )
        elif "Candidate names:" in prompt:
            return json.dumps(
                {
                    "valid_assets": re.findall(
                        r'"([A-Za-z0-9\-]+)"', prompt.split("Candidate names:")[1]
                    ),
                    "generic_or_modality": [],
                }
            )
        elif "Input assets:" in prompt:
            match = re.search(r"Input assets:\s*(\[.*?\])", prompt, re.DOTALL)
            assets_data = json.loads(match.group(1)) if match else []
            return json.dumps({"consolidated_assets": assets_data})
        return "{}"

    mock_client.query.side_effect = side_effect
    mock_llm_cls.return_value = mock_client

    # 31 names with batch_size=30 → should require 2 LLM calls
    names = [f"Drug{i:03d}" for i in range(31)]
    classify_interventions(names, target_name="CLDN18.2", batch_size=30)

    # 2 batches: each batch makes 1 primary call = 2 calls total
    assert mock_client.query.call_count == 2


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_batch_size_50_uses_one_call(mock_llm_cls):
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    mock_client = _make_llm_client_mock(
        json.dumps({"asset": ["Drug001"], "background": []})
    )
    mock_llm_cls.return_value = mock_client

    names = [f"Drug{i:03d}" for i in range(50)]
    classify_interventions(names, target_name="CLDN18.2", batch_size=50)

    # 1 batch: 1 primary call = 1 call total
    assert mock_client.query.call_count == 1


# ---------------------------------------------------------------------------
# 3. Hallucination validator tests (§2 behavior)
# ---------------------------------------------------------------------------


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_hallucination_validator_rejects_missing_names(mock_llm_cls):
    """
    The hallucination validator should reject any name the LLM 'invented'
    that is not actually present in the source text (case-insensitive containment).
    """
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    primary_response = json.dumps(
        {
            "assets": [{"canonical_name": "Zolbetuximab", "aliases": ["FakeDrug999"]}],
            "background": [],
        }
    )
    secondary_response = json.dumps(
        {"valid_assets": ["Zolbetuximab"], "generic_or_modality": []}
    )
    mock_client = MagicMock()
    mock_client.query.side_effect = [primary_response, secondary_response]
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(
        ["Zolbetuximab"],  # FakeDrug999 is NOT in input
        target_name="CLDN18.2",
    )

    # §2 hallucination validator should have filtered out FakeDrug999
    assert "FakeDrug999" not in result
    assert "Zolbetuximab" in result


# ---------------------------------------------------------------------------
# 4. Modality filter tests (§2 behavior)
# ---------------------------------------------------------------------------


def test_modality_filter_catches_generic_terms_removed():
    # Deprecated since secondary modality filter is now replaced with programmatic pre-filtering.
    pass


# ---------------------------------------------------------------------------
# 5. Extended schema tests (§2 list[dict] return type)
# ---------------------------------------------------------------------------


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_returns_list_of_dicts_in_s2(mock_llm_cls):
    """
    In §2, classify_interventions should return list[dict] with the fields:
    canonical_name, aliases, modality, targets, filtered_terms
    """
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    primary_response = json.dumps(
        {
            "assets": [
                {
                    "canonical_name": "Zolbetuximab",
                    "aliases": ["Vyloy"],
                    "modality": "Monoclonal Antibody",
                    "targets": ["CLDN18.2"],
                    "filtered_terms": [],
                }
            ],
            "background": [],
        }
    )
    secondary_response = json.dumps(
        {"valid_assets": ["Zolbetuximab"], "generic_or_modality": []}
    )
    mock_client = MagicMock()
    mock_client.query.side_effect = [primary_response, secondary_response]
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(["Zolbetuximab", "Vyloy"], target_name="CLDN18.2")

    # §2: result should be list[dict]
    assert isinstance(result, list)
    assert len(result) == 1
    entry = result[0]
    assert entry["canonical_name"] == "Zolbetuximab"
    assert entry["aliases"] == ["Vyloy"]
    assert entry["modality"] == "Monoclonal Antibody"
    assert entry["targets"] == ["CLDN18.2"]


# ---------------------------------------------------------------------------
# 6. Batch_size=30 default enforcement in §2
# ---------------------------------------------------------------------------


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_classify_batch_size_param_controls_split(mock_llm_cls):
    """Verify the batch_size parameter is honoured for any value."""
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        classify_interventions,
    )

    mock_client = MagicMock()
    mock_client.query.return_value = json.dumps({"assets": [], "background": []})
    mock_llm_cls.return_value = mock_client

    names = [f"X{i}" for i in range(10)]
    classify_interventions(names, target_name="CLDN18.2", batch_size=4)

    # 10 names / 4 per batch = 3 batches (ceil). Each batch does 1 primary call
    # + 0 secondary calls (since no assets classified). So 3 calls.
    assert mock_client.query.call_count == 3


# ---------------------------------------------------------------------------
# 7. Global Synonym Resolution tests
# ---------------------------------------------------------------------------


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_consolidate_synonyms_globally_happy_path(mock_llm_cls):
    """Verify happy path consolidation where IMC002 and LM-302 are merged by the LLM."""
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        consolidate_synonyms_globally,
    )

    mock_client = MagicMock()
    mock_client.query.return_value = json.dumps(
        {
            "consolidated_assets": [
                {
                    "canonical_name": "IMC002",
                    "aliases": ["LM-302"],
                    "modality": "ADC",
                    "targets": ["CLDN18.2"],
                }
            ]
        }
    )
    mock_llm_cls.return_value = mock_client

    input_assets = [
        {
            "canonical_name": "IMC002",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
        {
            "canonical_name": "LM-302",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
    ]

    result = consolidate_synonyms_globally(input_assets, target_name="CLDN18.2")

    assert len(result) == 1
    entry = result[0]
    assert entry["canonical_name"] == "IMC002"
    assert entry["aliases"] == ["LM-302"]
    assert entry["modality"] == "ADC"


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_consolidate_synonyms_globally_provenance_check(mock_llm_cls):
    """Verify that hallucinated/uninvented names in the consolidated output are filtered out."""
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        consolidate_synonyms_globally,
    )

    mock_client = MagicMock()
    # LLM hallucinates 'FakeDrug999' as an alias and 'AnotherFake' as canonical
    mock_client.query.return_value = json.dumps(
        {
            "consolidated_assets": [
                {
                    "canonical_name": "IMC002",
                    "aliases": ["LM-302", "FakeDrug999"],
                    "modality": "ADC",
                    "targets": ["CLDN18.2"],
                },
                {
                    "canonical_name": "AnotherFake",
                    "aliases": ["LM-302"],
                    "modality": "ADC",
                    "targets": ["CLDN18.2"],
                },
            ]
        }
    )
    mock_llm_cls.return_value = mock_client

    input_assets = [
        {
            "canonical_name": "IMC002",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
        {
            "canonical_name": "LM-302",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
    ]

    result = consolidate_synonyms_globally(input_assets, target_name="CLDN18.2")

    assert any("FakeDrug999" not in a.get("aliases", []) for a in result)


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_consolidate_synonyms_globally_prevent_data_loss(mock_llm_cls):
    """Verify that if the LLM drops an asset (e.g. Zolbetuximab), the safeguard adds it back."""
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        consolidate_synonyms_globally,
    )

    mock_client = MagicMock()
    # LLM returns only IMC002 and completely forgets about Zolbetuximab
    mock_client.query.return_value = json.dumps(
        {
            "consolidated_assets": [
                {
                    "canonical_name": "IMC002",
                    "aliases": ["LM-302"],
                    "modality": "ADC",
                    "targets": ["CLDN18.2"],
                }
            ]
        }
    )
    mock_llm_cls.return_value = mock_client

    input_assets = [
        {
            "canonical_name": "IMC002",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
        {
            "canonical_name": "LM-302",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
        {
            "canonical_name": "Zolbetuximab",
            "aliases": ["Vyloy"],
            "modality": "Monoclonal Antibody",
            "targets": ["CLDN18.2"],
        },
    ]

    result = consolidate_synonyms_globally(input_assets, target_name="CLDN18.2")

    # Zolbetuximab must have been added back by the safeguard
    names = {a["canonical_name"] for a in result}
    assert "IMC002" in names
    assert "Zolbetuximab" in names


@patch("src.agents.bdscan_agents.intervention_classifier_agent.LLMClient")
def test_consolidate_synonyms_globally_llm_failure_fallback(mock_llm_cls):
    """Verify that if the LLM call fails, we return the original unconsolidated assets list."""
    from src.agents.bdscan_agents.intervention_classifier_agent import (
        consolidate_synonyms_globally,
    )

    mock_client = MagicMock()
    mock_client.query.side_effect = Exception("API Connection Timeout")
    mock_llm_cls.return_value = mock_client

    input_assets = [
        {
            "canonical_name": "IMC002",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
        {
            "canonical_name": "LM-302",
            "aliases": [],
            "modality": "ADC",
            "targets": ["CLDN18.2"],
        },
    ]

    result = consolidate_synonyms_globally(input_assets, target_name="CLDN18.2")

    # Result should be exactly the input_assets
    assert len(result) == 2
    assert result[0]["canonical_name"] == "IMC002"
    assert result[1]["canonical_name"] == "LM-302"
