"""Urgency scoring for breaking financial news. Heuristic, conservative."""
import re

HIGH_URGENCY = ("emergency rate decision", "emergency rate cut", "emergency rate hike", "unexpected rate decision", "rate decision announced", "fomc emergency meeting", "central bank intervention", "bank collapse", "bank failure", "sovereign default", "financial panic", "military strike", "airstrike", "missile attack", "invasion", "major escalation", "emergency sanctions", "ceasefire agreement")
MEDIUM_URGENCY = ("breaking", "just in", "urgent", "surprise rate", "rate cut announced", "rate hike announced", "fed cuts rates", "fed raises rates", "nfp surprise", "cpi surprise", "unexpected inflation", "unexpected jobs", "unexpected unemployment", "opec emergency", "tariffs announced", "new sanctions")
MARKET_EVENT = ("cpi", "pce", "nfp", "nonfarm payroll", "interest rate", "rate decision", "fomc", "central bank", "gdp", "inflation", "unemployment", "bank", "sanctions", "tariff", "war", "strike", "oil", "opec", "gold", "crash", "surge", "plunge", "rally", "selloff")

def score_breaking_news(title, summary="", source=""):
    text = re.sub(r"\s+", " ", f"{title} {summary}").lower()
    score = 0
    matches = []
    if any(term in text for term in HIGH_URGENCY): score += 55; matches.append("high urgency phrase")
    if any(term in text for term in MEDIUM_URGENCY): score += 35; matches.append("breaking/medium urgency phrase")
    if any(term in text for term in MARKET_EVENT): score += 15; matches.append("market-moving topic")
    if len(title.strip()) < 18: score -= 10
    score = min(100, max(0, score))
    if score >= 60: level="عاجل"
    elif score >= 35: level="مهم"
    else: level="عادی"
    return {"score": score, "level": level, "threshold": 35, "matches": matches, "source": source}

def format_breaking_badge(assessment):
    level=assessment.get("level", "عادی")
    score=assessment.get("score", 0)
    return f"{level} ({score}/100)"
