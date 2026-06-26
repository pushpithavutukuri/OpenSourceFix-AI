"""
llm_client.py
Thin adapters so fix_generator.py stays model-agnostic.
Every adapter exposes:   generate(prompt: str) -> str
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str: ...


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
class GeminiClient(BaseLLMClient):
    """Wraps google-generativeai."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    def generate(self, prompt: str) -> str:
        response = self._model.generate_content(prompt)
        return response.text


# ---------------------------------------------------------------------------
# OpenAI-compatible (Qwen, LM Studio, Ollama, etc.)
# ---------------------------------------------------------------------------
class OpenAICompatibleClient(BaseLLMClient):
    """Works with any OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(self, base_url: str, api_key: str = "no-key", model: str = "qwen"):
        from openai import OpenAI
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_llm_client(config: dict) -> BaseLLMClient:
    """
    Build the right client from config.yaml settings.

    Config example:
        llm:
          backend: gemini          # or openai_compatible
          api_key: YOUR_KEY
          model: gemini-1.5-flash
          base_url: ""             # only for openai_compatible
    """
    backend = config.get("backend", "gemini")
    if backend == "gemini":
        return GeminiClient(api_key=config["api_key"], model=config.get("model", "gemini-1.5-flash"))
    elif backend == "openai_compatible":
        return OpenAICompatibleClient(
            base_url=config["base_url"],
            api_key=config.get("api_key", "no-key"),
            model=config.get("model", "qwen"),
        )
    else:
        raise ValueError(f"Unknown LLM backend: {backend}")
