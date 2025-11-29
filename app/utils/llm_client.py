from __future__ import annotations

import logging
import os
from typing import Dict

import requests

from app.prompts.analysis import CANDIDATE_FEEDBACK_PROMPT
from app.utils.text_utils import split_sentences

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "gemma3:1b"


def _get_base_url(ollama_url: str) -> str:
    """
    Strip the /api suffix so we can hit other Ollama endpoints.
    """
    return ollama_url.split("/api", 1)[0]


class LLMClient:
    """
    Ollama-powered LLM client (no external API keys required).
    """

    def __init__(self, temperature: float = 0.2):
        self.ollama_url = os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)
        self.model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.temperature = temperature
        self.prompt_template = CANDIDATE_FEEDBACK_PROMPT

    def analyze_candidate(
        self, candidate_name: str, job_description: str, resume_text: str
    ) -> Dict[str, str]:
        """
        Generate qualitative insights with Ollama; fallback to heuristics if the
        local model is not available.
        """
        if self.prompt_template:
            try:
                prompt = self.prompt_template.format(
                    candidate_name=candidate_name,
                    job_description=job_description,
                    resume_text=resume_text,
                )
                content = self._call_ollama(prompt)
                return self._parse_llm_response(content)
            except Exception as exc:  # pragma: no cover - runtime dependency
                logger.warning("Ollama analysis failed (%s); using heuristics.", exc)

        sentences = split_sentences(resume_text)
        summary = " ".join(sentences[:3]) if sentences else "Summary unavailable."
        return {
            "strengths": "Solid baseline profile with relevant experience.",
            "weaknesses": "Needs deeper alignment verification via interview.",
            "reasoning": summary,
        }

    def _call_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": float(self.temperature),
            "stream": False,
            "max_tokens": 512,
        }
        response = requests.post(self.ollama_url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            chunks = [
                chunk.get("response") or chunk.get("text") or chunk.get("output")
                for chunk in data
            ]
            return "".join(filter(None, chunks))
        return (
            data.get("response")
            or data.get("text")
            or data.get("output")
            or str(data)
        )

    def health_check(self, timeout: int = 2) -> dict:
        """
        Ping the Ollama server for available models. Tries multiple endpoints to
        stay compatible across versions.
        """
        base_url = _get_base_url(self.ollama_url).rstrip("/")
        endpoints = ["/api/models", "/api/tags", "/api/status"]
        for path in endpoints:
            try:
                response = requests.get(f"{base_url}{path}", timeout=timeout)
                if response.status_code == 200:
                    data = response.json()
                    model_names = self._parse_model_list(data)
                    return {"ok": True, "msg": "Ollama reachable", "models": model_names}
                # Treat 404 as reachable if at least one endpoint responds
                if response.status_code == 404:
                    return {"ok": True, "msg": "Ollama reachable (no model list)", "models": []}
            except Exception:
                continue
        return {"ok": False, "msg": "Unable to reach Ollama", "models": None}

    @staticmethod
    def _parse_model_list(data) -> list[str]:
        models: list[str] = []
        if isinstance(data, dict):
            entries = data.get("models") or data.get("data") or []
        else:
            entries = data

        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("model")
                    if name:
                        models.append(name)
                elif isinstance(item, str):
                    models.append(item)
        return models

    @staticmethod
    def _parse_llm_response(content: str) -> Dict[str, str]:
        sections = {"strengths": "", "weaknesses": "", "reasoning": ""}
        current_key = None
        for line in content.splitlines():
            lower = line.lower()
            if "strength" in lower:
                current_key = "strengths"
                sections[current_key] = line.split(":", 1)[-1].strip()
            elif "weakness" in lower:
                current_key = "weaknesses"
                sections[current_key] = line.split(":", 1)[-1].strip()
            elif "reason" in lower:
                current_key = "reasoning"
                sections[current_key] = line.split(":", 1)[-1].strip()
            elif current_key:
                sections[current_key] += f" {line.strip()}"

        return {k: v.strip() or "Not provided." for k, v in sections.items()}

