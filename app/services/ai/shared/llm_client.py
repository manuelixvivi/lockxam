import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Set

from app.services.ai.shared.config import AiConfig

logger = logging.getLogger(__name__)


class LlmClient:
    """
    Unified LLM Client abstraction for EquiGrade.
    Handles JSON normalization, markdown stripping, rate-limit retry with backoff,
    model availability checks, and transparent fallback between direct Groq API
    and equigradeAI microservice.
    """

    _model_cache: Dict[str, Any] = {
        "models": set(),
        "last_checked": 0.0,
        "ttl_seconds": 900.0,  # 15 minutes cache
    }

    @classmethod
    def get_live_models(cls, api_key: Optional[str] = None) -> Set[str]:
        """Queries Groq /models endpoint to discover active production models (cached 15m)."""
        effective_key = AiConfig.get_effective_api_key(api_key)
        if not effective_key:
            return set()

        now = time.time()
        if (
            cls._model_cache["models"]
            and (now - cls._model_cache["last_checked"]) < cls._model_cache["ttl_seconds"]
        ):
            return cls._model_cache["models"]

        url = f"{AiConfig.GROQ_BASE_URL.rstrip('/')}/models"
        headers = {
            "Authorization": f"Bearer {effective_key}",
            "User-Agent": "EquiGrade-AI-Engine/2.0",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                active_models = {
                    item["id"]
                    for item in data.get("data", [])
                    if isinstance(item, dict) and item.get("active", True)
                }
                cls._model_cache["models"] = active_models
                cls._model_cache["last_checked"] = now
                return active_models
        except Exception as e:
            logger.warning(f"Failed to fetch live models from Groq /models: {e}")
            return cls._model_cache["models"]

    @classmethod
    def check_live_model_availability(
        cls, model_name: Optional[str] = None, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Checks if a specified model is active and available on Groq."""
        target = model_name or AiConfig.MODEL_NAME
        effective_key = AiConfig.get_effective_api_key(api_key)

        if not effective_key:
            return {
                "available": True,  # Assume offline / dev mock mode
                "model": target,
                "mode": "offline_configured",
            }

        live_models = cls.get_live_models(effective_key)
        if not live_models:
            # Fallback if models API could not be queried
            return {
                "available": True,
                "model": target,
                "mode": "unverified_network",
            }

        is_available = target in live_models
        fallback_available = AiConfig.GROQ_FALLBACK_MODEL in live_models

        return {
            "available": is_available,
            "model": target,
            "fallback_model": AiConfig.GROQ_FALLBACK_MODEL,
            "fallback_available": fallback_available,
            "status": (
                "READY"
                if is_available
                else ("FALLBACK_READY" if fallback_available else "MODEL_UNAVAILABLE")
            ),
        }

    @classmethod
    def call_chat_completion(
        cls,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: int = 25,
        max_retries: int = 2,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes chat completion with JSON normalization, rate-limit exponential backoff,
        and fallback model routing.
        """
        effective_key = AiConfig.get_effective_api_key(api_key)
        target_model = model or AiConfig.get_effective_model()
        if target_model.startswith("openai/gpt-oss"):
            target_model = "llama-3.3-70b-versatile"

        direct_error = None
        if effective_key:
            url = f"{AiConfig.GROQ_BASE_URL.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {effective_key}",
                "User-Agent": "EquiGrade-AI-Engine/2.0",
            }

            sys_content = system_prompt
            if "json" not in (sys_content + user_prompt).lower():
                sys_content = f"{sys_content}\nRespond strictly in valid JSON format."

            for attempt in range(max_retries):
                payload = {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": sys_content},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                }
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        resp_json = json.loads(resp.read().decode("utf-8"))
                        raw_content = resp_json["choices"][0]["message"]["content"].strip()
                        parsed = cls.clean_and_parse_json(raw_content)
                        if not parsed or not isinstance(parsed, dict):
                            raise ValueError(
                                f"Empty or non-dictionary JSON from LLM: {raw_content[:100]}"
                            )
                        return {
                            "status": "success",
                            "data": parsed,
                            "raw": raw_content,
                            "model": target_model,
                            "usage": resp_json.get("usage", {}),
                        }
                except urllib.error.HTTPError as he:
                    error_body = he.read().decode("utf-8", errors="ignore")

                    # Handle 429 Rate Limit with Retry-After or exponential backoff
                    if he.code == 429:
                        retry_after = he.headers.get("Retry-After")
                        sleep_time = (
                            float(retry_after)
                            if retry_after and retry_after.isdigit()
                            else (2**attempt + 1.0)
                        )
                        logger.warning(
                            f"Rate limit 429 encountered on model '{target_model}'. Retrying in {sleep_time:.1f}s (attempt {attempt+1}/{max_retries})..."
                        )
                        if attempt < max_retries - 1:
                            time.sleep(sleep_time)
                            continue
                        direct_error = (
                            f"Rate limit exceeded (429) after {max_retries} retries: {error_body}"
                        )
                        break

                    # Handle 404 Model Not Found / Deprecated -> Attempt Fallback Model
                    if he.code == 404 and target_model != AiConfig.GROQ_FALLBACK_MODEL:
                        logger.warning(
                            f"Model '{target_model}' not found (404 / deprecated). Switching to fallback model '{AiConfig.GROQ_FALLBACK_MODEL}'..."
                        )
                        target_model = AiConfig.GROQ_FALLBACK_MODEL
                        continue

                    # Handle 401 / 403 Authentication / Permission Error
                    if he.code in (401, 403):
                        logger.error(f"Authentication error ({he.code}) on AI engine: {error_body}")
                        direct_error = f"Groq API Authentication Error ({he.code}): {error_body}"
                        break

                    # Handle 5xx Provider Server Error
                    if he.code >= 500:
                        logger.warning(
                            f"Upstream provider error ({he.code}). Retrying attempt {attempt+1}..."
                        )
                        if attempt < max_retries - 1:
                            time.sleep(2**attempt)
                            continue

                    logger.error(f"Direct LLM HTTP Error {he.code}: {error_body}")
                    direct_error = f"LLM Chat Completion error ({he.code}): {error_body}"
                    break

                except Exception as e:
                    logger.warning(
                        f"Direct LLM call failed ({e}), attempting microservice bridge fallback..."
                    )
                    direct_error = str(e)
                    break

        # Fallback to microservice if direct key is absent or failed
        fallback_res = cls._call_microservice_fallback(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=target_model,
            api_key=effective_key,
            timeout=timeout,
            extra_payload=extra_payload,
        )
        if fallback_res.get("status") == "success" and fallback_res.get("data"):
            return fallback_res

        # If both direct API and microservice fallback fail, fail closed with explicit exception
        err_msg = direct_error or fallback_res.get("error") or "All AI inference providers failed."
        logger.error(f"AI Inference failure: {err_msg}")
        raise RuntimeError(f"AI Inference Service Failure: {err_msg}")

    @classmethod
    def _call_microservice_fallback(
        cls,
        system_prompt: str,
        user_prompt: str,
        model: str,
        api_key: str,
        timeout: int,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Microservice HTTP bridge fallback."""
        url = f"{AiConfig.EQUIGRADE_AI_URL.rstrip('/')}/api/v1/ai/essay/grade"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "User-Agent": "EquiGrade-AI-Engine/2.0",
        }
        body = {
            "question_text": user_prompt,
            "student_answer": user_prompt,
            "rag_context": "",
        }
        if extra_payload:
            body.update(extra_payload)

        data_bytes = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_bytes = resp.read()
                if resp_bytes:
                    resp_data = json.loads(resp_bytes.decode("utf-8"))
                    if isinstance(resp_data, dict) and resp_data:
                        return {
                            "status": "success",
                            "data": resp_data,
                            "raw": json.dumps(resp_data),
                            "model": model,
                            "usage": {},
                        }
        except Exception as e:
            logger.warning(f"Microservice HTTP bridge error: {e}")
            return {
                "status": "error",
                "error": f"Microservice HTTP bridge failed: {e}",
                "data": None,
                "raw": "",
                "model": model,
                "usage": {},
            }

        return {
            "status": "error",
            "error": "Microservice returned empty response",
            "data": None,
            "raw": "",
            "model": model,
            "usage": {},
        }

    @classmethod
    def clean_and_parse_json(cls, raw_text: str) -> Dict[str, Any]:
        """Extracts and parses clean JSON from potentially messy or markdown-wrapped LLM text."""
        cleaned = raw_text.strip()
        # Strip markdown fences ```json ... ``` or ``` ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt to extract first complete JSON object
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"LLM did not return valid JSON output: {raw_text[:100]}") from None

    @classmethod
    def check_health(cls) -> Dict[str, Any]:
        """Checks overall AI engine and live model availability."""
        has_key = bool(AiConfig.GROQ_API_KEY)
        model_status = cls.check_live_model_availability(AiConfig.EVAL_MODEL_NAME)

        return {
            "status": "online" if has_key else "configured_offline",
            "engine": "EquiGrade-AI-Engine",
            "model": AiConfig.MODEL_NAME,
            "eval_model": AiConfig.EVAL_MODEL_NAME,
            "fallback_model": AiConfig.GROQ_FALLBACK_MODEL,
            "validation_model": AiConfig.VALIDATION_MODEL_NAME,
            "model_readiness": model_status.get("status", "READY"),
            "rag_enabled_default": AiConfig.is_rag_enabled(),
            "direct_api_configured": has_key,
        }
