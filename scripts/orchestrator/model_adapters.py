"""Multi-model provider adapters and intelligent routing engine.

Supports Claude, Opencode, Ollama (local), OpenRouter, Antigravity (Gemini),
Cursor, and Codex.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

logger = logging.getLogger("orchestrator.models")


class ModelProvider(str, Enum):
    """Supported model provider backends."""

    CLAUDE = "claude"
    OPENCODE = "opencode"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    AGY = "agy"
    CURSOR = "cursor"
    CODEX = "codex"
    MOCK = "mock"


class TaskTier(str, Enum):
    """Task complexity and routing tier."""

    LOCAL_FAST = "local_fast"          # Bounded checks, formatting, linting, syntax verification
    FREE_HOSTED = "free_hosted"        # Surveying, bulk search, lightweight triage
    STANDARD_CODE = "standard_code"    # Standard implementation, refactoring, documentation
    FRONTIER_HEAVY = "frontier_heavy"  # Complex architecture, subtle debugging, cross-file design
    ADVERSARIAL_REVIEW = "adversarial_review"  # Cross-model independent verification


@dataclass
class ModelSpec:
    """Specification of an AI model instance."""

    provider: ModelProvider
    model_name: str
    tier: TaskTier
    is_local: bool = False
    context_window: int = 128000
    cost_per_m_tokens: float = 0.0


@dataclass
class ModelResponse:
    """Unified response from any model provider."""

    success: bool
    content: str
    model_used: str
    provider: ModelProvider
    execution_time_seconds: float
    raw_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseModelAdapter(ABC):
    """Abstract interface for all model provider backends."""

    provider: ModelProvider

    @abstractmethod
    def is_available(self) -> bool:
        """Check if CLI tool or API credentials for this provider are ready."""
        raise NotImplementedError

    @abstractmethod
    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        """Execute a prompt against the model provider."""
        raise NotImplementedError


class OllamaAdapter(BaseModelAdapter):
    """Local Ollama model runner with fallback between direct REST API and opencode."""

    provider = ModelProvider.OLLAMA

    def __init__(self, base_url: str = "http://127.0.0.1:11434", default_model: str = "qwen2.5-coder:7b"):
        self.base_url = base_url
        self.default_model = default_model

    def is_available(self) -> bool:
        """Check if Ollama local server is responding."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        start_time = time.time()
        target_model = model or self.default_model

        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("response", "")
                return ModelResponse(
                    success=True,
                    content=content,
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    raw_output=data,
                )
        except Exception as exc:
            # Fallback to opencode run -m ollama/<model> if CLI is present
            if shutil.which("opencode"):
                try:
                    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                    cmd = ["opencode", "run", "-m", f"ollama/{target_model}", full_prompt]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
                    if proc.returncode == 0:
                        return ModelResponse(
                            success=True,
                            content=proc.stdout,
                            model_used=f"ollama/{target_model}",
                            provider=self.provider,
                            execution_time_seconds=time.time() - start_time,
                        )
                except Exception:
                    pass

            return ModelResponse(
                success=False,
                content="",
                model_used=target_model,
                provider=self.provider,
                execution_time_seconds=time.time() - start_time,
                error=f"Ollama execution error: {str(exc)}",
            )


class OpencodeAdapter(BaseModelAdapter):
    """Opencode CLI adapter supporting hosted free models and multi-provider bridging."""

    provider = ModelProvider.OPENCODE

    def __init__(self, default_model: str = "opencode/deepseek-v4-flash-free"):
        self.default_model = default_model

    def is_available(self) -> bool:
        return shutil.which("opencode") is not None

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        start_time = time.time()
        target_model = model or self.default_model

        if not self.is_available():
            return ModelResponse(
                success=False,
                content="",
                model_used=target_model,
                provider=self.provider,
                execution_time_seconds=0.0,
                error="opencode CLI executable not found on PATH.",
            )

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        cmd = ["opencode", "run", "-m", target_model, full_prompt]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
            if proc.returncode == 0:
                return ModelResponse(
                    success=True,
                    content=proc.stdout.strip(),
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                )
            else:
                return ModelResponse(
                    success=False,
                    content=proc.stdout,
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=proc.stderr.strip() or f"opencode exited with code {proc.returncode}",
                )
        except Exception as exc:
            return ModelResponse(
                success=False,
                content="",
                model_used=target_model,
                provider=self.provider,
                execution_time_seconds=time.time() - start_time,
                error=str(exc),
            )


