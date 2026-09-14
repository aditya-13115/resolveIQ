"""
Reply generation for ResolveIQ 06_agent.

Single system prompt shared by ungrounded and grounded modes.

Only difference between the two modes is whether the user message
includes historical precedents.

Public API:
    SYSTEM_PROMPT
    REPLY_SCHEMA
    build_user_message(query, precedents=None)

    Generator(model, cache_path, cache=None)
        .generate(query, precedents=None) -> dict
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
from groq import Groq


# ---------------------------------------------------------------------
# Groq configuration
# ---------------------------------------------------------------------

STRICT_OUTPUT_MODELS = {
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
}


# ---------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------

SYSTEM_PROMPT = """You are a customer support assistant for GWRHelp (Great Western Railway).

Draft a concise, helpful reply to the customer's message.

Rules:

- Be polite, brief, and specific to the customer's ask.
- Do NOT invent policies, compensation amounts, eligibility rules,
  timelines, procedures, contact routes, or operational actions.
- If historical precedents are provided below the customer message,
  use them as grounding evidence for any operational claims.
  Prefer phrasing supported by the precedents over generic phrasing.
- If you cannot answer from the information available, acknowledge
  the ask and direct the customer to the appropriate channel.
- Cite which precedent ranks you used (1-indexed) in the
  `used_precedent_ranks` field. Do not put citation markers in the
  reply text itself.
- Return strict JSON matching the required schema.

JSON schema:

