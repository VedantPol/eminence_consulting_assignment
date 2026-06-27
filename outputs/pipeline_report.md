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
- *Passive & ETF Investing* — 25 mentions, net sentiment +0.12
- *SIP Returns & Long-Term Performance* — 22 mentions, net sentiment +0.41
- *Naren & Leadership Outlook* — 15 mentions, net sentiment +0.27
- *App & Digital Experience* — 13 mentions, net sentiment -0.46
- *NFO & Fund Launches* — 12 mentions, net sentiment +0.08
- *CSR, Events & Financial Literacy* — 4 mentions, net sentiment +0.50
- *Active Asset Allocation & Hybrid Funds* — 3 mentions, net sentiment +0.67

## Classification accuracy (zero-shot vs Claude silver-gold)
- Reference: Claude Sonnet 4.6 (independent silver-gold annotator, not human) (n=95)
- Driver: 87.4% acc, macro-F1 0.81
- Sub-driver: 84.2% acc, macro-F1 0.831
- On the 71 high-confidence (non-escalated) rows: driver 87.3%, sub-driver 87.3%
- Sentiment 3-way: provided↔ours 70.5%, provided↔Claude 48.4%, ours↔Claude 41.1%

## Sentiment QA vs provided labels: 70.5% agreement (n=95)

## Risk queue: 12 flagged items (top priority surfaced in outputs)