class OpenRouterAdapter(BaseModelAdapter):
    """OpenRouter adapter supporting frontier and stealth model pools."""

    provider = ModelProvider.OPENROUTER

    def __init__(self, api_key: Optional[str] = None, default_model: str = "anthropic/claude-3.7-sonnet"):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.default_model = default_model

    def is_available(self) -> bool:
        return bool(self.api_key) or shutil.which("opencode") is not None

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        start_time = time.time()
        target_model = model or self.default_model

        if self.api_key:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": target_model,
                "messages": messages,
            }

            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/Morrison-Lab/ai-config",
                        "X-Title": "ai-config orchestrator",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    return ModelResponse(
                        success=True,
                        content=content,
                        model_used=target_model,
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                        raw_output=data,
                    )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=f"OpenRouter API error: {str(exc)}",
                )

        # Fallback via opencode openrouter provider
        if shutil.which("opencode"):
            cmd = ["opencode", "run", "-m", f"openrouter/{target_model}", prompt]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
                if proc.returncode == 0:
                    return ModelResponse(
                        success=True,
                        content=proc.stdout.strip(),
                        model_used=f"openrouter/{target_model}",
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                    )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=str(exc),
                )

        return ModelResponse(
            success=False,
            content="",
            model_used=target_model,
            provider=self.provider,
            execution_time_seconds=0.0,
            error="No OpenRouter API key configured and opencode fallback unavailable.",
        )


class ClaudeAdapter(BaseModelAdapter):
    """Claude Code CLI / API adapter."""

    provider = ModelProvider.CLAUDE

    def __init__(self, default_model: str = "claude-3-7-sonnet"):
        self.default_model = default_model

    def is_available(self) -> bool:
        return shutil.which("claude") is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 180,
    ) -> ModelResponse:
        start_time = time.time()
        target_model = model or self.default_model

        if shutil.which("claude"):
            cmd = ["claude", "-p", prompt]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
                if proc.returncode == 0:
                    return ModelResponse(
                        success=True,
                        content=proc.stdout.strip(),
                        model_used=target_model,
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                    )
                return ModelResponse(
                    success=False,
                    content=proc.stdout,
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=proc.stderr.strip() or f"claude exited with code {proc.returncode}",
                )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=f"claude invocation failed: {str(exc)}",
                )

        return ModelResponse(
            success=False,
            content="",
            model_used=target_model,
            provider=self.provider,
            execution_time_seconds=0.0,
            error="claude CLI executable or API credentials not available.",
        )


class AgyAdapter(BaseModelAdapter):
    """Gemini CLI / Google Antigravity adapter."""

    provider = ModelProvider.AGY

    def __init__(self, default_model: str = "gemini-2.5-pro"):
        self.default_model = default_model

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None or bool(os.environ.get("GEMINI_API_KEY"))

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        start_time = time.time()
        target_model = model or self.default_model

        if shutil.which("gemini"):
            cmd = ["gemini", "-p", prompt]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
                if proc.returncode == 0:
                    return ModelResponse(
                        success=True,
                        content=proc.stdout.strip(),
                        model_used=target_model,
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                    )
                return ModelResponse(
                    success=False,
                    content=proc.stdout,
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=proc.stderr.strip() or f"gemini exited with code {proc.returncode}",
                )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=f"gemini CLI invocation failed: {str(exc)}",
                )

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
            }
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return ModelResponse(
                        success=True,
                        content=content.strip(),
                        model_used=target_model,
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                    )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=f"Gemini API request failed: {str(exc)}",
                )

        return ModelResponse(
            success=False,
            content="",
            model_used=target_model,
            provider=self.provider,
            execution_time_seconds=0.0,
            error="Gemini CLI executable or GEMINI_API_KEY not configured.",
        )


