import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("agentflow.ollama")

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"


class OllamaClient:
    """
    Client for interacting with local open-source models running via Ollama.
    Supports lightweight models like llama3.2:1b and all-minilm.
    Gracefully fails over to deterministic extraction if the local daemon is unavailable.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.timeout = timeout

    async def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable and responding."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/version")
                return res.status_code == 200
        except Exception:
            return False

    async def extract_structured_resume(
        self, raw_text: str, timeout_override: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Request structured profile extraction in JSON format using local llama3.2:1b.
        Returns parsed dictionary or None if Ollama is offline or unparseable.
        """
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
            "Output JSON only:"
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }

        timeout = timeout_override or self.timeout
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code != 200:
                    logger.warning(
                        "Ollama request returned status %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return None

                data = response.json()
                raw_response = data.get("response", "")
                if not raw_response:
                    return None

                parsed = json.loads(raw_response)
                return parsed if isinstance(parsed, dict) else None

        except httpx.ConnectError:
            logger.info("Ollama is not running at %s, falling back to deterministic extractor.", self.base_url)
            return None
        except httpx.TimeoutException:
            logger.warning("Ollama call timed out after %s seconds, falling back to deterministic parser.", timeout)
            return None
        except Exception as e:
            logger.warning("Ollama extraction encountered error (%s), using deterministic parser.", e)
            return None

