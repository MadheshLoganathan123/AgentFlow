import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from packages.contracts.profile import WorkModePreference
from services.api.services.extractor import ResumeExtractorService
from services.api.services.huggingface_client import HuggingFaceClient


def test_huggingface_client_initialization():
    """Verify HuggingFaceClient initializes correctly with custom and default parameters."""
    client = HuggingFaceClient(token="hf_test_token_123", model="Qwen/Qwen2.5-1.5B-Instruct")
    assert client.token == "hf_test_token_123"
    assert client.model == "Qwen/Qwen2.5-1.5B-Instruct"
    assert client.is_configured is True
    assert client._get_headers()["Authorization"] == "Bearer hf_test_token_123"

    empty_client = HuggingFaceClient(token="", model="test-model")
    assert empty_client.is_configured is False
    assert "Authorization" not in empty_client._get_headers()


@pytest.mark.asyncio
async def test_extract_structured_resume_success():
    """Verify successful parsing when Hugging Face returns structured JSON."""
    client = HuggingFaceClient(token="hf_mock_token", model="Qwen/Qwen2.5-1.5B-Instruct")

    fake_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "full_name": "Alice Cooper",
                        "email": "alice@example.com",
                        "phone": "555-0199",
                        "primary_location": "New York, NY",
                        "work_modes": ["remote"],
                        "target_job_titles": ["Senior ML Engineer"],
                        "total_years_experience": 7.0,
                        "work_authorization": "US Citizen",
                    })
                }
            }
        ]
    }

    mock_resp = httpx.Response(200, json=fake_response, request=httpx.Request("POST", "http://test"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.extract_structured_resume("Raw resume content...")

    assert result is not None
    assert result["full_name"] == "Alice Cooper"
    assert result["email"] == "alice@example.com"
    assert result["total_years_experience"] == 7.0
    assert result["work_authorization"] == "US Citizen"


@pytest.mark.asyncio
async def test_extract_structured_resume_402_graceful_fallback():
    """Verify that HTTP 402 (payment/credits required) gracefully returns None without raising."""
    client = HuggingFaceClient(token="hf_mock_token")
    mock_resp = httpx.Response(402, text="Purchase credits", request=httpx.Request("POST", "http://test"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.extract_structured_resume("Raw resume content...")

    assert result is None


@pytest.mark.asyncio
async def test_extract_structured_resume_timeout_graceful():
    """Verify that network timeout returns None gracefully."""
    client = HuggingFaceClient(token="hf_mock_token")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")):
        result = await client.extract_structured_resume("Raw resume content...")

    assert result is None


@pytest.mark.asyncio
async def test_parse_profile_async_with_hf_integration():
    """Verify ResumeExtractorService integrates HF client output when available."""
    mock_hf_client = HuggingFaceClient(token="hf_mock_token", model="Qwen/Qwen2.5-1.5B-Instruct")

    ai_dict = {
        "full_name": "Dr. Evelyn Reed",
        "email": "evelyn@ai-lab.org",
        "phone": "555-4321",
        "primary_location": "Boston, MA",
        "work_modes": ["remote"],
        "target_job_titles": ["Principal AI Scientist"],
        "total_years_experience": 10.0,
        "work_authorization": "Permanent Resident",
    }

    with patch.object(mock_hf_client, "extract_structured_resume", new_callable=AsyncMock, return_value=ai_dict):
        profile = await ResumeExtractorService.parse_profile_async(
            "Dr. Evelyn Reed. Principal AI Scientist at Lab. Python, PyTorch, Docker.",
            user_id="user_evelyn",
            hf_client=mock_hf_client,
        )

    assert profile.full_name == "Dr. Evelyn Reed"
    assert profile.email == "evelyn@ai-lab.org"
    assert profile.primary_location == "Boston, MA"
    assert WorkModePreference.REMOTE in profile.work_modes
    assert profile.total_years_experience == 10.0
    assert profile.work_authorization == "Permanent Resident"
    assert profile.model_version.startswith("hf_")


@pytest.mark.asyncio
async def test_generate_text_success():
    """Verify general text generation method."""
    client = HuggingFaceClient(token="hf_mock_token")
    fake_response = {
        "choices": [{"message": {"content": "Sample generated response"}}]
    }
    mock_resp = httpx.Response(200, json=fake_response, request=httpx.Request("POST", "http://test"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await client.generate_text("Summarize resume")

    assert res == "Sample generated response"

