import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from services.api.config import settings

logger = logging.getLogger("agentflow.huggingface")

DEFAULT_HF_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
HF_ROUTER_URL = "https://router.huggingface.co/v1"


class HuggingFaceClient:
    """
    Client for interacting with lightweight open-source models hosted via Hugging Face.
    Uses Hugging Face token for authentication.
    Gracefully falls back to deterministic extraction if the API is unreachable,
    rate-limited, or returns payment/credit required errors (e.g. HTTP 402).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 15.0,
    ):
        if token is not None:
            self.token = token.strip()
        else:
            self.token = (settings.hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or "").strip()
        self.model = model or settings.hf_model_name or os.getenv("HF_MODEL_NAME") or DEFAULT_HF_MODEL
        self.timeout = timeout
        self.base_url = HF_ROUTER_URL

    @property
    def is_configured(self) -> bool:
        """Check if Hugging Face token is configured."""
        return bool(self.token and self.token.strip())

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token.strip()}"
        return headers

    async def extract_structured_resume(
        self, raw_text: str, timeout_override: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Request structured profile extraction in JSON format using a lightweight open-source
        model on Hugging Face.
        Returns parsed dictionary or None if HF is unconfigured, unreachable, or unparseable.
        """
        if not self.is_configured:
            logger.info("Hugging Face token not provided; bypassing HF extraction.")
            return None

        prompt = (
            "You are an expert resume parsing system. Parse the following resume text into a valid JSON object.\n"
            "Strict JSON schema:\n"
            "{\n"
            '  "full_name": "string",\n'
            '  "email": "string or null",\n'
            '  "phone": "string or null",\n'
            '  "primary_location": "string or null",\n'
            '  "work_modes": ["remote" | "hybrid" | "onsite"],\n'
            '  "target_job_titles": ["string"],\n'
            '  "total_years_experience": number or null,\n'
            '  "work_authorization": "string or null",\n'
            '  "notice_period_days": number or null,\n'
            '  "target_salary_min": number or null,\n'
            '  "preferred_sectors": ["string"],\n'
            '  "skills": [{"name": "string", "category": "string", "years_experience": number, "raw_snippet": "string"}],\n'
            '  "experience": [{"company": "string", "title": "string", "location": "string", "start_date": "string", "end_date": "string", "is_current": boolean, "highlights": ["string"], "raw_snippet": "string"}],\n'
            '  "education": [{"institution": "string", "degree": "string", "field_of_study": "string", "graduation_year": number, "raw_snippet": "string"}]\n'
            "}\n\n"
            "Resume Text:\n"
            f"{raw_text[:4000]}\n\n"
            "Output JSON only without any markdown formatting or commentary:"
        )

        messages = [
            {"role": "system", "content": "You are a precise resume extraction system that outputs valid JSON only."},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1500,
        }

        timeout = timeout_override or self.timeout
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code == 402:
                    logger.warning(
                        "Hugging Face serverless router requires pre-paid credits. "
                        "Gracefully falling back to local deterministic extractor."
                    )
                    return None

                if response.status_code != 200:
                    logger.warning(
                        "Hugging Face API returned status %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return None

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return None

                raw_content = choices[0].get("message", {}).get("content", "").strip()
                if not raw_content:
                    return None

                # Clean markdown json code fences if present
                clean_content = re.sub(r"^```(?:json)?\s*", "", raw_content, flags=re.MULTILINE)
                clean_content = re.sub(r"\s*```$", "", clean_content, flags=re.MULTILINE).strip()

                parsed = json.loads(clean_content)
                return parsed if isinstance(parsed, dict) else None

        except httpx.ConnectError:
            logger.info("Unable to connect to Hugging Face API, falling back to deterministic extractor.")
            return None
        except httpx.TimeoutException:
            logger.warning("Hugging Face API call timed out after %s seconds, falling back to deterministic parser.", timeout)
            return None
        except Exception as e:
            logger.warning("Hugging Face extraction encountered error (%s), using deterministic parser.", e)
            return None

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> Optional[str]:
        """Generate text completions using the configured lightweight Hugging Face model."""
        if not self.is_configured:
            return None

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
                else:
                    logger.warning("Hugging Face generate_text failed with status %s", res.status_code)
                    return None
        except Exception as e:
            logger.warning("Hugging Face generate_text error: %s", e)
            return None
