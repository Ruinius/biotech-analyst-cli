import json
from unittest.mock import patch

from src.utils.query_parser import fallback_parse, parse_query_via_llm


def test_fallback_parse_modality_and_indications():
    # Test target with modality
    res1 = fallback_parse("Claudin 18.2 ADC")
    assert res1["target_name"] == "Claudin 18.2"
    assert res1["modality"] == "ADC"
    assert "Claudin 18.2" in res1["en_list"]
    assert "Claudin18.2" in res1["en_list"]
    assert "Claudin-18.2" in res1["en_list"]

    # Test target with indication and no modality
    res2 = fallback_parse("Claudin 18.2 pancreatic cancer")
    assert res2["target_name"] == "Claudin 18.2"
    assert res2["modality"] == ""
    assert "Claudin 18.2" in res2["en_list"]
    assert "Claudin-18.2" in res2["en_list"]

    # Test plain target
    res3 = fallback_parse("Claudin 18.2")
    assert res3["target_name"] == "Claudin 18.2"
    assert res3["modality"] == ""

    # Test target with other modality
    res4 = fallback_parse("EGFR Bispecific solid tumors")
    assert res4["target_name"] == "EGFR"
    assert res4["modality"] == "Bispecific"


@patch("src.services.llm_client.LLMClient.query")
def test_parse_query_via_llm_success(mock_query):
    # LLM returns clean JSON
    mock_query.return_value = json.dumps(
        {
            "target_name": "Claudin 18.2",
            "en_list": ["CLDN18.2", "Claudin 18.2"],
            "zh_list": ["克劳丁 18.2", "CLDN18.2"],
            "modality": "ADC",
        }
    )

    res = parse_query_via_llm("Claudin 18.2 ADC")
    assert res["target_name"] == "Claudin 18.2"
    assert res["modality"] == "ADC"
    assert "CLDN18.2" in res["en_list"]
    assert "克劳丁 18.2" in res["zh_list"]


@patch("src.services.llm_client.LLMClient.query")
def test_parse_query_via_llm_markdown_json(mock_query):
    # LLM returns JSON enclosed in markdown code block
    mock_query.return_value = (
        "```json\n"
        "{\n"
        '  "target_name": "Claudin 18.2",\n'
        '  "en_list": ["CLDN18.2"],\n'
        '  "zh_list": ["CLDN18.2"],\n'
        '  "modality": "ADC"\n'
        "}\n"
        "```"
    )

    res = parse_query_via_llm("Claudin 18.2 ADC")
    assert res["target_name"] == "Claudin 18.2"
    assert res["modality"] == "ADC"
    assert res["en_list"] == ["CLDN18.2"]


@patch("src.services.llm_client.LLMClient.query")
def test_parse_query_via_llm_fallback(mock_query):
    # LLM returns an error prefix
    mock_query.return_value = "Error: Invalid API Key"
    res = parse_query_via_llm("Claudin 18.2 ADC")
    # Verify it falls back to regex parser
    assert res["target_name"] == "Claudin 18.2"
    assert res["modality"] == "ADC"

    # LLM returns garbage string
    mock_query.return_value = "This is a random non-json response."
    res2 = parse_query_via_llm("Claudin 18.2 pancreatic cancer")
    assert res2["target_name"] == "Claudin 18.2"
    assert res2["modality"] == ""
