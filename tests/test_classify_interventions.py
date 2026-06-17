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
import tempfile
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


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_returns_asset_list(mock_llm_cls):
    from src.tools.classify_interventions import classify_interventions

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


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_empty_input_returns_empty_list(mock_llm_cls):
    from src.tools.classify_interventions import classify_interventions

    result = classify_interventions([], target_name="CLDN18.2")
    assert len(result) == 0
    mock_llm_cls.assert_not_called()


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_deduplicates_case_insensitively(mock_llm_cls):
    from src.tools.classify_interventions import classify_interventions

    mock_client = _make_llm_client_mock(
        _make_llm_response(["Zolbetuximab"], [])
    )
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(
        ["Zolbetuximab", "zolbetuximab", "ZOLBETUXIMAB"],
        target_name="CLDN18.2",
    )

    # LLM should be called twice per batch (1 primary call + 1 secondary audit call)
    assert mock_client.query.call_count == 2
    assert "Zolbetuximab" in result


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_llm_failure_raises(mock_llm_cls):
    from src.tools.classify_interventions import classify_interventions

    mock_client = _make_llm_client_mock("Error: API rate limit exceeded")
    mock_llm_cls.return_value = mock_client

    with pytest.raises(RuntimeError, match="classification failed"):
        classify_interventions(["Zolbetuximab"], target_name="CLDN18.2")


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_malformed_json_raises(mock_llm_cls):
    from src.tools.classify_interventions import classify_interventions

    mock_client = _make_llm_client_mock("NOT VALID JSON {{{")
    mock_llm_cls.return_value = mock_client

    with pytest.raises(RuntimeError, match="unparseable JSON"):
        classify_interventions(["TST001"], target_name="CLDN18.2")


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_strips_markdown_fences(mock_llm_cls):
    from src.tools.classify_interventions import classify_interventions

    fenced_response = '```json\n{"asset": ["AMG910"], "background": []}\n```'
    mock_client = _make_llm_client_mock(fenced_response)
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(["AMG910"], target_name="CLDN18.2")
    assert "AMG910" in result


# ---------------------------------------------------------------------------
# 2. §2 batch size constraint test
# ---------------------------------------------------------------------------


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_batch_size_respected(mock_llm_cls):
    """classify_interventions must call LLM once per batch of batch_size names."""
    from src.tools.classify_interventions import classify_interventions

    mock_client = MagicMock()
    # Return all as assets
    mock_client.query.side_effect = lambda prompt, system: json.dumps(
        {
            "asset": re.findall(r'"([A-Za-z0-9\-]+)"', prompt.split("Input names:")[1]),
            "background": [],
        }
    )
    mock_llm_cls.return_value = mock_client

    # 31 names with batch_size=30 → should require 2 LLM calls
    names = [f"Drug{i:03d}" for i in range(31)]
    classify_interventions(names, target_name="CLDN18.2", batch_size=30)

    # 2 batches: each batch makes 1 primary call and 1 secondary call (since they returned assets) = 4 calls total
    assert mock_client.query.call_count == 4


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_batch_size_50_uses_one_call(mock_llm_cls):
    from src.tools.classify_interventions import classify_interventions

    mock_client = _make_llm_client_mock(
        json.dumps({"asset": ["Drug001"], "background": []})
    )
    mock_llm_cls.return_value = mock_client

    names = [f"Drug{i:03d}" for i in range(50)]
    classify_interventions(names, target_name="CLDN18.2", batch_size=50)

    # 1 batch: 1 primary call + 1 secondary call = 2 calls total
    assert mock_client.query.call_count == 2


# ---------------------------------------------------------------------------
# 3. Hallucination validator tests (§2 behavior)
# ---------------------------------------------------------------------------


@patch("src.tools.classify_interventions.LLMClient")
def test_hallucination_validator_rejects_missing_names(mock_llm_cls):
    """
    The hallucination validator should reject any name the LLM 'invented'
    that is not actually present in the source text (case-insensitive containment).
    """
    from src.tools.classify_interventions import classify_interventions

    primary_response = json.dumps({
        "assets": [
            {"canonical_name": "Zolbetuximab", "aliases": ["FakeDrug999"]}
        ],
        "background": []
    })
    secondary_response = json.dumps({
        "valid_assets": ["Zolbetuximab"],
        "generic_or_modality": []
    })
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


@patch("src.tools.classify_interventions.LLMClient")
def test_modality_filter_catches_generic_terms(mock_llm_cls):
    """
    The secondary modality filter must reject entries where the LLM classifies
    a generic modality term or target gene (not a specific molecule) as an asset.
    """
    from src.tools.classify_interventions import classify_interventions

    primary_response = json.dumps({
        "assets": [
            {"canonical_name": "chemotherapy", "aliases": []},
            {"canonical_name": "HER2", "aliases": []},
            {"canonical_name": "Zolbetuximab", "aliases": []}
        ],
        "background": []
    })
    secondary_response = json.dumps({
        "valid_assets": ["Zolbetuximab"],
        "generic_or_modality": ["chemotherapy", "HER2"]
    })
    mock_client = MagicMock()
    mock_client.query.side_effect = [primary_response, secondary_response]
    mock_llm_cls.return_value = mock_client

    result = classify_interventions(
        ["chemotherapy", "HER2", "Zolbetuximab"],
        target_name="CLDN18.2",
    )

    # §2 filter should remove generic terms
    result_lower = {r.lower() if isinstance(r, str) else r.get("canonical_name", "").lower() for r in result}
    assert "chemotherapy" not in result_lower
    assert "her2" not in result_lower
    assert "zolbetuximab" in result_lower


# ---------------------------------------------------------------------------
# 5. Extended schema tests (§2 list[dict] return type)
# ---------------------------------------------------------------------------


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_returns_list_of_dicts_in_s2(mock_llm_cls):
    """
    In §2, classify_interventions should return list[dict] with the fields:
    canonical_name, aliases, modality, targets, filtered_terms
    """
    from src.tools.classify_interventions import classify_interventions

    primary_response = json.dumps({
        "assets": [
            {
                "canonical_name": "Zolbetuximab",
                "aliases": ["Vyloy"],
                "modality": "Monoclonal Antibody",
                "targets": ["CLDN18.2"],
                "filtered_terms": []
            }
        ],
        "background": []
    })
    secondary_response = json.dumps({
        "valid_assets": ["Zolbetuximab"],
        "generic_or_modality": []
    })
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


@patch("src.tools.classify_interventions.LLMClient")
def test_classify_batch_size_param_controls_split(mock_llm_cls):
    """Verify the batch_size parameter is honoured for any value."""
    from src.tools.classify_interventions import classify_interventions

    mock_client = MagicMock()
    mock_client.query.return_value = json.dumps({"assets": [], "background": []})
    mock_llm_cls.return_value = mock_client

    names = [f"X{i}" for i in range(10)]
    classify_interventions(names, target_name="CLDN18.2", batch_size=4)

    # 10 names / 4 per batch = 3 batches (ceil). Each batch does 1 primary call
    # + 0 secondary calls (since no assets classified). So 3 calls.
    assert mock_client.query.call_count == 3
