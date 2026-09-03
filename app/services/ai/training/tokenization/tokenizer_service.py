import hashlib
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai.training.schemas import (
    SftConversationExample,
    SftMessage,
    TokenizationStats,
    TokenizedSample,
)
from app.services.ai.training.tokenization.tokenization_config import (
    ExecutionMode,
    TokenizationConfig,
)

logger = logging.getLogger(__name__)

# Memory cache for loaded HuggingFace AutoTokenizers
_TOKENIZER_CACHE: Dict[str, Any] = {}


class TokenizerService:
    """
    Milestone A9.1: Tokenization & Formatting Engine for SFT Training.
    Supports real HuggingFace AutoTokenizer integration with native chat templates,
    explicit execution mode gating (CPU_TEST vs REAL_TRAINING), prompt label masking (-100),
    pedagogical target truncation protection, and deterministic SHA-256 test pseudo-encoding.
    """

    IGNORE_INDEX = -100

    @classmethod
    def get_hf_tokenizer(cls, model_name_or_path: str, strict_mode: bool = False) -> Optional[Any]:
        """
        Loads and caches a real HuggingFace AutoTokenizer.
        In REAL_TRAINING (strict_mode=True), raises RuntimeError immediately if loading fails.
        """
        if model_name_or_path in _TOKENIZER_CACHE:
            return _TOKENIZER_CACHE[model_name_or_path]

        try:
            from transformers import AutoTokenizer  # type: ignore

            tokenizer = AutoTokenizer.from_pretrained(
                model_name_or_path,
                trust_remote_code=True,
                use_fast=True,
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token or "<|endoftext|>"
            _TOKENIZER_CACHE[model_name_or_path] = tokenizer
            logger.info(f"Loaded real HuggingFace tokenizer for '{model_name_or_path}'.")
            return tokenizer
        except Exception as e:
            if strict_mode:
                raise RuntimeError(
                    f"Real HuggingFace AutoTokenizer is strictly required in REAL_TRAINING mode for "
                    f"model '{model_name_or_path}'. Failed to load: {e}"
                )
            logger.debug(
                f"HuggingFace AutoTokenizer for '{model_name_or_path}' not loaded in CPU_TEST mode ({e}). "
                f"Using deterministic SHA-256 CPU test encoder."
            )
            return None

    @classmethod
    def apply_chat_template(
        cls,
        messages: List[SftMessage],
        chat_template_format: str = "chatml",
        add_generation_prompt: bool = False,
        hf_tokenizer: Optional[Any] = None,
    ) -> str:
        """
        Renders an ordered list of SftMessages into text.
        If a real HuggingFace tokenizer with native chat template is available, uses it.
        Otherwise falls back to standard ChatML / Llama-3 formatting.
        """
        if hf_tokenizer is not None and hasattr(hf_tokenizer, "apply_chat_template"):
            try:
                dict_messages = [{"role": m.role, "content": m.content} for m in messages]
                rendered = hf_tokenizer.apply_chat_template(
                    dict_messages,
                    tokenize=False,
                    add_generation_prompt=add_generation_prompt,
                )
                return rendered
            except Exception as e:
                logger.debug(
                    f"Native tokenizer apply_chat_template fallback to manual formatting: {e}"
                )

        fmt = (chat_template_format or "chatml").lower()

        if fmt == "chatml":
            rendered = []
            for msg in messages:
                rendered.append(f"<|im_start|>{msg.role}\n{msg.content}<|im_end|>")
            if add_generation_prompt:
                rendered.append("<|im_start|>assistant\n")
            return "\n".join(rendered)

        elif fmt in ["llama3", "llama-3"]:
            rendered = ["<|begin_of_text|>"]
            for msg in messages:
                rendered.append(
                    f"<|start_header_id|>{msg.role}<|end_header_id|>\n\n{msg.content}<|eot_id|>"
                )
            if add_generation_prompt:
                rendered.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
            return "".join(rendered)

        else:
            rendered = []
            for msg in messages:
                role_title = msg.role.upper()
                rendered.append(f"### {role_title}\n{msg.content}")
            return "\n\n".join(rendered)

    @classmethod
    def _deterministic_sha256_token_id(cls, token_str: str) -> int:
        """
        Computes a stable, cross-process deterministic integer token ID (100..99999)
        using SHA-256 hashing. Used exclusively for CPU offline unit testing.
        """
        h = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
        return int(h[:8], 16) % 99000 + 100

    @classmethod
    def _mock_cpu_encode(cls, text: str) -> List[int]:
        """
        Deterministic SHA-256 pseudo-tokenizer for CPU/offline testing.
        Preserves special ChatML/Llama header tokens.
        """
        special_token_map = {
            "<|im_start|>system": 100010,
            "<|im_start|>user": 100011,
            "<|im_start|>assistant": 100012,
            "<|im_end|>": 100002,
            "<|begin_of_text|>": 100000,
            "<|start_header_id|>": 100020,
            "<|end_header_id|>": 100021,
            "<|eot_id|>": 100022,
        }

        token_pattern = re.compile(
            r"(<\|[^|>]+(?:system|user|assistant|start|end|eot|begin)[^|>]*\|>|[\w']+|[^\w\s])",
            re.UNICODE,
        )

        tokens = token_pattern.findall(text)
        token_ids: List[int] = []

        for t in tokens:
            if t in special_token_map:
                token_ids.append(special_token_map[t])
            else:
                token_ids.append(cls._deterministic_sha256_token_id(t))

        return token_ids

    @classmethod
    def encode_text(cls, text: str, config: TokenizationConfig) -> Tuple[List[int], bool]:
        """
        Encodes raw text into token IDs.
        In REAL_TRAINING mode, strictly enforces real HuggingFace tokenizer.
        In CPU_TEST mode, falls back to deterministic SHA-256 test pseudo-encoding.
        Returns (token_ids, is_real_tokenizer_used).
        """
        is_real_mode = config.execution_mode == ExecutionMode.REAL_TRAINING

        if is_real_mode:
            hf_tok = cls.get_hf_tokenizer(config.model_name_or_path, strict_mode=True)
            encoded = hf_tok.encode(text, add_special_tokens=False)
            return encoded, True

        # CPU_TEST mode: attempt HF if requested, otherwise mock
        if config.use_real_tokenizer:
            hf_tok = cls.get_hf_tokenizer(config.model_name_or_path, strict_mode=False)
            if hf_tok is not None:
                encoded = hf_tok.encode(text, add_special_tokens=False)
                return encoded, True

        return cls._mock_cpu_encode(text), False

    @classmethod
    def tokenize_conversation(
        cls, example: SftConversationExample, config: Optional[TokenizationConfig] = None
    ) -> TokenizedSample:
        """
        Tokenizes an SftConversationExample with prompt label masking (-100) and
        strict assistant ground-truth target truncation tracking.
        """
        if config is None:
            config = TokenizationConfig()

        is_real_mode = config.execution_mode == ExecutionMode.REAL_TRAINING
        hf_tok = cls.get_hf_tokenizer(config.model_name_or_path, strict_mode=is_real_mode)

        prompt_messages = [m for m in example.messages if m.role in ("system", "user")]
        assistant_messages = [m for m in example.messages if m.role == "assistant"]

        prompt_text = cls.apply_chat_template(
            prompt_messages,
            chat_template_format=config.chat_template_format,
            add_generation_prompt=True,
            hf_tokenizer=hf_tok,
        )
        assistant_text = ""
        if assistant_messages:
            if config.chat_template_format == "chatml":
                assistant_text = f"{assistant_messages[0].content}<|im_end|>"
            elif config.chat_template_format in ["llama3", "llama-3"]:
                assistant_text = f"{assistant_messages[0].content}<|eot_id|>"
            else:
                assistant_text = assistant_messages[0].content

        prompt_ids, _ = cls.encode_text(prompt_text, config)
        assistant_ids, _ = cls.encode_text(assistant_text, config)

        len_p = len(prompt_ids)
        len_a = len(assistant_ids)
        full_input_ids = prompt_ids + assistant_ids
        total_len = len(full_input_ids)

        is_truncated = total_len > config.max_seq_length
        target_is_truncated = False

        if is_truncated:
            if config.truncation_strategy == "prompt_first":
                # Prioritize protecting teacher ground truth: preserve entire assistant target if possible
                if len_a > config.max_seq_length:
                    # Assistant target itself exceeds maximum context window
                    target_is_truncated = True
                    full_input_ids = assistant_ids[: config.max_seq_length]
                    attention_mask = [1] * len(full_input_ids)
                    labels = list(full_input_ids)
                else:
                    target_is_truncated = False
                    keep_prompt_len = config.max_seq_length - len_a
                    truncated_prompt_ids = (
                        prompt_ids[-keep_prompt_len:] if keep_prompt_len > 0 else []
                    )
                    full_input_ids = truncated_prompt_ids + assistant_ids
                    attention_mask = [1] * len(full_input_ids)
                    if config.mask_prompt_labels:
                        labels = [cls.IGNORE_INDEX] * len(truncated_prompt_ids) + list(
                            assistant_ids
                        )
                    else:
                        labels = list(full_input_ids)

                return TokenizedSample(
                    input_ids=full_input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                    token_length=total_len,
                    is_truncated=is_truncated,
                    target_is_truncated=target_is_truncated,
                )

            # Strict cut mode (raw slicing)
            if config.truncation_side == "right":
                # Right cut removes tokens from the end (assistant response)
                target_is_truncated = len_p + len_a > config.max_seq_length
                full_input_ids = full_input_ids[: config.max_seq_length]
            else:
                # Left cut removes tokens from the beginning (prompt).
                # If prompt is completely removed and cut reaches into assistant tokens:
                target_is_truncated = len_a > config.max_seq_length
                full_input_ids = full_input_ids[-config.max_seq_length :]

        attention_mask = [1] * len(full_input_ids)

        # Label computation
        if config.mask_prompt_labels:
            if is_truncated and config.truncation_side == "right":
                remaining_prompt_len = min(len_p, len(full_input_ids))
                remaining_assistant_len = max(0, len(full_input_ids) - remaining_prompt_len)
                labels = [cls.IGNORE_INDEX] * remaining_prompt_len + list(
                    full_input_ids[remaining_prompt_len:]
                )
            elif is_truncated and config.truncation_side == "left":
                dropped_prompt_len = total_len - config.max_seq_length
                remaining_prompt_len = max(0, len_p - dropped_prompt_len)
                labels = [cls.IGNORE_INDEX] * remaining_prompt_len + list(
                    full_input_ids[remaining_prompt_len:]
                )
            else:
                labels = [cls.IGNORE_INDEX] * len_p + list(assistant_ids)
        else:
            labels = list(full_input_ids)

        return TokenizedSample(
            input_ids=full_input_ids,
            attention_mask=attention_mask,
            labels=labels,
            token_length=total_len,
            is_truncated=is_truncated,
            target_is_truncated=target_is_truncated,
        )

    @classmethod
    def compute_tokenization_stats(
        cls,
        examples: List[SftConversationExample],
        config: Optional[TokenizationConfig] = None,
    ) -> TokenizationStats:
        """
        Computes comprehensive token length distribution statistics across a set of examples.
        """
        if config is None:
            config = TokenizationConfig()

        if not examples:
            return TokenizationStats(
                total_samples=0,
                total_tokens=0,
                avg_tokens_per_sample=0.0,
                min_tokens=0,
                max_tokens=0,
                p95_tokens=0.0,
                truncated_samples_count=0,
                target_truncated_count=0,
                truncation_rate_pct=0.0,
            )

        lengths = []
        truncated_count = 0
        target_truncated_count = 0

        for ex in examples:
            sample = cls.tokenize_conversation(ex, config)
            lengths.append(sample.token_length)
            if sample.is_truncated:
                truncated_count += 1
            if sample.target_is_truncated:
                target_truncated_count += 1

        total_samples = len(lengths)
        total_tokens = sum(lengths)
        avg_tokens = round(total_tokens / total_samples, 2)
        min_tokens = min(lengths)
        max_tokens = max(lengths)

        sorted_lengths = sorted(lengths)
        p95_idx = min(total_samples - 1, math.ceil(0.95 * total_samples) - 1)
        p95_tokens = float(sorted_lengths[p95_idx])

        truncation_rate = round((truncated_count / total_samples) * 100.0, 2)

        return TokenizationStats(
            total_samples=total_samples,
            total_tokens=total_tokens,
            avg_tokens_per_sample=avg_tokens,
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            p95_tokens=p95_tokens,
            truncated_samples_count=truncated_count,
            target_truncated_count=target_truncated_count,
            truncation_rate_pct=truncation_rate,
        )
