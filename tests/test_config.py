from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.core.config import Settings, config_exists, load_config, save_config
from src.services.llm_client import LLMClient


@pytest.fixture
def temp_config_path(tmp_path):
    temp_file = tmp_path / ".env"
    with patch("src.core.config.CONFIG_FILE_PATH", temp_file):
        yield temp_file


def test_settings_backwards_compatibility(temp_config_path):
    # Setup legacy configuration format
    temp_config_path.write_text(
        'FULL_NAME="Legacy User"\n'
        'EMAIL="legacy@test.com"\n'
        'BASE_FOLDER="legacy_base"\n'
        'GEMINI_API_KEY="legacy_gemini_key"\n',  # pragma: allowlist secret
        encoding="utf-8",
    )

    assert config_exists() is True
    settings = load_config()

    assert settings.full_name == "Legacy User"
    assert settings.email == "legacy@test.com"
    assert settings.base_folder == "legacy_base"
    assert settings.gemini_api_key == "legacy_gemini_key"  # pragma: allowlist secret
    assert settings.openrouter_api_key is None
    assert settings.deepseek_api_key is None
    assert settings.llm_provider == "gemini"
    assert settings.llm_model is None
    assert settings.gemini_model is None
    assert settings.openrouter_model is None
    assert settings.deepseek_model is None


def test_settings_base_folder_expansion(temp_config_path):
    temp_config_path.write_text(
        'FULL_NAME="Test User"\n'
        'EMAIL="test@test.com"\n'
        'BASE_FOLDER="~/Desktop/AI_Native_2026"\n',
        encoding="utf-8",
    )

    settings = load_config()
    expected_path = str(Path.home() / "Desktop" / "AI_Native_2026")
    assert settings.base_folder == expected_path


def test_settings_save_and_load(temp_config_path):
    original_settings = Settings(
        full_name="Tiger Huang",
        email="tiger@example.com",
        base_folder="AI_Biotech",
        gemini_api_key="gem_key",  # pragma: allowlist secret
        openrouter_api_key="or_key",  # pragma: allowlist secret
        deepseek_api_key="ds_key",  # pragma: allowlist secret
        llm_provider="openrouter",
        llm_model="meta-llama/llama-3.1-70b-instruct",
        gemini_model="gemini-1.5-pro",
        openrouter_model="meta-llama/llama-3.1-70b-instruct",
        deepseek_model="deepseek-coder",
    )

    save_config(original_settings)
    assert config_exists() is True

    loaded = load_config()
    assert loaded.full_name == "Tiger Huang"
    assert loaded.email == "tiger@example.com"
    assert loaded.base_folder == "AI_Biotech"
    assert loaded.gemini_api_key == "gem_key"  # pragma: allowlist secret
    assert loaded.openrouter_api_key == "or_key"  # pragma: allowlist secret
    assert loaded.deepseek_api_key == "ds_key"  # pragma: allowlist secret
    assert loaded.llm_provider == "openrouter"
    assert loaded.llm_model == "meta-llama/llama-3.1-70b-instruct"
    assert loaded.gemini_model == "gemini-1.5-pro"
    assert loaded.openrouter_model == "meta-llama/llama-3.1-70b-instruct"
    assert loaded.deepseek_model == "deepseek-coder"


@patch("src.services.llm_client.load_config")
@patch("httpx.Client.post")
def test_llm_client_routing_gemini(mock_post, mock_load_config):
    mock_load_config.return_value = Settings(
        full_name="Test",
        email="test@test.com",
        gemini_api_key="gem_key",  # pragma: allowlist secret
        llm_provider="gemini",
        llm_model="custom-gemini-2.0",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Hello Gemini"}]}}]
    }
    mock_post.return_value = mock_response

    client = LLMClient()
    response = client.query("test prompt")
    assert response == "Hello Gemini"

    # Verify that the HTTP POST request contains correct URL format with custom model
    called_url = mock_post.call_args[0][0]
    assert "custom-gemini-2.0:generateContent" in called_url
    assert "key=gem_key" in called_url


@patch("src.services.llm_client.load_config")
@patch("httpx.Client.post")
def test_llm_client_routing_openrouter(mock_post, mock_load_config):
    mock_load_config.return_value = Settings(
        full_name="Test",
        email="test@test.com",
        openrouter_api_key="or_key",  # pragma: allowlist secret
        llm_provider="openrouter",
        llm_model="custom-or-model",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello OpenRouter"}}]
    }
    mock_post.return_value = mock_response

    client = LLMClient()
    response = client.query("test prompt")
    assert response == "Hello OpenRouter"

    # Verify model is passed correctly in payload
    called_json = mock_post.call_args[1]["json"]
    assert called_json["model"] == "custom-or-model"
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer or_key"


