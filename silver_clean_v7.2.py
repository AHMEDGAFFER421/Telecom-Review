"""
Silver layer v7.2: v7.1 + "other" fixes found by auditing 80 "other" reviews.

CHANGELOG vs v7.1
-----------------
P5 (classifier recall/precision, from the "other" audit):
  1. "جدا/جداً/جدآ" (= "very") removed from PRAISE_WORDS. It is an intensifier,
     so "سيئ جدا" matched BOTH praise and negative: long reviews fell to
     "other" and reviews of <=3 words were labelled praise_short.
  2. Arabic clitic prefixes (و، ب، ل، ف، ك، ا، ال، وال، بال، لل) are allowed
     before Arabic keywords of 3+ letters. The v7 word-boundary regex had
     stopped "الرصيد", "وممتازه", "اشحن", "الحراميه" from matching.
  3. Short reviews with BOTH praise and negative cues now return "other"
     (was praise_short).
  4. Emoji-only reviews: positive emoji -> praise_short, negative emoji ->
     vague_negative_short.
  5. Dictionary additions (superlative negatives, praise typos, "انترنت",
     "لايعمل"/"لم يفتح" forms). Original lists are untouched; additions are
     appended in section 1a so the changes stay attributable.

Silver layer v7.1: v7 + app_bug praise guard.

CHANGELOG vs v7
---------------
P4 (classifier fix):
  - fix_app_bug(): reviews labelled app_bug that contain a praise cue and no
    problem cue are relabelled "praise". Cause: generic keywords in the
    app_bug list ("تطبيق", "البرنامج", "el app", "update") made reviews like
    "تطبيق ممتاز" land in app_bug before the praise check ever ran.
    Validated on 178,531 app_bug rows: low-rating share 43.5% -> 74.7%;
    76,524 rows moved to praise (about 3.4% of low-rated app_bug rows get
    rerouted, accepted cost).
  - Dictionary CONTENT is unchanged vs v7.

CHANGELOG vs v6 (carried over from v7)
--------------------------------------
P0 (correctness):
  1. Word-boundary regex for anger/praise/vague-negative.
  2. FRANCO_RE no longer misclassifies 2g/3g/4g/5g as Franco-Arabic.
  3. Praise/vague-negative detection uses the same regex approach.
  4. Missing 'repliedAt' no longer crashes; replied_at is NaT-filled.
  5. NaT review dates dropped BEFORE review_month is computed.
  6. Keyword lists are stripped before weighting.

P1 (method bias):
  7. Rating-only reviews are KEPT, flagged via has_text.
  8. in_common_window policy documented; caller decides.
  9. Category keywords sorted longest-first so multi-word phrases win.

P2 (schema additions):
 10. helpful_count, review_key (sha256), reply_length.

P3 (hygiene):
 11. silver/reviews_raw.parquet — full raw archive for incremental runs.
 12. silver/pipeline_log.json — row counts at every step.
 13. Schema guard at load time.

NOTE: dictionary CONTENT is unchanged vs v6. Fixing the matching logic
exposes what the dictionary can do. Changing both at once would make it
impossible to attribute the shift in results.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import pandas as pd

# Windows consoles default to cp1252 and crash on Arabic / star characters.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---------------------------------------------------------------------------
# 0. PATHS & POLICY
# ---------------------------------------------------------------------------
BRONZE_DIR = Path("bronze")
SILVER_DIR = Path("silver")
SILVER_DIR.mkdir(exist_ok=True)

# in_common_window policy:
#   True = review is in the window where ALL 4 operators have coverage.
# Current setting assumes all 4 operators have Play Store data from 2022-03-10.
# If your data actually starts in 2018 for all 4, change and re-run — this
# shifts every downstream benchmark.
COMMON_START = pd.Timestamp("2022-03-10")

# ---------------------------------------------------------------------------
# 1. KEYWORD DICTIONARIES (verbatim from v6)
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "network_coverage": [
        "network", "signal", "coverage", "no service", "no internet",
        "disconnect", "disconnected", "slow internet", "4g", "5g", "lte",
        "net ", "internet", "offline", "weak signal", "no signal",
        "data", "connection", "reconnect", "dropped call", "call drop",
        "cannot call", "can't call", "no bars", "outage",
        "شبكة", "تغطية", "لا يوجد اتصال", "ضعيف", "إشارة",
        "انقطاع", "الاتصال", "الإنترنت", "بطء", "خدمة الشبكة",
        "نت", "الشبكة", "مفيش نت", "بيقطع", "مفيش تغطية",
        "سيجنال", "مفيش شبكة", "بطيء", "بطئ", "تقيل",
        "النت", "النت فاصل", "النت بيقطع", "النت وحش", "النت زفت",
        "مش لاقي شبكة", "الشبكة فاصلة", "الشبكة ضعيفة", "الشبكة وحشة",
        "مفيش سيغنال", "السيجنال وحش", "مش بيجيب شبكة",
        "بيقطع في المكالمات", "المكالمة بتقطع", "بتفصل لوحدها",
        "الواي فاي", "داتا",
        "مش عارف اتصل", "مش بيرن", "الخط مش بيرن",
        "نقطة حمرا", "الشبكة راحت", "فصلت فجأة", "قاطع النت",
        "مش قادر ادخل نت", "النت واقف", "النت مش موجود",
        "net", "el net", "el shabaka", "mfish net", "mafish net",
        "signaal", "ishara", "beta2ta3", "batee2", "ta2eel",
        "m4 sha8al", "el shabaka da3efa", "m4 byegy shabaka",
    ],
    "billing": [
        "bill", "billing", "charge", "charged", "overcharge", "money",
        "refund", "balance", "credit", "price", "pricing", "expensive",
        "payment", "pay", "paid", "deduct", "deducted", "deduction",
        "package", "plan", "subscription", "renew", "renewal", "top up",
        "top-up", "recharge", "voucher", "invoice", "fee", "fees",
        "cost", "costly", "extra charge", "double charge", "wrong charge",
        "felos", "flous",
        "فلوس", "فاتورة", "خصم", "رصيد", "غالي", "سحب", "دفع", "باقة",
        "اشتراك", "تجديد", "شحن", "سعر", "تكلفة", "استرجاع", "مبلغ",
        "رسوم", "مصاريف", "تحويل", "رصيدي",
        "خصموا", "اتخصم", "بيخصم", "فلوسي", "سحب فلوس",
        "الشحن مش", "غالية", "خصم غلط",
        "خدوا فلوسي", "فلوسي راحت", "اتسحب مني", "خصم زيادة",
        "خصم مكرر", "خصم مرتين", "خصم مش مفهوم",
        "الباقة خلصت بسرعة", "الباقة بتخلص بسرعة", "الباقة غالية",
        "عايز استرجع", "عايز فلوسي", "رجعوا فلوسي", "فلوسي ضاعت",
        "مش عارف الرصيد", "الرصيد مش مظبوط", "الرصيد قل",
        "مش شاحن", "الشحن مش وصل", "شحنت ومش وصل",
        "دفعت ومش", "دفعت زيادة", "حاسبوني غلط",
        "فاتورتي غلط", "الفاتورة غالية", "فاتورة كبيرة",
        "مش بدفع", "مش هادفع",
        "بياخدوا فلوس على الفاضي",
        "felous", "feloos", "floosy", "5asm", "5asmo", "bats5am",
        "ra2eed", "ra2edy", "baka", "sha7n", "sha7net", "ghaly",
        "ghalya", "sa3r", "esta2sa3", "fattora", "fattorty",
    ],
    "app_bug": [
        "crash", "crashes", "crashing", "bug", "buggy", "error", "errors",
        "won't open", "wont open", "not working", "doesn't work",
        "doesnt work", "freeze", "freezes", "frozen", "login", "log in",
        "sign in", "update", "loading", "stuck", "glitch", "glitchy",
        "broken", "fail", "failed", "failure", "slow app", "force close",
        "black screen", "white screen", "spinning", "not responding",
        "تحديث", "لا يعمل", "خطأ", "تعليق", "تطبيق", "تحميل", "دخول",
        "تسجيل", "واجهة", "مشكلة", "عطل", "توقف", "انهيار",
        "مش شغال", "بيهنج", "هنج", "مش بيفتح", "بيقفل", "تسجيل الدخول",
        "معرفش ادخل", "التطبيق مش", "اتقفل", "بيتهنج", "مش راضي يفتح",
        "بيقفل لوحده", "بيعلق", "واقف", "مش بيكمل", "بيفصل",
        "الشاشة سودة", "الشاشة بيضا", "مش بتحمل", "التحميل واقف",
        "مش عارف اسجل", "مش عارف ادخل", "الباسورد مش", "الرقم مش",
        "الابليكيشن", "الابليكشن", "البرنامج",
        "بيطلع ايرور", "ايرور", "فيه مشكلة", "مش مظبوط",
        "بياخد وقت", "مش بيستجيب", "بيوقف فجأة",
        "بعد التحديث", "التحديث بوظ", "التحديث خرب", "من ساعة التحديث",
        "مش بيفتح خالص", "بيقفل فجأة", "بيعمل ريستارت",
        "m4 sha8al", "baihang", "hang", "m4 byfta7", "by2fel",
        "el app", "el application", "el barnameg", "m4 bystgeeb",
        "ba3d el update", "el update bawaz",
    ],
    "customer_service": [
        "support", "customer service", "agent", "complaint", "response",
        "respond", "reply", "replied", "call center", "callcenter",
        "helpline", "hotline", "representative", "rep", "staff",
        "no response", "no reply", "waiting", "ignored", "rude",
        "unhelpful", "useless", "help", "chat", "live chat", "ticket",
        "escalate", "supervisor", "manager", "complained",
        "خدمة عملاء", "دعم", "شكوى", "رد", "الدعم الفني", "موظف",
        "ممثل", "مركز الاتصال", "استجابة", "تجاهل", "مساعدة",
        "خدمة العملاء", "محدش رد", "معلش رد",
        "الشكوى", "اتصلت", "الموظف", "الموظفين", "محدش بيرد",
        "مش بيردوا", "بيتجاهلوني", "مفيش رد", "مستني من امبارح",
        "مستني من زمان", "قولوا هيجوا", "وعدوني", "كذابين",
        "خدمة زفت", "خدمة وحشة", "خدمة سيئة", "موظف وقح",
        "موظف مش محترم", "مش بيساعدوا", "مش عايزين يساعدوا",
        "بحاول اتصل", "مش عارف اوصل", "الخط مشغول",
        "الكول سنتر", "الكولسينتر", "الفرع", "رحت الفرع",
        "في الفرع قالوا", "اتكلمت مع", "كلمت حد", "محدش عبرني",
        "كل شوية احكيلهم", "حكيت المشكلة", "قدمت شكوى",
        "الشكوى مش اتحلت", "مفيش فايدة", "زهقت",
        "هشوف شركة تانية",
        "5edmet 3omala", "el da3m", "ma7adsh rad", "el shakwa",
        "etasalet", "el mowazaf", "el mowazafeen", "m4 byraddo",
        "el call center", "el far3", "ro7t el far3",
        "sakwa", "sha2wa",
    ],
}

PRAISE_WORDS = [
    "ممتاز", "ممتازه", "ممتازة", "جيد", "جيده", "جيدة", "جيدا", "جيداً",
    "جميل", "جميله", "جميلة", "رائع", "رائعه",
    "رائعة", "روعه", "روعة", "مميز", "مميزه", "مميزة", "مفيد", "مفيده",
    "مفيدة", "سهل", "سهله", "سهلة", "تمام", "تحفه", "تحفة", "هايل",
    "هايله", "هايلة", "مقبول", "مقبوله", "ممتعه", "ممتع", "ممتعا",
    "أفضل", "افضل", "أحسن", "احسن", "أحلي", "احلي", "احلى",
    "شكرا", "شكرًا", "شكرا ليكم", "شكرا جزيلا", "تسلموا", "تسلم",
    "ربنا يوفقكم", "ربنا يبارك", "بالتوفيق", "مشكورين", "جزاكم الله",
    "الله ينور", "الله يكرمكم", "برافو", "زى الفل", "زي الفل",
    "عظيم", "عظيمه", "عظيمة", "محترم", "محترمه", "محترمة",
    "نعم", "تم", "اوك", "أوك", "ok", "حلو", "حلوه", "حلوة",
    "سريع", "سريعه", "سريعة", "مريح", "مريحه", "مريحة",
    "كويس", "كويسه", "كويسة", "جامد", "جامده", "جامدة",
    "ظريف", "لطيف", "لطيفه", "لطيفة", "شيك", "بيجنن", "يجنن",
    "هايل جدا", "جميل جدا", "ممتاز جدا", "تحفه بجد",
    "excellent", "great", "good", "perfect", "awesome", "nice", "best",
    "love", "amazing", "thanks", "thank you", "super", "wonderful",
    "fantastic", "helpful", "useful", "easy", "smooth", "fast",
]

VAGUE_NEGATIVE = [
    "سئ", "سيئ", "سيئة", "سيئه", "وحش", "وحشه", "وحشة",
    "زفت", "زفته", "زي الزفت",
    "فاشل", "فاشله", "فاشلة",
    "تعبان", "تعبانه", "تعبانة",
    "رديء", "رديئه", "رديئة",
    "مش حلو", "مش حلوه", "مش كويس", "مش كويسه",
    "مقرف", "مقرفه", "مقرفة",
    "bad", "terrible", "awful", "worst", "trash", "garbage",
    "useless", "horrible", "poor", "disappointing", "shit",
]

ANGER_WORDS = [
    # Thieves / Scams
    "حرامية", "حراميه", "حرامى", "حرامي", "سراق", "سراقين", "سرقوني",
    "سرقة", "بيسرقوا", "بيسرقو", "نصابين", "نصب", "بيستغلوا",

    # Trash / Disgust / Bad Service
    "زفت", "زفتين", "زفتة", "زي الزفت", "خدمة زفت", "نت زفت",
    "خرا", "خراء", "خره", "زي الخرا", "كلام خرا", "خدمة خرا",
    "قرف", "قرفان", "قرفانين", "مقرف", "مقرفة", "قرفوني",
    "عرة", "عار", "عيب", "عيب عليكم", "مش عيب", "حرام عليكم",

    # Animal / Insult (Mild)
    "كلب", "كلاب", "كلبة", "يا كلب", "يا كلاب",
    "حمار", "حمير", "حمارة", "يا حمار", "بهيمة", "بهائم",

    # Failure / Stupidity
    "غبي", "غبية", "أغبياء", "اغبياء", "هبل", "هبلة",
    "مجانين", "مجنون", "اتجننتوا", "انتوا مجانين",
    "فاشلين", "فاشل", "فشلة", "شركة فاشلة", "فشل",
    "زبالة", "زباله", "زي الزبالة", "شركة زبالة",
    "وسخ", "وسخة", "وسخين", "قذر", "قذرة",

    # Threats / Mockery
    "انتم بتضحكوا عليا", "بتضحكوا علينا", "بتنصبوا",
    "هقاضيكم", "هقاضيك", "هشكيكم", "هرفع قضية",

    # Despair / Religion / Anger
    "جهنم", "الله يحرقكم", "حرق دمي", "حرقتوا دمي",
    "يلعن", "يلعنكم", "يلعن ابوكم",
    "طز", "طز فيكم", "خلاص مش قادر",
    "ندمت", "ندمت اني", "غلطة عمري", "خسارة فيكم",
    "حسبي الله", "حسبي الله ونعم الوكيل",
    "الله ياخدكم", "ربنا ينتقم", "ربنا ياخد حقنا",

    # Franco-Arab (Safe versions)
    "7arameya", "7arami", "sara2", "sara2o", "sere2a",
    "zeft", "zft", "5ara", "5ra", "2erf", "2erfan", "mo2ref",
    "kalb", "kalab", "7omar", "7omir", "ghaby", "habal", "magnon",
    "fashal", "zebala", "wes5", "2ather", "taz", "ye3n", "ye3nkom",
    "ha2adykom", "ha2adyk", "hashkekom", "nadamt",
]

# ---------------------------------------------------------------------------
# 1a. v7.2 DICTIONARY ADDITIONS (appended; original lists above are untouched)
# ---------------------------------------------------------------------------
PRAISE_WORDS += [
    "ممتاذ", "متاز", "فوق الممتاز", "فوق الامتياز", "امتياز", "الامتياز",
    "اجمل", "أجمل", "فخم", "فخمه", "فخمة", "متميز", "متميزه", "راءع",
    "كوويس", "فريده", "فريدة", "اقوي", "أقوى", "اقوى",
    "عاجبني", "عجبني", "يعجبني",
]
VAGUE_NEGATIVE += [
    "اسوأ", "أسوأ", "اسوا", "اوسخ", "أوسخ", "بقرف", "خري", "قبيحه", "قبيحة",
    "قبيح", "غير مرضيه", "غير مرضية", "غير مرضي", "ميستحقش", "مايستهل",
    "مايستحق", "يستاهل صفر", "عاطل", "محبط",
]
ANGER_WORDS += ["حرمية", "حرميه", "الحراميه"]
CATEGORY_KEYWORDS["app_bug"] += [
    "لايعمل", "لا يفتح", "لايفتح", "لم يفتح", "مش عاوز يفتح", "مش عاوز يشتغل",
    "مش عايز يفتح", "مش عايز يشتغل", "لا يستجيب", "لايستجيب", "مبيشتغلش",
]
CATEGORY_KEYWORDS["network_coverage"] += ["انترنت", "إنترنت"]

POS_EMOJI_RE = re.compile("[👍❤♥😍😘😙💪🌹😊🥰😉💕🔥👏😁😃🙏🤩😎💯👌✨]")
NEG_EMOJI_RE = re.compile("[😡😠🤬👎😤😒💩🤮]")

# ---------------------------------------------------------------------------
# 1b. APP_BUG PRAISE GUARD (v7.1)
# "تطبيق" / "البرنامج" / "el app" are generic words, so praise like
# "تطبيق ممتاز" was landing in app_bug. If a review in app_bug has a praise
# cue and no problem cue, relabel it as praise.
# Validated on 178K rows: app_bug low-rating share 43.5% -> 74.7%.
# Known limits: ~3.4% of low-rated app_bug rows get rerouted; "تحديث" and
# "مش " are noisy problem cues (they also appear in positive reviews).
# ---------------------------------------------------------------------------
APP_PRAISE_CUES = [
    "ممتاز", "رائع", "جميل", "جيد", "احسن", "افضل", "احلي", "احلى", "اجمل",
    "مميز", "حلو", "روعه", "محترم", "مفيد", "شكرا", "سهل",
]
APP_PROBLEM_CUES = [
    "لا يعمل", "مش شغال", "مش بيفتح", "لا يفتح", "بيعلق", "يعلق", "مشكل",
    "بطيء", "بطئ", "خطأ", "خطا", "error", "crash", "not working", "تسجيل",
    "بيهنج", "هنج", "فاشل", "سئ", "سيء", "سيئ", "زباله", "زفت", "وحش",
    "تحديث", "التحديث", "مش ",
    "لايعمل", "لم يفتح", "لايفتح", "لا يستجيب", "لايستجيب", "مبيشتغلش",
]


def fix_app_bug(text: str, cat: str) -> str:
    if cat != "app_bug":
        return cat
    t = str(text)
    if any(w in t for w in APP_PRAISE_CUES) and not any(w in t for w in APP_PROBLEM_CUES):
        return "praise"
    return cat


# ---------------------------------------------------------------------------
# 2. REGEX & NORMALIZATION
# ---------------------------------------------------------------------------
ARABIC_RE   = re.compile(r"[\u0600-\u06FF]")
WORD_RE     = re.compile(r"[\u0600-\u06FFa-z0-9]+")
EMOJI_RE    = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+")
_HARAKAT_RE = re.compile(r"[\u064B-\u0652\u0640]")
_ELONG_RE   = re.compile(r"(.)\1{2,}")
FRANCO_RE   = re.compile(r"[a-z]*[23745][a-z]*", re.IGNORECASE)
FRANCO_EXCLUDE = {"2g", "3g", "4g", "5g", "2gb", "3gb", "4gb", "5gb"}

PHONE_RE    = re.compile(r"(\+?20|0)?1[0125]\d{8}")
EMAIL_RE    = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
LONG_NUM_RE = re.compile(r"\b\d{10,}\b")

# Boundary class for word-boundary wrapping: Arabic block + Latin + digits
_BOUND = r"\u0600-\u06FFa-zA-Z0-9"


def normalize_ar(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = _HARAKAT_RE.sub("", text)
    t = re.sub(r"[إأآا]", "ا", t)
    t = re.sub(r"[ىي]", "ي", t)
    t = re.sub(r"[ةه]", "ه", t)
    t = _ELONG_RE.sub(r"\1", t)
    return t.lower()


_PREFIXES = "وال|بال|لل|ال|و|ب|ل|ف|ك|ا"


def _build_kw_regex(keywords):
    """Word-boundary regex, longest keywords first. Arabic keywords of 3+
    letters may carry one clitic prefix (و/ب/ل/ف/ك/ا/ال...). Group 1 is
    always the keyword itself (prefix excluded)."""
    cleaned = sorted(
        {normalize_ar(kw).strip() for kw in keywords if kw and kw.strip()},
        key=len, reverse=True,
    )
    if not cleaned:
        return None
    all_alt  = "|".join(map(re.escape, cleaned))
    pref_alt = "|".join(re.escape(k) for k in cleaned
                        if ARABIC_RE.match(k) and len(k) >= 3)
    if pref_alt:
        prefix_part = rf"(?:(?:{_PREFIXES})(?=(?:{pref_alt})(?![{_BOUND}])))?"
    else:
        prefix_part = ""
    pattern = rf"(?<![{_BOUND}]){prefix_part}({all_alt})(?![{_BOUND}])"
    return re.compile(pattern, re.IGNORECASE)


CATEGORY_REGEX  = {cat: _build_kw_regex(kws) for cat, kws in CATEGORY_KEYWORDS.items()}
ANGER_REGEX     = _build_kw_regex(ANGER_WORDS)
PRAISE_REGEX    = _build_kw_regex(PRAISE_WORDS)
VAGUE_NEG_REGEX = _build_kw_regex(VAGUE_NEGATIVE)


def _kw_weight(kw: str) -> int:
    if " " in kw.strip():
        return 3
    if len(kw.strip()) > 3:
        return 2
    return 1


def detect_language(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unknown"
    if ARABIC_RE.search(text):
        return "ar"
    tokens = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", text)}
    if any(FRANCO_RE.fullmatch(t) and t not in FRANCO_EXCLUDE for t in tokens):
        return "franco"
    return "en"


def categorize(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "other"
    text_norm = normalize_ar(text)
    # v7.2: emoji-only reviews (no letters/digits at all)
    if not WORD_RE.search(text_norm):
        if POS_EMOJI_RE.search(text) and not NEG_EMOJI_RE.search(text):
            return "praise_short"
        if NEG_EMOJI_RE.search(text) and not POS_EMOJI_RE.search(text):
            return "vague_negative_short"
        return "other"
    scores = {}
    for cat, rx in CATEGORY_REGEX.items():
        if rx is None:
            continue
        matches = {m.group(1) for m in rx.finditer(text_norm)}
        if matches:
            scores[cat] = sum(_kw_weight(m) for m in matches)
    if scores:
        # Tie-break: highest score; on equal score, declaration order.
        return max(scores.items(),
                   key=lambda kv: (kv[1], -list(CATEGORY_KEYWORDS).index(kv[0])))[0]

    word_count = len(text.split())
    is_positive = bool(PRAISE_REGEX.search(text_norm))    if PRAISE_REGEX    else False
    is_negative = bool(VAGUE_NEG_REGEX.search(text_norm)) if VAGUE_NEG_REGEX else False
    if word_count <= 3:
        if is_positive and not is_negative: return "praise_short"
        if is_negative and not is_positive: return "vague_negative_short"
        return "other"   # v7.2: both cues (or none) -> other, not praise_short
    if is_positive and not is_negative: return "praise"
    if is_negative and not is_positive: return "vague_negative"
    return "other"


def anger_score(text: str) -> int:
    if not isinstance(text, str) or not text.strip() or ANGER_REGEX is None:
        return 0
    matches = {m.group(1) for m in ANGER_REGEX.finditer(normalize_ar(text))}
    return sum(_kw_weight(m) for m in matches)


def priority_from_anger(score: int) -> str:
    if score >= 4: return "critical"
    if score >= 1: return "angry"
    return "normal"


def clean_text(t):
    if not isinstance(t, str): return None
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else None


def scrub_pii(text: str) -> str:
    if not isinstance(text, str): return text
    text = PHONE_RE.sub("[phone]", text)
    text = EMAIL_RE.sub("[email]", text)
    text = LONG_NUM_RE.sub("[number]", text)
    return text


# ---------------------------------------------------------------------------
# 3. LOAD
# ---------------------------------------------------------------------------
def load_all_data(log):
    frames = []
    raw_archive = SILVER_DIR / "reviews_raw.parquet"
    legacy      = SILVER_DIR / "reviews_clean.parquet"

    if raw_archive.exists():
        print(f"Loading raw archive: {raw_archive.name}")
        frames.append(pd.read_parquet(raw_archive))
    elif legacy.exists():
        print(f"Loading legacy clean data (one-time migration): {legacy.name}")
        df = pd.read_parquet(legacy)
        if "at" not in df.columns and "review_at" in df.columns:
            print("  WARNING: 'at' missing in legacy — falling back to 'review_at'")
            df["at"] = df["review_at"]
        frames.append(df)

    for f in BRONZE_DIR.glob("reviews_*_eg_*.parquet"):
        if "checkpoint" in f.name or "reviews_all_" in f.name:
            continue
        print(f"Loading bronze: {f.name}")
        df = pd.read_parquet(f)
        m = re.search(r"reviews_(.+?)_eg", f.name)
        if m:
            op = m.group(1)
            if "operator" in df.columns:
                df["operator"] = df["operator"].fillna(op)
            else:
                df["operator"] = op
        frames.append(df)

    if not frames:
        raise FileNotFoundError("No data found in bronze/ or silver/")

    df = pd.concat(frames, ignore_index=True)

    required = {"reviewId", "content", "score", "at"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required raw columns: {missing}")

    log.append({"step": "loaded_raw", "rows": int(len(df))})
    print(f"  loaded_raw: {len(df):,} rows")
    return df


# ---------------------------------------------------------------------------
# 4. DEDUP
# ---------------------------------------------------------------------------
def dedup(df, log):
    df = df.copy()
    before = len(df)
    if "repliedAt" in df.columns:
        df["_has_reply_raw"] = df["repliedAt"].notna()
    else:
        df["_has_reply_raw"] = False
    df = df.sort_values("_has_reply_raw", ascending=False, kind="stable")
    df = df.drop_duplicates(subset="reviewId", keep="first")
    df = df.drop(columns=["_has_reply_raw"])
    log.append({"step": "dedup", "before": int(before), "after": int(len(df)),
                "dropped": int(before - len(df))})
    print(f"  dedup: dropped {before - len(df):,} (kept {len(df):,})")
    return df


# ---------------------------------------------------------------------------
# 5. ENRICH
# ---------------------------------------------------------------------------
DERIVED_COLS = {
    "review_at", "replied_at", "review_month", "in_common_window", "is_future_dated",
    "sentiment_group", "has_reply", "reply_lag_days", "reply_length",
    "text_length", "word_count", "has_emoji", "language",
    "anger_score", "priority", "complaint_category",
    "app_version", "app_version_short",
    "has_text", "helpful_count", "review_key",
}


def enrich(df, log):
    df = df.copy()

    # ---- Dates ----
    df["review_at"] = pd.to_datetime(df["at"], errors="coerce", utc=True).dt.tz_localize(None)
    before = len(df)
    df = df[df["review_at"].notna()]
    log.append({"step": "drop_invalid_dates", "before": int(before), "after": int(len(df)),
                "dropped": int(before - len(df))})
    print(f"  drop_invalid_dates: dropped {before - len(df):,}")

    if "repliedAt" in df.columns:
        df["replied_at"] = pd.to_datetime(df["repliedAt"], errors="coerce", utc=True).dt.tz_localize(None)
    else:
        df["replied_at"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

    df["review_month"]     = df["review_at"].dt.to_period("M").astype(str)
    df["in_common_window"] = df["review_at"] >= COMMON_START
    df["is_future_dated"]  = df["review_at"] > pd.Timestamp.now()

    # ---- Text presence (keeps rating-only reviews) ----
    df["has_text"] = df["content"].notna() & df["content"].astype(str).str.strip().ne("")
    df["content"]  = df["content"].fillna("").apply(clean_text).fillna("").apply(scrub_pii)

    # ---- Sentiment ----
    df["score"] = pd.to_numeric(df["score"], errors="coerce")

    def bucket(s):
        if pd.isna(s): return None
        return "negative" if s <= 2 else ("neutral" if s == 3 else "positive")

    df["sentiment_group"] = df["score"].map(bucket)

    # ---- Replies ----
    reply = df.get("replyContent")
    df["has_reply"] = (reply.notna() & reply.astype(str).str.strip().ne("")) if reply is not None else False
    df["reply_lag_days"] = (df["replied_at"] - df["review_at"]).dt.days
    df.loc[df["reply_lag_days"] < 0, "reply_lag_days"] = pd.NA
    df["reply_length"] = reply.astype(str).str.len().where(reply.notna(), 0).astype(int) if reply is not None else 0

    # ---- Text features ----
    df["text_length"] = df["content"].str.len()
    df["word_count"]  = df["content"].str.split().str.len().fillna(0).astype(int)
    df["has_emoji"]   = df["content"].apply(lambda x: bool(EMOJI_RE.search(x)) if isinstance(x, str) and x else False)
    df["language"]    = df["content"].apply(detect_language)

    # ---- Anger + priority ----
    # NOTE: some ANGER_WORDS (حرامية, سرقوني, نصابين) overlap billing keywords,
    # so "billing reviews are angrier" is partly a dictionary artifact.
    df["anger_score"] = df["content"].apply(anger_score)
    df["priority"]    = df["anger_score"].apply(priority_from_anger)

    # ---- Category ----
    df["complaint_category"] = df["content"].apply(categorize)
    # v7.1: praise guard for generic "app" words landing in app_bug
    df["complaint_category"] = [
        fix_app_bug(t, c) for t, c in zip(df["content"], df["complaint_category"])
    ]
    mask = (df["complaint_category"] == "other") & (df["anger_score"] >= 1)
    df.loc[mask, "complaint_category"] = "angry_other"

    # ---- App version ----
    ver_col = next((c for c in ["reviewCreatedVersion", "appVersion", "version"] if c in df.columns), None)
    if ver_col:
        df["app_version"] = df[ver_col].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        df["app_version_short"] = df["app_version"].apply(
            lambda v: f"{v.split('.')[0]}.{v.split('.')[1]}" if pd.notna(v) and "." in str(v) else v
        )
        print(f"  app_version coverage: {df['app_version'].notna().mean():.1%}")
    else:
        df["app_version"]       = pd.NA
        df["app_version_short"] = pd.NA
        print("  app_version: no version column found")

    # ---- Helpful count ----
    if "thumbsUpCount" in df.columns:
        df["helpful_count"] = pd.to_numeric(df["thumbsUpCount"], errors="coerce").fillna(0).astype(int)
    else:
        df["helpful_count"] = 0

    # ---- Review key (stable, non-reversible) ----
    df["review_key"] = df["reviewId"].astype(str).map(
        lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
    )

    return df


# ---------------------------------------------------------------------------
# 6. SAVE
# ---------------------------------------------------------------------------
def save_raw_archive(df):
    raw_cols = [c for c in df.columns if c not in DERIVED_COLS]
    df[raw_cols].to_parquet(SILVER_DIR / "reviews_raw.parquet", index=False)
    print(f"  raw archive: {len(df):,} rows × {len(raw_cols)} cols")


def save_outputs(df):
    public_cols = [
        "operator", "score", "review_at", "review_month", "in_common_window",
        "is_future_dated", "sentiment_group", "has_reply", "reply_lag_days",
        "reply_length", "text_length", "word_count", "has_emoji", "language",
        "anger_score", "priority", "complaint_category",
        "app_version", "app_version_short",
        "has_text", "helpful_count", "review_key",
    ]
    private_cols = public_cols + ["reviewId", "content"]

    public_cols  = [c for c in public_cols  if c in df.columns]
    private_cols = [c for c in private_cols if c in df.columns]

    df[public_cols].to_parquet(SILVER_DIR / "reviews_public.parquet", index=False)
    df[public_cols].to_csv(SILVER_DIR / "reviews_public.csv", index=False, encoding="utf-8-sig")
    df[private_cols].to_parquet(SILVER_DIR / "reviews_private.parquet", index=False)

    print(f"  public:  {len(df):,} rows × {len(public_cols)} cols")
    print(f"  private: {len(df):,} rows × {len(private_cols)} cols")


# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------
def main():
    log = []
    print("Starting v7.2 pipeline...")
    df = load_all_data(log)
    df = dedup(df, log)

    save_raw_archive(df)   # save raw BEFORE enrich so re-runs are safe
    df = enrich(df, log)
    save_outputs(df)

    with open(SILVER_DIR / "pipeline_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print("  log: silver/pipeline_log.json")


if __name__ == "__main__":
    main()