{
  "reply": string,
  "used_precedent_ranks": array of integers,
  "grounded": boolean,
  "confidence": number in [0, 1]
}
"""


REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string"
        },
        "used_precedent_ranks": {
            "type": "array",
            "items": {
                "type": "integer"
            }
        },
        "grounded": {
            "type": "boolean"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
    },
    "required": [
        "reply",
        "used_precedent_ranks",
        "grounded",
        "confidence",
    ],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------
# User message construction
# ---------------------------------------------------------------------

def build_user_message(
    query: str,
    precedents: Optional[list] = None,
) -> str:
    """
    Build the user message.

    precedents=None or [] -> ungrounded mode.

    precedents=[dict, ...] -> grounded mode.
    Each precedent should contain:
        {
            "intent": str,
            "customer_text": str,
            "response_text": str
        }
    """

    if not precedents:
        return f"Customer message:\n{query}"

    lines = [
        f"Customer message:\n{query}",
        "",
        "Historical precedents (most relevant first):",
    ]

    for i, p in enumerate(precedents, start=1):
        intent = p.get("intent", "unknown")
        cust = str(p.get("customer_text", ""))
        resp = str(p.get("response_text", ""))

        lines.append(f"[{i}] (intent={intent})")
        lines.append(f"  Customer: {cust}")
        lines.append(f"  Brand:    {resp}")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Groq API key handling
# ---------------------------------------------------------------------

def _get_api_keys() -> list[str]:
    """
    Supports either:

        GROQ_API_KEY=key

    or multiple keys:

        GROQ_API_KEYS=key1,key2,key3
    """

    raw = (
        os.environ.get("GROQ_API_KEYS")
        or os.environ.get("GROQ_API_KEY")
        or ""
    )

    return [k.strip() for k in raw.split(",") if k.strip()]


# ---------------------------------------------------------------------
# Rotating Groq client
# ---------------------------------------------------------------------

class _RotatingGroqClient:
    """
    Groq client wrapper.

    If multiple API keys are supplied, rotate to the next key
    when a rate-limit (429) error occurs.
    """

    def __init__(self, keys: list[str]):
        if not keys:
            raise RuntimeError(
                "No GROQ_API_KEY(s) found. "
                "Set GROQ_API_KEY or GROQ_API_KEYS."
            )

        self._clients = [
            Groq(api_key=key)
            for key in keys
        ]

        self._idx = 0

    @property
    def kind(self) -> str:
        return "groq"

    def chat_completions_create(self, **kwargs):
        n = len(self._clients)
        last_err: Optional[Exception] = None

        # Try each key at most twice.
        for _ in range(n * 2):
            client = self._clients[self._idx]

            try:
                return client.chat.completions.create(**kwargs)

            except Exception as e:
                msg = str(e).lower()

                is_rate_limit = (
                    "429" in msg
                    or "rate_limit" in msg
                    or "rate limit" in msg
                )

                if not is_rate_limit:
                    raise

                last_err = e

                # Rotate to next API key.
                self._idx = (self._idx + 1) % n

                # Small delay before retry.
                time.sleep(
                    1.0 + float(np.random.uniform(0, 0.5))
                )

        raise RuntimeError(
            f"All Groq API keys exhausted: {last_err}"
        )


# ---------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------

class Generator:

    def __init__(
        self,
        model: str,
        cache_path: Path,
        cache: Optional[dict] = None,
    ):
        self.model = model
        self.cache_path = Path(cache_path)
        self.cache = cache if cache is not None else {}

        # Make sure cache directory exists.
        self.cache_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._client = _RotatingGroqClient(
            _get_api_keys()
        )

    # -----------------------------------------------------------------
    # Cache
    # -----------------------------------------------------------------

    def _cache_key(self, user_message: str) -> str:
        h = hashlib.sha256()

        h.update(self.model.encode("utf-8"))
        h.update(b"|")

        h.update(SYSTEM_PROMPT.encode("utf-8"))
        h.update(b"|")

        h.update(user_message.encode("utf-8"))
        h.update(b"|temperature=0|strict_schema_v1")

        return h.hexdigest()

    # -----------------------------------------------------------------
    # Groq call
    # -----------------------------------------------------------------

    def _call(self, user_message: str) -> dict:

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        # -------------------------------------------------------------
        # Strict structured output
        # -------------------------------------------------------------

        if self.model in STRICT_OUTPUT_MODELS:
            try:
                response = self._client.chat_completions_create(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "reply",
                            "strict": True,
                            "schema": REPLY_SCHEMA,
                        },
                    },
                )

                content = response.choices[0].message.content

                return json.loads(content)

            except Exception as e:
                print(
                    f"[gen] strict structured output failed: "
                    f"{type(e).__name__}: {e}"
                )

                print(
                    "[gen] Falling back to JSON object mode."
                )

        # -------------------------------------------------------------
        # JSON object fallback
        # -------------------------------------------------------------

        response = self._client.chat_completions_create(
            model=self.model,
            messages=messages,
            temperature=0,
            response_format={
                "type": "json_object"
            },
        )

        content = response.choices[0].message.content

        return json.loads(content)

    # -----------------------------------------------------------------
    # Normalize response
    # -----------------------------------------------------------------

    @staticmethod
    def _normalize(
        raw: dict,
        api_status: str = "ok",
    ) -> dict:

        reply = str(
            raw.get("reply", "")
        ).strip()

        ranks = raw.get(
            "used_precedent_ranks",
            [],
        )

        if not isinstance(ranks, list):
            ranks = []

        ranks_out = []

        for r in ranks:
            try:
                r_int = int(r)

                if r_int >= 1:
                    ranks_out.append(r_int)

            except (TypeError, ValueError):
                continue

        try:
            confidence = float(
                raw.get("confidence", 0.0)
            )

        except (TypeError, ValueError):
            confidence = 0.0

        confidence = min(
            max(confidence, 0.0),
            1.0,
        )

        return {
            "reply": reply,
            "used_precedent_ranks": ranks_out,
            "grounded": bool(
                raw.get("grounded", False)
            ),
            "confidence": confidence,
            "api_status": api_status,
        }

    # -----------------------------------------------------------------
    # Generate
    # -----------------------------------------------------------------

    def generate(
        self,
        query: str,
        precedents: Optional[list] = None,
        max_retries: int = 3,
    ) -> dict:

        user_message = build_user_message(
            query,
            precedents,
        )

        key = self._cache_key(
            user_message
        )

        # -------------------------------------------------------------
        # Cache hit
        # -------------------------------------------------------------

        if key in self.cache:
            return self.cache[key]

        # -------------------------------------------------------------
        # API call
        # -------------------------------------------------------------

        last_err: Optional[Exception] = None

        for attempt in range(max_retries):

            try:
                raw = self._call(
                    user_message
                )

                parsed = self._normalize(
                    raw,
                    api_status="ok",
                )

                # Cache in memory.
                self.cache[key] = parsed

                # Persist cache.
                with open(
                    self.cache_path,
                    "a",
                    encoding="utf-8",
                ) as f:

                    f.write(
                        json.dumps(
                            {
                                "key": key,
                                "model": self.model,
                                "user_message_sha": hashlib.sha256(
                                    user_message.encode("utf-8")
                                ).hexdigest(),
                                "response": parsed,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

                return parsed

            except Exception as e:

                last_err = e

                print(
                    f"[gen] attempt {attempt + 1}/{max_retries} "
                    f"failed: {type(e).__name__}: {e}"
                )

                if attempt < max_retries - 1:
                    time.sleep(
                        0.5 * (2 ** attempt)
                        + float(
                            np.random.uniform(0, 0.3)
                        )
                    )

        # -------------------------------------------------------------
        # Final fallback
        # -------------------------------------------------------------

        print(
            f"[gen] failed after {max_retries} retries: "
            f"{last_err}"
        )

        fallback = {
            "reply": "",
            "used_precedent_ranks": [],
            "grounded": False,
            "confidence": 0.0,
            "api_status": "failed",
        }

        self.cache[key] = fallback

        return fallback