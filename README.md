# ResolveIQ

A selective, evidence-grounded support agent for **GWRHelp**, built on the
Twitter Customer Support dataset. The agent classifies intent, retrieves
historical precedents, generates a grounded reply, and decides whether to
auto-handle or escalate.

**The emphasis is on evaluation, not architectural complexity.** Every
test-time artifact is SHA-locked. Every reported number traces to a
frozen artifact.

---

## Reproduce in under 15 minutes

```bash
# 1. Environment
uv sync

# 2. API key
cp .env.example .env
# Add: GROQ_API_KEY=gsk_...

# 3. Run notebooks in order
jupyter notebook notebooks/01_eda.ipynb
# ... then 02 → 03 → 04 → 05 → 06 → 07
```

Notebooks `02`–`06` are cached. Re-runs hit the disk cache and complete
in seconds. Notebook `07` makes no API calls at all.

---

## Final system

| Stage | Chosen approach | Test metric |
|---|---|---:|
| Intent classifier | Few-shot LLM (`openai/gpt-oss-20b` via Groq) | op macro F1 = **0.624** |
| Retriever | TF-IDF (1–2 grams, sublinear TF) | Recall@5 = **0.532** |
| Agent | Ungrounded (predeclared fallback) | unsafe auto rate = **0.597** |
| End-to-end | Safe automation coverage | **0.295** |

Full metrics: `runs/evaluation/metrics.json`  
Full analysis: `reports/final_report.md`

---

## Notebooks

| Notebook | Purpose | Status |
|---|---|---|
| `01_eda.ipynb` | Brand selection and EDA | ✓ |
| `02_taxonomy.ipynb` | Intent taxonomy (11 intents) | ✓ Frozen (`7a05e4af...`) |
| `03_golden_set.ipynb` | Human-verified golden set (198 examples) | ✓ Frozen (`acde341d...`) |
| `04_classifier.ipynb` | Intent classifier (4 approaches) | ✓ Frozen (`7d51251a...`) |
| `05_retrieval.ipynb` | Retrieval over historical replies (7 approaches) | ✓ Frozen (`33dbaea4...`) |
| `06_agent.ipynb` | End-to-end agent (4 approaches) | ✓ Frozen (`dc6c09f6...`) |
| `07_evaluation.ipynb` | End-to-end synthesis | ✓ Complete |

---

## Frozen artifacts

All test-time predictions and metrics are immutable. Any modification
invalidates downstream locks.

```text
configs/intents.yaml                            taxonomy (source of truth)
runs/classifier/chosen.json                     classifier choice + config
runs/classifier/TEST_LOCK.json                  hash of classifier test artifacts
runs/retrieval/chosen_retriever.json            retriever choice + human audit
runs/retrieval/corpus.jsonl                     50-document corpus
runs/retrieval/TEST_LOCK.json                   hash of retrieval test artifacts
runs/agent/chosen_agent.json                    agent choice + escalation config
runs/agent/TEST_LOCK.json                       hash of agent test generation
runs/agent/EVAL_LOCK.json                       hash of all agent judging artifacts
runs/evaluation/metrics.json                    single source of truth for the report
evaluation/golden_set.jsonl                     198 human-verified examples
evaluation/annotation_guidelines.md             annotation rules
```

Every SHA in `runs/evaluation/metrics.json` and `handoff_to_report.json`
must match the artifact on disk. Any drift is a hard failure.

---

## Repo layout

```text
ResolveIQ/
├── configs/                brand.yaml, intents.yaml, eval.yaml
├── notebooks/              01–07 (run in order)
├── src/support_agent/      reusable modules
│   ├── intents/            classifier
│   ├── retrieval/          index + retriever
│   ├── generation/         reply generation
│   ├── escalation/         policy
│   ├── evaluation/         judges
│   └── llm/                Groq client + cache
├── runs/                   frozen run artifacts
│   ├── taxonomy/           discovery + coverage
│   ├── golden_set/         golden set + audit trail
│   ├── classifier/         predictions + TEST_LOCK
│   ├── retrieval/          predictions + TEST_LOCK + corpus
│   ├── agent/              predictions + TEST_LOCK + EVAL_LOCK
│   └── evaluation/         end-to-end metrics + tables + figures
├── reports/                final_report.md + figures/
├── evaluation/             promoted golden set + guidelines
├── tests/                  unit tests
└── DECISIONS.md            chronological decision log
```

---

## Key findings

1. **Classifier is the bottleneck.** 55 of 139 test rows (39.6%) have a
   wrong predicted intent. Everything downstream inherits that error.
2. **`delay_compensation` boundary is the single largest error.** 8 of
   15 errors on that intent are `→ service_disruption`.
3. **Grounding did not improve reply quality.** Δ = −0.51 on dev; the
   grounded prompt invents operational claims from weakly relevant precedents.
4. **Escalation signals do not discriminate safe from unsafe.** Classifier
   confidence and retrieval coverage do not correlate with the suitability judge.
5. **The corpus is 50 documents.** Recall is bounded by this more than by
   the choice of retriever.

---

## Known limitations

See `runs/evaluation/limitations.md`. Short version:

- Test set is 139 rows; CIs are wide.
- Golden set is coverage-oriented, not prevalence-representative.
- Retrieval relevance is proxied by intent-match; a human audit found
  nDCG@5 = 0.592, graded P@5 = 0.330.
- Judges are LLM-based; human spot-check agreement ρ = 0.72 (universal),
  0.95 (escalation).
- Cost and latency are not captured.

---

## Reproducibility pins

| Artifact | SHA-256 prefix |
|---|---|
| Taxonomy (`configs/intents.yaml`) | `7a05e4af...` |
| Golden set (`evaluation/golden_set.jsonl`) | `acde341d...` |
| Classifier (`runs/classifier/chosen.json`) | `7d51251a...` |
| Retriever (`runs/retrieval/chosen_retriever.json`) | `33dbaea4...` |
| Agent (`runs/agent/chosen_agent.json`) | `dc6c09f6...` |
| Corpus (`runs/retrieval/corpus.jsonl`) | `69327018...` |

Full hashes: `runs/evaluation/metrics.json` → `frozen_inputs`.