class CodexAdapter(BaseModelAdapter):
    """OpenAI Codex / CLI adapter."""

    provider = ModelProvider.CODEX

    def __init__(self, default_model: str = "o3-mini"):
        self.default_model = default_model

    def is_available(self) -> bool:
        return shutil.which("codex") is not None or bool(os.environ.get("OPENAI_API_KEY"))

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        start_time = time.time()
        target_model = model or self.default_model

        if shutil.which("codex"):
            cmd = ["codex", "exec", prompt]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
                if proc.returncode == 0:
                    return ModelResponse(
                        success=True,
                        content=proc.stdout.strip(),
                        model_used=target_model,
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                    )
                return ModelResponse(
                    success=False,
                    content=proc.stdout,
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=proc.stderr.strip() or f"codex exited with code {proc.returncode}",
                )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=f"codex invocation failed: {str(exc)}",
                )

        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            url = "https://api.openai.com/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": target_model,
                "messages": messages,
            }
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return ModelResponse(
                        success=True,
                        content=content.strip(),
                        model_used=target_model,
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                    )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=f"OpenAI API request failed: {str(exc)}",
                )

        return ModelResponse(
            success=False,
            content="",
            model_used=target_model,
            provider=self.provider,
            execution_time_seconds=0.0,
            error="Codex CLI or OPENAI_API_KEY not configured.",
        )


class CursorAdapter(BaseModelAdapter):
    """Cursor CLI / Background Agent adapter."""

    provider = ModelProvider.CURSOR

    def __init__(self, default_model: str = "cursor-agent"):
        self.default_model = default_model

    def is_available(self) -> bool:
        return shutil.which("cursor") is not None

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        start_time = time.time()
        target_model = model or self.default_model

        if shutil.which("cursor"):
            cmd = ["cursor", "--agent", prompt]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
                if proc.returncode == 0:
                    return ModelResponse(
                        success=True,
                        content=proc.stdout.strip(),
                        model_used=target_model,
                        provider=self.provider,
                        execution_time_seconds=time.time() - start_time,
                    )
                return ModelResponse(
                    success=False,
                    content=proc.stdout,
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=proc.stderr.strip() or f"cursor exited with code {proc.returncode}",
                )
            except Exception as exc:
                return ModelResponse(
                    success=False,
                    content="",
                    model_used=target_model,
                    provider=self.provider,
                    execution_time_seconds=time.time() - start_time,
                    error=f"cursor CLI invocation failed: {str(exc)}",
                )

        return ModelResponse(
            success=False,
            content="",
            model_used=target_model,
            provider=self.provider,
            execution_time_seconds=0.0,
            error="Cursor CLI executable not available on PATH.",
        )


class MockAdapter(BaseModelAdapter):
    """Deterministic mock adapter for testing and simulation."""

    provider = ModelProvider.MOCK

    def is_available(self) -> bool:
        return True

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 10,
    ) -> ModelResponse:
        start_time = time.time()
        return ModelResponse(
            success=True,
            content=f"Mock response for prompt: {prompt[:80]}",
            model_used=model or "mock-v1",
            provider=self.provider,
            execution_time_seconds=time.time() - start_time,
        )


