## Notebooks

| Notebook | Purpose | Status |
|---|---|---|
| `01_eda.ipynb` | Data loading, brand selection, EDA | ✓ |
| `02_taxonomy.ipynb` | Discover and freeze the intent taxonomy (11 intents) | ✓ Frozen (SHA: `7a05e4af...`) |
| `03_golden_set.ipynb` | Human-verify a golden evaluation set (198 examples) | ✓ Frozen (SHA: `acde341d...`) |
| `04_classifier.ipynb` | Intent classifier | pending |
| `05_retrieval.ipynb` | Retrieval over past replies | pending |
| `06_agent.ipynb` | End-to-end agent pipeline | pending |
| `07_evaluation.ipynb` | Final metrics and failure analysis | pending |

## Frozen artifacts

- `configs/intents.yaml` — intent taxonomy (source of truth)
- `evaluation/golden_set.jsonl` — 198 human-verified evaluation examples
- `evaluation/annotation_guidelines.md` — annotation rules