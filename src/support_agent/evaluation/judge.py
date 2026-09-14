"""Three independent judges for 06_agent.

1. escalation_suitability(customer_text)         — independent of generation
2. universal(query, reply)                       — 3 dimensions + unsupported claims
3. groundedness(query, precedents, reply)        — grounded replies only

Each judge has its own rubric (frozen, hashed) and its own cache.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

import numpy as np

from support_agent.generation.generator import (
    _RotatingGroqClient,
    _get_api_keys,
    STRICT_OUTPUT_MODELS,
)


# ---------------------------------------------------------------------
# Rubrics
# ---------------------------------------------------------------------

ESCALATION_SYSTEM = """You assess whether a customer message can be safely auto-handled.

You receive ONLY the customer's message. You do NOT receive any model
prediction, retrieved evidence, or taxonomy information.

A message is SAFE TO AUTO-HANDLE only if all of the following hold:
- The request is clear enough to answer without follow-up questions.
- The message contains the information needed, OR the answer does not
  require customer-specific details.
- A reasonable reply can be produced from general customer-service
  knowledge WITHOUT inventing company-specific policy, timelines,
  amounts, or actions.
- There is no legal, financial, medical, or vulnerability risk.
- It is a single, simple issue (not compound or edge-case).

Closed-world rule: assume nothing outside the customer message.

Return strict JSON:
{
  "auto_handle_safe": <boolean>,
  "reasons": [<short string>, ...]
}
Reasons should be <=10 words each. Empty if safe.
"""

ESCALATION_SCHEMA = {
    "type": "object",
    "properties": {
        "auto_handle_safe": {"type": "boolean"},
        "reasons":          {"type": "array", "items": {"type": "string"}},
    },
    "required": ["auto_handle_safe", "reasons"],
    "additionalProperties": False,
}


UNIVERSAL_SYSTEM = """You score a customer-support reply on three dimensions.

You receive:
- the customer's original message
- a candidate reply

Score each on 1-5:
- correctness:  no false claims; does not contradict the customer's message
- relevance:    addresses the customer's specific ask
- helpfulness:  actionable; moves the conversation forward

Also flag any unsupported claim. An unsupported claim is a statement
about GWR policy, compensation, eligibility, timelines, procedures,
contact routes, or operational actions asserted by the reply with no
evidence provided. Empathy, acknowledgement, and paraphrase of the
customer's message are NOT claims.

Return strict JSON:
{
  "correctness": <number 1-5>,
  "relevance":   <number 1-5>,
  "helpfulness": <number 1-5>,
  "unsupported_claim": <boolean>,
  "unsupported_claims": [<string>, ...]
}
"""

UNIVERSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "correctness":         {"type": "number"},
        "relevance":           {"type": "number"},
        "helpfulness":         {"type": "number"},
        "unsupported_claim":   {"type": "boolean"},
        "unsupported_claims":  {"type": "array", "items": {"type": "string"}},
    },
    "required": ["correctness", "relevance", "helpfulness",
                 "unsupported_claim", "unsupported_claims"],
    "additionalProperties": False,
}


GROUNDEDNESS_SYSTEM = """You score how well a reply is grounded in retrieved evidence.

You receive:
- the customer's message
- retrieved historical precedents (ranked)
- a candidate reply

Score groundedness 1-5:
- 5: every operational claim in the reply is supported by the precedents
- 3: most operational claims supported; minor ungrounded statements
- 1: reply makes operational claims not present in the precedents

An operational claim is a statement about GWR policy, compensation,
eligibility, timelines, procedures, contact routes, or operational
actions. Empathy, acknowledgement, and paraphrase do NOT count.

