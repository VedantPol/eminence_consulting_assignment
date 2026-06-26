"""
Central configuration for the reputation-intelligence pipeline.

Everything that is "knowledge" rather than "logic" lives here so the pipeline
is transparent and easy to audit/tune: the classification taxonomy, the
zero-shot hypotheses, brand/competitor gazetteers, source-tier map, and the
weights of the composite Reputation Health Score.
"""
from __future__ import annotations
import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
DATA_XLSX = ROOT / "Dataset.xlsx"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

BRAND = "ICICI Prudential AMC"


# --------------------------------------------------------------------------- #
# Secrets / .env  — read ANTHROPIC_API_KEY from the environment only.
# Minimal loader so `.env` (gitignored) populates os.environ without an extra
# dependency; existing env vars always win.
# --------------------------------------------------------------------------- #
def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(ROOT / ".env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
# Sub-driver confidence below which a zero-shot row is escalated to the LLM.
LLM_CONF_THRESHOLD = float(os.environ.get("LLM_CONF_THRESHOLD", "0.45"))
LLM_ENABLED = bool(ANTHROPIC_API_KEY)

# --------------------------------------------------------------------------- #
# Local models (run fully offline after first download)
# --------------------------------------------------------------------------- #
MODEL_SENTIMENT = "ProsusAI/finbert"                                # finance NEWS sentiment
MODEL_SENTIMENT_SOCIAL = "cardiffnlp/twitter-roberta-base-sentiment-latest"  # social/review
MODEL_ZEROSHOT  = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"      # driver/sub-driver
MODEL_EMOTION   = "j-hartmann/emotion-english-distilroberta-base"   # emotion
MODEL_EMBED     = "sentence-transformers/all-MiniLM-L6-v2"          # embeddings

# Channels whose tone is informal -> routed to the social sentiment model.
# FinBERT is trained on financial news and misreads app-review/social tone
# (it labelled blunt app complaints "neutral"); the social model fixes recall.
SOCIAL_SENTIMENT_CHANNELS = {"App Store / Reviews", "Reddit", "X/Twitter"}

# --------------------------------------------------------------------------- #
# Classification framework  (3 Drivers / 8 Sub-drivers)
# Each sub-driver carries a natural-language hypothesis used by the zero-shot
# NLI classifier. Rich, example-laden hypotheses materially improve accuracy.
# --------------------------------------------------------------------------- #
TAXONOMY: dict[str, dict[str, str]] = {
    "Brand Perception": {
        "Thought Leadership":
            "expert or CXO commentary, market outlook, economic views, rate-cut "
            "opinion, or an interview with a fund manager or chief investment officer",
        "Product Strategy":
            "the launch or introduction of a NEW fund, a new NFO opening or offering, "
            "a new SIP plan, product pricing, expense ratio, a festive offer, or product "
            "positioning — i.e. a new product being announced",
        "Brand Visibility & Marketing":
            "an advertising campaign, a sponsorship, a brand ambassador, an award, "
            "or an investor-awareness or brand event",
    },
    "User Experience": {
        "Product & Service Quality":
            "fund returns and performance, a scheme compared against its benchmark, "
            "or a product feature being praised or criticised",
        "Customer Support & Complaint Resolution":
            "customer service and complaint handling, a delayed redemption, a slow "
            "KYC process, an unresponsive helpline, or a quick complaint resolution",
        "Digital & Omnichannel Experience":
            "the mobile app, the website, online onboarding, app crashes, website "
            "downtime, or the digital transaction experience",
    },
    "Responsible Business Practices": {
        "Regulatory Compliance & Ethical Governance":
            "a regulatory action or penalty, SEBI, a disclosure lapse, a mis-selling "
            "allegation, compliance, governance, or business ethics",
        "Social Impact & Community (CSR)":
            "corporate social responsibility, a community or rural-outreach programme, "
            "a financial-literacy drive, a donation, relief activity, or a women-investor "
            "initiative",
    },
}

# Flat helpers derived from the taxonomy
SUBDRIVERS: list[str] = [s for subs in TAXONOMY.values() for s in subs]
SUB_TO_DRIVER: dict[str, str] = {
    s: d for d, subs in TAXONOMY.items() for s in subs
}
SUB_HYPOTHESIS: dict[str, str] = {
    s: h for subs in TAXONOMY.values() for s, h in subs.items()
}
DRIVERS: list[str] = list(TAXONOMY)

# Confidence below which a sub-driver prediction is flagged "low confidence"
# (still populated — never blank — but surfaced for review).
LOW_CONF_THRESHOLD = 0.45
# When the top-2 sub-drivers are within this margin, channel/title hints break the tie.
TIE_MARGIN = 0.10

# --------------------------------------------------------------------------- #
# Brand + competitor gazetteer  (Share-of-Voice & entity extraction)
# --------------------------------------------------------------------------- #
BRAND_TERMS = [
    "icici prudential", "icici pru", "ipruamc", "ipru amc", "icici amc",
    "icici prudential mutual fund", "icici prudential amc", "icici mf",
]

COMPETITORS = {
    "HDFC": ["hdfc"],
    "SBI": ["sbi mutual", "sbi mf", "sbi funds", "sbi amc"],
    "Nippon India": ["nippon india", "nippon mutual", "reliance mutual"],
    "Kotak": ["kotak mahindra mf", "kotak mutual", "kotak amc"],
    "Axis": ["axis mutual", "axis mf", "axis amc"],
    "Aditya Birla SL": ["aditya birla", "birla sun life", "absl"],
    "UTI": ["uti amc", "uti mutual", "uti mf"],
    "Mirae Asset": ["mirae"],
    "DSP": ["dsp mutual", "dsp mf"],
    "Franklin Templeton": ["franklin templeton", "franklin india"],
    "Quant": ["quant mutual", "quant amc"],
    "Motilal Oswal": ["motilal oswal"],
    "Parag Parikh": ["parag parikh", "ppfas"],
    "Tata": ["tata mutual", "tata mf", "tata amc"],
    "Bandhan": ["bandhan mutual", "bandhan mf"],
    "Edelweiss": ["edelweiss mutual", "edelweiss mf"],
}

# Known spokespeople / key executives (entity extraction + thought-leadership signal)
KEY_PEOPLE = [
    "Sankaran Naren", "S. Naren", "Naren", "Nimesh Shah",
    "Mittul Kalawadia", "Anish Tawakley", "Manish Banthia", "Rahul Goswami",
]

# --------------------------------------------------------------------------- #
# Source tiers  (media-quality weighting in the Reputation Health Score)
# --------------------------------------------------------------------------- #
TIER1_NEWS = [
    "economic times", "the economic times", "moneycontrol", "cnbc", "business standard",
    "financial express", "hindu business line", "businessline", "mint", "livemint",
    "business today", "forbes", "bloomberg", "reuters", "zee business", "businessworld",
    "news18", "et now", "times of india", "fortune india", "et markets", "hindustan times",
]
TIER2_AGG = [
    "dailyhunt", "msn", "obnews", "newspoint", "goodreturns", "equitymaster",
    "shiksha", "zigwheels", "ndtv profit", "money9", "angel one", "angelone",
    "outlook money", "groww", "et money",
]
REVIEW_SOURCES = ["play store", "play.google", "mouthshut", "app store"]
SOCIAL_SOURCES = ["reddit", "linkedin", "x.com", "twitter", "facebook", "youtube", "quora"]

# Channel -> sub-drivers it provides a (soft) prior toward; used only as a tie-breaker.
CHANNEL_PRIORS = {
    "App Store / Reviews": [
        "Digital & Omnichannel Experience",
        "Customer Support & Complaint Resolution",
        "Product & Service Quality",
    ],
}

# Coarse category hints that leak into the Title field for some review rows.
TITLE_HINTS = {
    "digital experience": "Digital & Omnichannel Experience",
    "customer support": "Customer Support & Complaint Resolution",
    "product & service quality": "Product & Service Quality",
    "product and service quality": "Product & Service Quality",
}

# --------------------------------------------------------------------------- #
# Reputation Health Score — composite weights (0-100).
# Adapted from the standard reputation-index model (SoV / Net-Sentiment /
# Media-Quality / Risk) to the signals actually available in this dataset.
# Stakeholder-trust (NPS) and social-engagement components are omitted because
# the dataset does not contain that data — see the methodology doc.
# --------------------------------------------------------------------------- #
REPUTATION_WEIGHTS = {
    "net_sentiment":      0.45,   # (pos - neg) / total, reach-weighted
    "media_quality":      0.20,   # outlet tier x prominence (brand in headline)
    "positive_share":     0.20,   # share of mentions that are positive
    "risk_penalty":       0.15,   # inverse of compliance/UX negative-reach exposure
}

# Themes (semantic clustering of the corpus)
N_THEMES = 7
RANDOM_STATE = 42

# Theme keyphrase hygiene. A phrase is dropped if it contains ANY brand/person
# token (so "equity icici prudential" is removed), and also if it consists only
# of generic noise words. This surfaces real topics (NFO, SIP, midcap...).
THEME_BRAND_TOKENS = {
    "icici", "prudential", "amc", "ipru", "ipruamc", "pru",
    "naren", "sankaran", "tawakley", "banthia", "kalawadia", "haria", "chintan",
    "nimesh", "shah", "anish", "manish", "mittul", "rajat", "chandak", "anand",
}
THEME_GENERIC_TOKENS = {
    "mutual", "fund", "funds", "mf", "said", "says", "asset", "management",
    "ltd", "limited", "company", "executive", "director", "cio", "ed",
    "principal", "head", "officer", "india", "indian", "new", "year", "years",
}
THEME_BANNED_TOKENS = THEME_BRAND_TOKENS | THEME_GENERIC_TOKENS  # back-compat