@patch("src.services.llm_client.load_config")
@patch("httpx.Client.post")
def test_llm_client_routing_deepseek(mock_post, mock_load_config):
    mock_load_config.return_value = Settings(
        full_name="Test",
        email="test@test.com",
        deepseek_api_key="ds_key",  # pragma: allowlist secret
        llm_provider="deepseek",
        llm_model="custom-ds-model",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello DeepSeek"}}]
    }
    mock_post.return_value = mock_response

    client = LLMClient()
    response = client.query("test prompt")
    assert response == "Hello DeepSeek"

    # Verify model is passed correctly in payload
    called_json = mock_post.call_args[1]["json"]
    assert called_json["model"] == "custom-ds-model"
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ds_key"


@patch("src.services.llm_client.load_config")
@patch("httpx.Client.post")
def test_llm_client_connection_retry(mock_post, mock_load_config):
    mock_load_config.return_value = Settings(
        full_name="Test",
        email="test@test.com",
        gemini_api_key="gem_key",  # pragma: allowlist secret
        llm_provider="gemini",
    )

    # Mock post to raise RequestError
    mock_post.side_effect = httpx.RequestError(
        "Connection timeout", request=MagicMock()
    )

    client = LLMClient()
    client.max_connection_retries = 2
    client.initial_connection_delay = 0.001

    with patch("time.sleep") as mock_sleep:
        response = client.query("test prompt")
        # Since it fails permanently, it should return an error message
        assert "Failed to call" in response
        # 1 initial call + 2 retries = 3 calls
        assert mock_post.call_count == 3
        # Should have slept 2 times
        assert mock_sleep.call_count == 2


@patch("src.services.llm_client.load_config")
@patch("httpx.Client.post")
def test_llm_client_llm_level_retry(mock_post, mock_load_config):
    mock_load_config.return_value = Settings(
        full_name="Test",
        email="test@test.com",
        gemini_api_key="gem_key",  # pragma: allowlist secret
        llm_provider="gemini",
    )

    # Mock post to return HTTP status error (e.g., 429)
    response_429 = MagicMock()
    response_429.status_code = 429
    response_429.text = "Rate Limit Exceeded"
    response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Rate Limit", request=MagicMock(), response=response_429
    )
    mock_post.return_value = response_429

    client = LLMClient()
    client.max_llm_retries = 2
    client.initial_llm_delay = 0.001

    with patch("time.sleep") as mock_sleep:
        response = client.query("test prompt")
        assert "Failed to call" in response
        # 1 initial call + 2 retries = 3 calls
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2


@patch("src.services.llm_client.load_config")
@patch("httpx.Client.post")
def test_llm_client_fatal_error_no_retry(mock_post, mock_load_config):
    mock_load_config.return_value = Settings(
        full_name="Test",
        email="test@test.com",
        gemini_api_key="gem_key",  # pragma: allowlist secret
        llm_provider="gemini",
    )

    response_401 = MagicMock()
    response_401.status_code = 401
    response_401.text = "Unauthorized key"
    response_401.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=response_401
    )
    mock_post.return_value = response_401

    client = LLMClient()

    with patch("time.sleep") as mock_sleep:
        response = client.query("test prompt")
        assert "Failed to call" in response
        # 401 is fatal, should only try once
        assert mock_post.call_count == 1
        assert mock_sleep.call_count == 0


def test_llm_queue_manager_sequential():
    import queue
    import time

    from src.services.llm_client import LLMQueueManager

    mgr = LLMQueueManager()
    mgr.start_worker()

    execution_order = []

    def task_fn(val, delay):
        time.sleep(delay)
        execution_order.append(val)
        return val

    res_q1 = queue.Queue()
    res_q2 = queue.Queue()

    # Push job 1 (slow) then job 2 (fast)
    mgr.queue.put((task_fn, (1, 0.05), {}, res_q1))
    mgr.queue.put((task_fn, (2, 0.01), {}, res_q2))

    # Wait for results
    res1, err1 = res_q1.get()
    res2, err2 = res_q2.get()

    assert res1 == 1
    assert res2 == 2
    # Even though job 2 has a much smaller sleep delay, it must finish AFTER job 1
    # because the queue executes them sequentially.
    assert execution_order == [1, 2]

    # Stop worker
    mgr._stop_event.set()
    mgr.queue.put(None)
    if mgr.worker_thread:
        mgr.worker_thread.join(timeout=1.0)
