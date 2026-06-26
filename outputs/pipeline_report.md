# Phase 1 Pipeline Report — ICICI Prudential AMC

**Reputation Health Score: 60.1/100 (Healthy)**  
Components: net_sentiment 62.8, media_quality 58.3, positive_share 29.5, risk_penalty 95.3

## Funnel
- Raw records: 100
- Duplicates removed: 4
- Irrelevant removed: 1
- **Final relevant & classified: 95**

## Share of Voice: 82.4% (vs 8 competitors named)

## Driver breakdown
- **User Experience** — 56 mentions, net sentiment +0.11 (+18/26/-12)
- **Brand Perception** — 35 mentions, net sentiment +0.26 (+9/26/-0)
- **Responsible Business Practices** — 4 mentions, net sentiment +0.25 (+1/3/-0)

## Top themes
- *Naren & CIO Market Outlook* — 21 mentions, net sentiment +0.24
- *Passive & ETF Investing* — 19 mentions, net sentiment +0.32
- *NFO & Fund Launches* — 16 mentions, net sentiment +0.06
- *SIP Returns & Long-Term Performance* — 15 mentions, net sentiment +0.27
- *App & Digital Experience* — 13 mentions, net sentiment -0.46
- *Active Fund & Portfolio Strategy* — 6 mentions, net sentiment +0.50
- *CSR, Events & Financial Literacy* — 4 mentions, net sentiment +0.50

## Classification accuracy (zero-shot vs Claude silver-gold)
- Reference: Claude Sonnet 4.6 (independent silver-gold annotator, not human) (n=95)
- Driver: 86.3% acc, macro-F1 0.803
- Sub-driver: 83.2% acc, macro-F1 0.827
- On the 71 high-confidence (non-escalated) rows: driver 85.9%, sub-driver 85.9%
- Sentiment 3-way: provided↔ours 70.5%, provided↔Claude 47.4%, ours↔Claude 42.1%

## Sentiment QA vs provided labels: 70.5% agreement (n=95)

## Risk queue: 12 flagged items (top priority surfaced in outputs)