class ModelRouter:
    """Intelligently routes tasks to the optimal model and provider based on task tier,

    cost, confidentiality, and adversarial review independence constraints.
    """

    def __init__(self):
        self.adapters: Dict[ModelProvider, BaseModelAdapter] = {
            ModelProvider.OLLAMA: OllamaAdapter(),
            ModelProvider.OPENCODE: OpencodeAdapter(),
            ModelProvider.OPENROUTER: OpenRouterAdapter(),
            ModelProvider.CLAUDE: ClaudeAdapter(),
            ModelProvider.AGY: AgyAdapter(),
            ModelProvider.CODEX: CodexAdapter(),
            ModelProvider.CURSOR: CursorAdapter(),
            ModelProvider.MOCK: MockAdapter(),
        }

    def register_adapter(self, provider: ModelProvider, adapter: BaseModelAdapter) -> None:
        self.adapters[provider] = adapter

    def get_adapter(self, provider: ModelProvider) -> BaseModelAdapter:
        return self.adapters.get(provider, self.adapters[ModelProvider.MOCK])

    def route_task(
        self,
        tier: TaskTier,
        is_confidential: bool = False,
        prior_author_model: Optional[str] = None,
    ) -> tuple[BaseModelAdapter, str]:
        """Select best available adapter and model string for a given task requirement,

        prioritizing free and local models where feasible.
        """
        # 1. Strict local confidentiality -> Ollama local model only
        if is_confidential:
            ollama = self.adapters[ModelProvider.OLLAMA]
            if ollama.is_available():
                return ollama, "qwen2.5-coder:7b"
            # Fallback to mock if offline
            return self.adapters[ModelProvider.MOCK], "local-mock"

        # 2. Adversarial Review -> Must use a different model family than author,
        # preferring local/free reviewers first while strictly preventing same-family self-review.
        if tier == TaskTier.ADVERSARIAL_REVIEW:
            author = (prior_author_model or "").lower()

            if "claude" in author:
                # Must not use Claude for review
                if self.adapters[ModelProvider.OLLAMA].is_available():
                    return self.adapters[ModelProvider.OLLAMA], "deepseek-r1:8b"
                if self.adapters[ModelProvider.OPENCODE].is_available():
                    return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"
                if self.adapters[ModelProvider.OPENROUTER].is_available():
                    return self.adapters[ModelProvider.OPENROUTER], "deepseek/deepseek-r1"
                if self.adapters[ModelProvider.AGY].is_available():
                    return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
                return self.adapters[ModelProvider.MOCK], "independent-reviewer-mock"

            if "opencode" in author:
                # Must not use Opencode for review
                if self.adapters[ModelProvider.OLLAMA].is_available():
                    return self.adapters[ModelProvider.OLLAMA], "deepseek-r1:8b"
                if self.adapters[ModelProvider.CLAUDE].is_available():
                    return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"
                if self.adapters[ModelProvider.OPENROUTER].is_available():
                    return self.adapters[ModelProvider.OPENROUTER], "anthropic/claude-3.7-sonnet"
                if self.adapters[ModelProvider.AGY].is_available():
                    return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
                return self.adapters[ModelProvider.MOCK], "independent-reviewer-mock"

            if "deepseek" in author:
                # Must not use DeepSeek family for review (neither Ollama deepseek nor Opencode deepseek)
                if self.adapters[ModelProvider.CLAUDE].is_available():
                    return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"
                if self.adapters[ModelProvider.AGY].is_available():
                    return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
                if self.adapters[ModelProvider.OPENROUTER].is_available():
                    return self.adapters[ModelProvider.OPENROUTER], "anthropic/claude-3.7-sonnet"
                if self.adapters[ModelProvider.OLLAMA].is_available():
                    return self.adapters[ModelProvider.OLLAMA], "qwen2.5-coder:7b"
                return self.adapters[ModelProvider.MOCK], "independent-reviewer-mock"

            if "ollama" in author or "qwen" in author:
                # Must not use Ollama/Qwen for review
                if self.adapters[ModelProvider.OPENCODE].is_available():
                    return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"
                if self.adapters[ModelProvider.CLAUDE].is_available():
                    return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"
                if self.adapters[ModelProvider.OPENROUTER].is_available():
                    return self.adapters[ModelProvider.OPENROUTER], "anthropic/claude-3.7-sonnet"
                if self.adapters[ModelProvider.AGY].is_available():
                    return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
                return self.adapters[ModelProvider.MOCK], "independent-reviewer-mock"

            if "cursor" in author:
                # Must not use Cursor for review
                if self.adapters[ModelProvider.OLLAMA].is_available():
                    return self.adapters[ModelProvider.OLLAMA], "deepseek-r1:8b"
                if self.adapters[ModelProvider.OPENCODE].is_available():
                    return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"
                if self.adapters[ModelProvider.CLAUDE].is_available():
                    return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"
                if self.adapters[ModelProvider.OPENROUTER].is_available():
                    return self.adapters[ModelProvider.OPENROUTER], "anthropic/claude-3.7-sonnet"
                if self.adapters[ModelProvider.AGY].is_available():
                    return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
                return self.adapters[ModelProvider.MOCK], "independent-reviewer-mock"

            if "codex" in author:
                # Must not use Codex for review
                if self.adapters[ModelProvider.OLLAMA].is_available():
                    return self.adapters[ModelProvider.OLLAMA], "deepseek-r1:8b"
                if self.adapters[ModelProvider.OPENCODE].is_available():
                    return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"
                if self.adapters[ModelProvider.CLAUDE].is_available():
                    return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"
                if self.adapters[ModelProvider.OPENROUTER].is_available():
                    return self.adapters[ModelProvider.OPENROUTER], "anthropic/claude-3.7-sonnet"
                if self.adapters[ModelProvider.AGY].is_available():
                    return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
                return self.adapters[ModelProvider.MOCK], "independent-reviewer-mock"

            # Default: use local/free reviewer if available, else Claude/OpenRouter, with terminal MOCK fallback
            if self.adapters[ModelProvider.OLLAMA].is_available():
                return self.adapters[ModelProvider.OLLAMA], "deepseek-r1:8b"
            if self.adapters[ModelProvider.OPENCODE].is_available():
                return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"
            if self.adapters[ModelProvider.CLAUDE].is_available():
                return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"
            if self.adapters[ModelProvider.OPENROUTER].is_available():
                return self.adapters[ModelProvider.OPENROUTER], "anthropic/claude-3.7-sonnet"
            if self.adapters[ModelProvider.AGY].is_available():
                return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
            return self.adapters[ModelProvider.MOCK], "independent-reviewer-mock"

        # 3. Local Fast (bounded checks, formatting, link checks) -> Local Ollama / Free
        if tier == TaskTier.LOCAL_FAST:
            if self.adapters[ModelProvider.OLLAMA].is_available():
                return self.adapters[ModelProvider.OLLAMA], "qwen2.5-coder:7b"
            if self.adapters[ModelProvider.OPENCODE].is_available():
                return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"

        # 4. Free Hosted (survey, triage, broad sweep) -> Opencode free / Ollama
        if tier == TaskTier.FREE_HOSTED:
            if self.adapters[ModelProvider.OPENCODE].is_available():
                return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"
            if self.adapters[ModelProvider.OLLAMA].is_available():
                return self.adapters[ModelProvider.OLLAMA], "qwen2.5-coder:7b"
            if self.adapters[ModelProvider.OPENROUTER].is_available():
                return self.adapters[ModelProvider.OPENROUTER], "openrouter/free"

        # 5. Frontier / Heavy (architecture, deep logic, coordination) -> Frontier models
        if tier == TaskTier.FRONTIER_HEAVY:
            if self.adapters[ModelProvider.CLAUDE].is_available():
                return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"
            if self.adapters[ModelProvider.AGY].is_available():
                return self.adapters[ModelProvider.AGY], "gemini-2.5-pro"
            if self.adapters[ModelProvider.OPENROUTER].is_available():
                return self.adapters[ModelProvider.OPENROUTER], "anthropic/claude-3.7-sonnet"

        # 6. Standard Code Tasks -> Prioritize local zero-cost Ollama, then free pools, then Claude CLI
        if self.adapters[ModelProvider.OLLAMA].is_available():
            return self.adapters[ModelProvider.OLLAMA], "qwen2.5-coder:7b"
        if self.adapters[ModelProvider.OPENCODE].is_available():
            return self.adapters[ModelProvider.OPENCODE], "opencode/deepseek-v4-flash-free"
        if self.adapters[ModelProvider.CURSOR].is_available():
            return self.adapters[ModelProvider.CURSOR], "cursor-agent"
        if self.adapters[ModelProvider.CLAUDE].is_available():
            return self.adapters[ModelProvider.CLAUDE], "claude-3-7-sonnet"

        return self.adapters[ModelProvider.MOCK], "mock-standard"
