"""Self-contained pipeline for the ResolveIQ API.

Loads frozen artifacts once at startup. Reconstructs the classifier prompt
from the taxonomy and the frozen corpus. Wraps the existing modules in
src/support_agent/.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from support_agent.retrieval.index import Corpus
from support_agent.retrieval.retriever import TFIDFRetriever
from support_agent.generation.generator import Generator
from support_agent.escalation.policy import (
    EscalationConfig, decide, calibrate_confidence,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass
class Pipeline:
    root: Path
    tax: dict = field(default_factory=dict)
    intent_names: list = field(default_factory=list)
    classifier_cfg: dict = field(default_factory=dict)
    retriever_cfg: dict = field(default_factory=dict)
    agent_cfg: dict = field(default_factory=dict)
    esc_cfg: EscalationConfig | None = None

    def __post_init__(self):
        self.root = Path(self.root)
        self._load_taxonomy()
        self._load_classifier()
        self._load_retriever()
        self._load_generator()
        self._load_escalation()

    # ---- loaders --------------------------------------------------

    def _load_taxonomy(self) -> None:
        p = self.root / "configs" / "intents.yaml"
        self.tax = yaml.safe_load(p.read_bytes())
        self.intent_names = [i["name"] for i in self.tax["intents"]]

    def _load_classifier(self) -> None:
        self.classifier_cfg = json.loads(
            (self.root / "runs" / "classifier" / "chosen.json").read_text()
        )
        self.reliability = pd.read_csv(
            self.root / "runs" / "classifier" / "reliability_for_escalation.csv"
        )
        ex_path = self.root / "runs" / "taxonomy" / "intent_examples.csv"
        if ex_path.exists():
            ex = pd.read_csv(ex_path, encoding="utf-8")
            ex = ex[ex["_keep"].astype(str).str.lower() == "y"]
            self.fewshot = ex.groupby("intent")["customer_text"].apply(list).to_dict()
        else:
            self.fewshot = {}

    def _load_retriever(self) -> None:
        self.retriever_cfg = json.loads(
            (self.root / "runs" / "retrieval" / "chosen_retriever.json").read_text()
        )
        corpus_path = self.root / "runs" / "retrieval" / "corpus.jsonl"
        self.corpus = Corpus.load_jsonl(corpus_path)
        name = self.retriever_cfg["approach"]
        if name == "tfidf":
            self.retriever = TFIDFRetriever(self.corpus)
        elif name == "bm25":
            from support_agent.retrieval.retriever import BM25Retriever
            self.retriever = BM25Retriever(self.corpus)
        else:
            raise ValueError(f"Unsupported retriever: {name}")

    def _load_generator(self) -> None:
        self.agent_cfg = json.loads(
            (self.root / "runs" / "agent" / "chosen_agent.json").read_text()
        )
        self.generator = Generator(
            model=self.agent_cfg.get("generator_model", "openai/gpt-oss-20b"),
            cache_path=self.root / "cache" / "api_generated_replies.jsonl",
        )

    def _load_escalation(self) -> None:
        c = self.agent_cfg.get("escalation_config", {})
        self.esc_cfg = EscalationConfig(
            tau_c=float(c.get("tau_c", 0.40)),
            tau_m=float(c.get("tau_m", 0.15)),
            escalate_on_other_or_ambiguous=bool(
                c.get("escalate_on_other_or_ambiguous", True)
            ),
            escalate_on_zero_coverage=bool(
                c.get("escalate_on_zero_coverage", True)
            ),
        )

    # ---- classifier prompt ---------------------------------------

    def _build_classifier_prompt(self) -> str:
        parts = [
            "You are an intent classifier for GWRHelp customer support.",
            "",
            "Available intents (choose exactly one):",
        ]
        for it in self.tax["intents"]:
            parts.append(f"- {it['name']}: {it['description'].strip()}")
            parts.append(f"  Include when: {' | '.join(it['include_when'])}")
            parts.append(f"  Exclude when: {' | '.join(it['exclude_when'])}")
        parts += [
            "",
            "Rules:",
            '- Respond with a single JSON object and nothing else.',
            '- Do NOT force-fit a message into an operational intent merely '
            'because related words appear. If nothing fits, use "other".',
            '- If two intents are genuinely equally plausible, use "ambiguous".',
            "- Confidence is a raw score in [0,1].",
            "",
            'Output schema: {"intent": "<name>", "confidence": <float>, '
            '"alternative_intent": "<name>", "alternative_confidence": <float>}',
            "",
            "Few-shot examples:",
        ]
        for intent, examples in self.fewshot.items():
            for ex in examples[:2]:
                parts.append(f'  <ex intent="{intent}">{str(ex)[:200]}</ex>')
        return "\n".join(parts)

    # ---- runtime --------------------------------------------------

    def _classify(self, message: str) -> dict:
        system = self._build_classifier_prompt()
        raw = self._call_classifier(message, system)
        intent = str(raw.get("intent", "")).strip()
        conf = float(raw.get("confidence", 0.0) or 0.0)
        alt = str(raw.get("alternative_intent", "")).strip()
        alt_c = float(raw.get("alternative_confidence", 0.0) or 0.0)
        if intent not in self.intent_names:
            intent, conf = "other", 0.0
        if alt not in self.intent_names:
            alt, alt_c = "", 0.0
        return {
            "intent": intent,
            "confidence": min(max(conf, 0.0), 1.0),
            "alternative_intent": alt,
            "alternative_confidence": min(max(alt_c, 0.0), 1.0),
        }

    def _call_classifier(self, message: str, system: str) -> dict:
        # Prefer the project client if present
        try:
            from support_agent.llm.client import classify as client_classify
            return client_classify(message, system)
        except Exception:
            pass

        keys = (os.environ.get("GROQ_API_KEYS")
                or os.environ.get("GROQ_API_KEY") or "").split(",")
        keys = [k.strip() for k in keys if k.strip()]
        if not keys:
            raise RuntimeError("Set GROQ_API_KEY in .env")

        model = (self.classifier_cfg.get("model_meta", {})
                 .get("model", "openai/gpt-oss-20b"))
        try:
            from groq import Groq
            client = Groq(api_key=keys[0])
        except ImportError:
            from openai import OpenAI
            client = OpenAI(api_key=keys[0], base_url=GROQ_BASE_URL)

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    # ---- public --------------------------------------------------

    def get_taxonomy(self) -> dict:
        return {
            "version": self.tax.get("version", 1),
            "intents": [
                {
                    "name": i["name"],
                    "description": i["description"].strip(),
                    "include_when": i["include_when"],
                    "exclude_when": i["exclude_when"],
                }
                for i in self.tax["intents"]
            ],
        }

    def run(self, message: str, top_k: int = 5,
            force_escalate: bool = False) -> dict:
        # 1. classify
        cls = self._classify(message)
        conf_cal = calibrate_confidence(cls["confidence"], self.reliability)

        # 2. retrieve
        hits = self.retriever.retrieve(message, k=top_k)
        idx = {int(self.corpus.doc_ids[i]): i for i in range(len(self.corpus))}
        precedents = []
        for doc_id, score in hits:
            i = idx.get(int(doc_id))
            if i is None:
                continue
            precedents.append({
                "root_id": int(doc_id),
                "intent": str(self.corpus.intents[i]),
                "customer_text": self.corpus.customer_texts[i],
                "response_text": self.corpus.response_texts[i],
                "score": float(score),
            })

        corpus_coverage = int(cls["intent"] in set(self.corpus.intents))

        # 3. escalate?
        if force_escalate:
            escalated, reason = True, "force"
        else:
            escalated, reason = decide(
                {
                    "pred_intent": cls["intent"],
                    "confidence": cls["confidence"],
                    "confidence_calibrated": conf_cal,
                    "alternative_confidence": cls["alternative_confidence"],
                    "corpus_coverage": corpus_coverage,
                },
                self.esc_cfg,
            )

        # 4. generate
        reply, used_ranks, grounded, api_status = None, [], False, "skipped"
        if not escalated:
            out = self.generator.generate(message, precedents=precedents)
            reply = out["reply"]
            used_ranks = out["used_precedent_ranks"]
            grounded = out["grounded"]
            api_status = out["api_status"]

        return {
            "message": message,
            "intent": cls["intent"],
            "confidence": cls["confidence"],
            "confidence_calibrated": conf_cal,
            "alternative_intent": cls["alternative_intent"],
            "alternative_confidence": cls["alternative_confidence"],
            "corpus_coverage": corpus_coverage,
            "retrieved": precedents,
            "escalated": escalated,
            "escalation_reason": reason,
            "reply": reply,
            "used_precedent_ranks": used_ranks,
            "grounded": grounded,
            "api_status": api_status,
        }