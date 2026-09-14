"""Escalation policy for 06_agent.

The policy is ordered: first matching rule fires.
Thresholds are declared before dev and locked before test.

Public API:
    EscalationConfig
    calibrate_confidence(raw_conf, rel_table)
    decide(row, config) -> (escalated: bool, reason: str)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd


@dataclass
class EscalationConfig:
    tau_c: float = 0.40                     # calibrated confidence floor
    tau_m: float = 0.15                     # top-1 minus top-2 margin floor
    escalate_on_other_or_ambiguous: bool = True
    escalate_on_zero_coverage: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def calibrate_confidence(raw_conf, rel_table: pd.DataFrame) -> float:
    """Look up empirical accuracy for a raw confidence from the reliability table.

    This is a *pure lookup*, not a recalibration. The reliability table was
    produced by 04 and is treated as frozen input.
    """
    if raw_conf is None or (isinstance(raw_conf, float) and pd.isna(raw_conf)):
        return 0.0
    try:
        raw = float(raw_conf)
    except (TypeError, ValueError):
        return 0.0

    valid = rel_table.dropna(subset=["mean_conf", "emp_acc"])
    if len(valid) == 0:
        return raw

    idx = (valid["mean_conf"].astype(float) - raw).abs().idxmin()
    try:
        return float(valid.loc[idx, "emp_acc"])
    except Exception:
        return raw


def decide(row, config: EscalationConfig) -> tuple[bool, str]:
    """Return (escalated, reason).

    row is a mapping or Series with:
        pred_intent              str
        confidence               float   (raw)
        confidence_calibrated    float   (from reliability table)
        alternative_confidence   float
        corpus_coverage          int (0 or 1)
    """
    def _get(k, default=None):
        try:
            v = row.get(k, default) if hasattr(row, "get") else row[k]
        except Exception:
            return default
        return v if v is not None else default

    intent = str(_get("pred_intent", "other"))

    if config.escalate_on_other_or_ambiguous and intent in ("other", "ambiguous"):
        return True, "intent_other_or_ambiguous"

    try:
        cov = int(_get("corpus_coverage", 1))
    except (TypeError, ValueError):
        cov = 1
    if config.escalate_on_zero_coverage and cov == 0:
        return True, "corpus_coverage_zero"

    try:
        cal_conf = float(_get("confidence_calibrated", 0.0))
    except (TypeError, ValueError):
        cal_conf = 0.0
    if cal_conf < config.tau_c:
        return True, "low_calibrated_confidence"

    try:
        top1 = float(_get("confidence", 0.0))
        alt = float(_get("alternative_confidence", 0.0))
        margin = top1 - alt
    except (TypeError, ValueError):
        margin = 0.0
    if margin < config.tau_m:
        return True, "low_margin"

    return False, ""