Return strict JSON:
{
  "groundedness": <number 1-5>,
  "unsupported_claims": [<string>, ...]
}
"""

GROUNDEDNESS_SCHEMA = {
    "type": "object",
    "properties": {
        "groundedness":       {"type": "number"},
        "unsupported_claims": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["groundedness", "unsupported_claims"],
    "additionalProperties": False,
}


def _build_precedent_block(precedents: list) -> str:
    lines = []
    for i, p in enumerate(precedents, start=1):
        intent = p.get("intent", "unknown")
        cust = str(p.get("customer_text", ""))
        resp = str(p.get("response_text", ""))
        lines.append(f"[{i}] (intent={intent})")
        lines.append(f"  Customer: {cust}")
        lines.append(f"  Brand:    {resp}")
    return "\n".join(lines)


class Judge:
    def __init__(self, model: str, cache_path: Path,
                 cache: Optional[dict] = None):
        self.model = model
        self.cache_path = Path(cache_path)
        self.cache: dict = cache if cache is not None else {}
        self._client = _RotatingGroqClient(_get_api_keys())

    def _key(self, kind: str, system: str, user: str) -> str:
        return hashlib.sha256(
            f"{kind}|{self.model}|{system}|{user}".encode()
        ).hexdigest()

    def _call(self, system: str, user: str, schema: dict, name: str) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]
        if self.model in STRICT_OUTPUT_MODELS:
            try:
                resp = self._client.chat_completions_create(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": name,
                            "strict": True,
                            "schema": schema,
                        },
                    },
                )
                return json.loads(resp.choices[0].message.content)
            except Exception as e:
                print(f"[judge:{name}] strict failed ({type(e).__name__}); "
                      f"falling back")
        resp = self._client.chat_completions_create(
            model=self.model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    def _cached_call(self, kind: str, system: str, user: str,
                     schema: dict, name: str, max_retries: int = 3) -> dict:
        key = self._key(kind, system, user)
        if key in self.cache:
            return self.cache[key]

        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                raw = self._call(system, user, schema, name)
                self.cache[key] = raw
                with open(self.cache_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "key": key, "kind": kind,
                        "model": self.model,
                        "response": raw,
                    }, ensure_ascii=False) + "\n")
                return raw
            except Exception as e:
                last_err = e
                time.sleep(0.5 * (2 ** attempt) + float(np.random.uniform(0, 0.3)))

        print(f"[judge:{kind}] failed: {last_err}")
        return {"_error": str(last_err)}

    # ---- Public judges ----

    def escalation_suitability(self, customer_text: str) -> dict:
        user = f"Customer message:\n{customer_text}"
        raw = self._cached_call("escalation", ESCALATION_SYSTEM, user,
                                ESCALATION_SCHEMA, "escalation")
        if "_error" in raw:
            return {"auto_handle_safe": False,
                    "reasons": ["judge_error"]}
        reasons = raw.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = []
        return {
            "auto_handle_safe": bool(raw.get("auto_handle_safe", False)),
            "reasons": [str(r) for r in reasons if r],
        }

    def universal(self, query: str, reply: str) -> dict:
        user = f"Customer message:\n{query}\n\nReply:\n{reply}"
        raw = self._cached_call("universal", UNIVERSAL_SYSTEM, user,
                                UNIVERSAL_SCHEMA, "universal")

        def _clip(v, lo=1, hi=5):
            try:
                return int(min(max(int(round(float(v))), lo), hi))
            except (TypeError, ValueError):
                return 3

        claims = raw.get("unsupported_claims", [])
        if not isinstance(claims, list):
            claims = []

        return {
            "correctness":       _clip(raw.get("correctness", 3)),
            "relevance":         _clip(raw.get("relevance", 3)),
            "helpfulness":       _clip(raw.get("helpfulness", 3)),
            "unsupported_claim": bool(raw.get("unsupported_claim", False)),
            "unsupported_claims": [str(c) for c in claims if c],
        }

    def groundedness(self, query: str, precedents: list, reply: str) -> dict:
        block = _build_precedent_block(precedents)
        user = (
            f"Customer message:\n{query}\n\n"
            f"Retrieved precedents:\n{block}\n\n"
            f"Reply:\n{reply}"
        )
        raw = self._cached_call("groundedness", GROUNDEDNESS_SYSTEM, user,
                                GROUNDEDNESS_SCHEMA, "groundedness")
        try:
            g = int(min(max(int(round(float(raw.get("groundedness", 3)))), 1), 5))
        except (TypeError, ValueError):
            g = 3
        claims = raw.get("unsupported_claims", [])
        if not isinstance(claims, list):
            claims = []
        return {
            "groundedness": g,
            "unsupported_claims": [str(c) for c in claims if c],
        }