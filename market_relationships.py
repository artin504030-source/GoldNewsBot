"""Rule-based cross-market relationships and conditional scenario notes (not trading signals)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Relationship:
    event: str
    assets: tuple
    tendency: str
    condition: str
    confidence: str = "پایین تا متوسط"

RELATIONSHIPS = (
    Relationship("افزایش بازده اوراق آمریکا", ("USD", "DXY", "XAUUSD", "US30", "NAS100", "US500"), "بازده بالاتر می‌تواند دلار را تقویت و طلا/سهام را تحت فشار قرار دهد", "اگر افزایش بازده ناشی از تورم یا انقباض پولی باشد؛ رشد اقتصادی قوی می‌تواند سهام را حمایت کند"),
    Relationship("کاهش بازده اوراق آمریکا", ("USD", "DXY", "XAUUSD", "US30", "NAS100", "US500"), "بازده پایین‌تر می‌تواند دلار را تضعیف و طلا/سهام را حمایت کند", "اگر افت بازده به دلیل انتظار کاهش نرخ باشد؛ افت ناشی از ترس رشد ممکن است سهام را تضعیف کند"),
    Relationship("دلار قوی", ("DXY", "XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY"), "معمولاً فشار بر طلا و ارزهای مقابل دلار", "اثر به انتظارات نرخ و موقعیت‌گیری بازار وابسته است"),
    Relationship("دلار ضعیف", ("DXY", "XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY"), "معمولاً حمایت از طلا و ارزهای مقابل دلار", "رابطه می‌تواند با ریسک‌گریزی یا خبرهای خاص تغییر کند"),
    Relationship("ریسک‌گریزی", ("XAUUSD", "DXY", "VIX", "US30", "NAS100", "US500", "BTCUSD"), "تمایل به دارایی امن؛ نوسان بیشتر و فشار بر سهام پرریسک", "در شوک‌های نقدینگی، حتی دارایی‌های امن ممکن است موقتاً فروخته شوند"),
    Relationship("ریسک‌پذیری", ("US30", "NAS100", "US500", "AUDUSD", "NZDUSD", "BTCUSD", "XAUUSD"), "تمایل به رشد سهام و دارایی‌های ریسک‌پذیر", "به شرط نبود شوک نرخ، دلار یا خبر منفی مستقل"),
    Relationship("افزایش قیمت نفت", ("USOIL", "UKOIL", "CAD", "USD", "XAUUSD", "US500"), "می‌تواند انتظارات تورمی را بالا ببرد و به ارزهای مرتبط با انرژی کمک کند", "اثر بر سهام/طلا/دلار به علت افزایش قیمت و واکنش بانک مرکزی وابسته است"),
    Relationship("کاهش قیمت نفت", ("USOIL", "UKOIL", "CAD", "inflation", "US500"), "می‌تواند فشار تورمی را کاهش دهد و به مصرف‌کنندگان کمک کند", "افت نفت ناشی از ضعف تقاضا می‌تواند نشانه نگرانی رشد باشد"),
    Relationship("ضعف رشد چین", ("CNY", "AUDUSD", "NZDUSD", "USOIL", "XAUUSD", "US30", "US500"), "احتمال فشار بر ارزهای وابسته به کالا و کالاها", "میزان اثر به سیاست حمایتی چین و انتظارات قبلی وابسته است"),
    Relationship("بهبود رشد چین", ("CNY", "AUDUSD", "NZDUSD", "USOIL", "XAUUSD", "US30", "US500"), "می‌تواند تقاضای کالاها و ارزهای حساس به چین را تقویت کند", "اگر رشد با محرک واقعی تقاضا همراه باشد؛ واکنش بازار ممکن است قبلاً قیمت‌گذاری شده باشد"),
)

KEYS = {
    "yields_up": ("yield rises", "yields rise", "bond yields rise", "treasury yields rise", "بازده اوراق افزایش", "yield higher"),
    "yields_down": ("yield falls", "yields fall", "bond yields fall", "treasury yields fall", "بازده اوراق کاهش", "yield lower"),
    "usd_up": ("dollar strengthens", "usd strengthens", "dollar rises", "dxy rises", "دلار تقویت", "دلار افزایش"),
    "usd_down": ("dollar weakens", "usd weakens", "dollar falls", "dxy falls", "دلار تضعیف", "دلار کاهش"),
    "risk_off": ("risk-off", "risk aversion", "safe haven", "flight to safety", "ریسک گریزی", "ریسک‌گریزی"),
    "risk_on": ("risk-on", "risk appetite", "risk sentiment improves", "ریسک پذیری", "ریسک‌پذیری"),
    "oil_up": ("oil rises", "oil prices rise", "crude jumps", "oil surges", "نفت افزایش", "نفت بالا"),
    "oil_down": ("oil falls", "oil prices fall", "crude drops", "نفت کاهش", "نفت پایین"),
    "china_weak": ("china slowdown", "china growth slows", "weak china", "چین ضعیف", "رشد چین کاهش"),
    "china_strong": ("china stimulus", "china growth improves", "strong china", "چین تقویت", "رشد چین افزایش"),
}

def analyze_relationships(text):
    """Return relevant relationship notes from text; unknown text returns empty safely."""
    normalized = (text or "").lower()
    matched = []
    for group, phrases in KEYS.items():
        if any(phrase in normalized for phrase in phrases):
            matched.append(group)
    result = []
    for group in matched:
        if group == "yields_up": label = "افزایش بازده اوراق آمریکا"
        elif group == "yields_down": label = "کاهش بازده اوراق آمریکا"
        elif group == "usd_up": label = "دلار قوی"
        elif group == "usd_down": label = "دلار ضعیف"
        elif group == "risk_off": label = "ریسک‌گریزی"
        elif group == "risk_on": label = "ریسک‌پذیری"
        elif group == "oil_up": label = "افزایش قیمت نفت"
        elif group == "oil_down": label = "کاهش قیمت نفت"
        elif group == "china_weak": label = "ضعف رشد چین"
        else: label = "بهبود رشد چین"
        relation = next((r for r in RELATIONSHIPS if r.event == label), None)
        if relation:
            result.append({"event": relation.event, "assets": list(relation.assets), "tendency": relation.tendency, "condition": relation.condition, "confidence": relation.confidence})
    return result

def format_relationships(text):
    notes = analyze_relationships(text)
    if not notes:
        return "🔗 ارتباط بین بازارها: عبارت کلیدی کافی پیدا نشد؛ جهت‌گیری ساخته نشد."
    lines = ["🔗 ارتباط احتمالی بین بازارها (قواعد کلی):"]
    for note in notes:
        lines.append(f"• {note['event']}: {note['tendency']}.")
        lines.append(f"  نمادها/دارایی‌ها: {', '.join(note['assets'])}")
        lines.append(f"  شرط/استثنا: {note['condition']} | اطمینان: {note['confidence']}")
    lines.append("⚠️ روابط احتمالی‌اند؛ همبستگی ثابت یا سیگنال معامله نیستند.")
    return "\n".join(lines)
