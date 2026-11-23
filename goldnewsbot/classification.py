"""Deterministic topic and market tagging; not a directional trading signal."""
from dataclasses import dataclass
RULES={"war_conflict":("war","airstrike","missile","invasion","ceasefire","military strike","conflict"),"geopolitics_sanctions":("sanction","tariff","trade war","diplomatic","election","government"),"oil_energy":("crude oil","opec","oil export","oil import","oil supply","pipeline","tanker","natural gas"),"central_banks":("federal reserve","fed","fomc","ecb","bank of england","bank of japan","interest rate","monetary policy"),"economics":("inflation","cpi","pce","nfp","payroll","unemployment","gdp","pmi","retail sales"),"financial_markets":("stock market","bond yield","treasury yield","dollar index","forex","gold price","bullion")}
MARKETS={"war_conflict":("XAUUSD","USD","CRUDE_OIL"),"geopolitics_sanctions":("XAUUSD","USD","CRUDE_OIL"),"oil_energy":("CRUDE_OIL","XAUUSD","CAD"),"central_banks":("XAUUSD","USD","EURUSD","GBPUSD","USDJPY"),"economics":("XAUUSD","USD","EURUSD","GBPUSD","USDJPY"),"financial_markets":("XAUUSD","USD","EURUSD","GBPUSD","USDJPY")}
@dataclass(frozen=True)
class Classification:
    primary:str
    categories:tuple[str,...]
    related_markets:tuple[str,...]
    matched_terms:tuple[str,...]
def classify_news(title,body=""):
    text=f"{title or ''} {body or ''}".casefold(); hits={c:tuple(t for t in terms if t in text) for c,terms in RULES.items()}
    cats=tuple(c for c,terms in hits.items() if terms)
    if not cats:return Classification("other",(),(),())
    matched=tuple(t for c in cats for t in hits[c]); markets=tuple(dict.fromkeys(m for c in cats for m in MARKETS[c])); primary=max(cats,key=lambda c:len(hits[c]))
    return Classification(primary,cats,markets,matched)
