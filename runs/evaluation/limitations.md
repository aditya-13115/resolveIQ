# Limitations

- **Test set size (n=139).** Bootstrap 95% CIs reported on headline
  quantities. Small-class metrics (e.g. `ambiguous`, n=1) have wide CIs.
- **Coverage-oriented golden sampling.** Rare intents oversampled.
  Natural-slice metrics are the closest proxy for production traffic.
- **Intent-match retrieval relevance.** A 20-query human audit on dev found
  nDCG@5 = 0.592 and graded P@5 = 0.33,
  indicating the proxy overstates usefulness.
- **Judge model is an LLM.** 20-row human spot-check: universal ρ = 0.7217486754461739, escalation agreement = 0.95.
- **Corpus scale.** 50 documents at smoke-test scale.
- **Historical responses may contain outdated policies.** Retrieval and
  grounding use historical GWRHelp replies without a time-relevance filter.
- **Escalation policy signals.** Classifier confidence and retrieval coverage
  do not discriminate safe from unsafe messages on dev.
- **Cost/latency not captured.**
