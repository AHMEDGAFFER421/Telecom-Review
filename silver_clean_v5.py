"""
Silver layer v5: FINAL clean + enrich for the 4-operator telecom project.

WHAT'S NEW VS v4
----------------
  * 'other' bucket split by LENGTH + SENTIMENT:
        praise_short        <= 3 words, positive
        vague_negative_short <= 3 words, negative
        other               everything else (true catch-all)
    This drops 'other' from ~27% to <5% because short one-word reviews
    genuinely have no complaint content to match against.
  * Expanded PRAISE and VAGUE_NEGATIVE lists based on the actual top-40
    contents that were sitting in 'other' (جيد، كويس، جامد، روعه، هايل،
    سئ، سيئ، وحش، ...).
  * Report now notes that reply-rate is a scrape-time measurement.

ANALYTICAL DECISIONS BAKED IN
-----------------------------
  * Cross-operator comparisons filter to review_at >= 2022-03-10
    (in_common_window). Vodafone's oldest Play review is 2022-03-10, so
    comparing 2012 Etisalat reviews to 2022 Vodafone reviews is unfair.
  * Categories are rule-based, English + MSA + Egyptian dialect + Franco.
  * Anger words DO NOT decide category; they set priority (angry/critical).

INSTALL:  pip install pandas pyarrow
RUN:      python -X utf8 silver_clean_v5.py
"""

from pathlib import Path
import re

import pandas as pd

BRONZE_DIR = Path("bronze")
SILVER_DIR = Path("silver")
SILVER_DIR.mkdir(exist_ok=True)

COMMON_START = pd.Timestamp("2022-03-10")

# ---------------------------------------------------------------------------
# CATEGORY KEYWORDS  (only real complaints - praise/vague go elsewhere)
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

# ---------------------------------------------------------------------------
# PRAISE  (positive sentiment -> praise / praise_short, NOT a complaint)
# ---------------------------------------------------------------------------
PRAISE_WORDS = [
    # MSA
    "ممتاز", "ممتازه", "ممتازة", "جيد", "جيده", "جيدة", "جيدا", "جيداً",
    "جدا", "جداً", "جدآ", "جميل", "جميله", "جميلة", "رائع", "رائعه",
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
    # Egyptian dialect
    "كويس", "كويسه", "كويسة", "جامد", "جامده", "جامدة",
    "ظريف", "لطيف", "لطيفه", "لطيفة", "شيك", "بيجنن", "يجنن",
    "هايل جدا", "جميل جدا", "ممتاز جدا", "تحفه بجد",
    # English
    "excellent", "great", "good", "perfect", "awesome", "nice", "best",
    "love", "amazing", "thanks", "thank you", "super", "wonderful",
    "fantastic", "helpful", "useful", "easy", "smooth", "fast",
]

# ---------------------------------------------------------------------------
# VAGUE NEGATIVE  (bad sentiment, no specific complaint category)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# ANGER (sets priority only, not category)
# ---------------------------------------------------------------------------
ANGER_WORDS = [
    "حرامية", "حراميه", "حرامى", "حرامي", "سراق", "سراقين", "سرقوني",
    "سرقة", "بيسرقوا", "بيسرقو", "نصابين", "نصب", "بيستغلوا",
    "زفت", "زفتين", "زفتة", "زي الزفت", "خدمة زفت", "نت زفت",
    "خرا", "خراء", "خره", "زي الخرا", "كلام خرا", "خدمة خرا",
    "قرف", "قرفان", "قرفانين", "مقرف", "مقرفة", "قرفوني",
    "عرة", "عار", "عيب", "عيب عليكم", "مش عيب", "حرام عليكم",
    "كسم", "كسمكم", "كس", "كسمك",
    "متناك", "متناكة", "عرص", "عرصة",
    "كلب", "كلاب", "كلبة", "يا كلب", "يا كلاب",
    "حمار", "حمير", "حمارة", "يا حمار", "بهيمة", "بهائم",
    "غبي", "غبية", "أغبياء", "اغبياء", "هبل", "هبلة",
    "مجانين", "مجنون", "اتجننتوا", "انتوا مجانين",
    "فاشلين", "فاشل", "فشلة", "شركة فاشلة", "فشل",
    "زبالة", "زباله", "زي الزبالة", "شركة زبالة",
    "وسخ", "وسخة", "وسخين", "قذر", "قذرة",
    "انتم بتضحكوا عليا", "بتضحكوا علينا", "بتنصبوا",
    "هقاضيكم", "هقاضيك", "هشكيكم", "هرفع قضية",
    "جهنم", "الله يحرقكم", "حرق دمي", "حرقتوا دمي",
    "يلعن", "يلعنكم", "يلعن ابوكم",
    "طز", "طز فيكم", "خلاص مش قادر",
    "ندمت", "ندمت اني", "غلطة عمري", "خسارة فيكم",
    "حسبي الله", "حسبي الله ونعم الوكيل",
    "الله ياخدكم", "ربنا ينتقم", "ربنا ياخد حقنا",
    "7arameya", "7arami", "sara2", "sara2o", "sere2a",
    "zeft", "zft", "5ara", "5ra", "2erf", "2erfan", "mo2ref",
    "kosom", "kosomko", "metnak", "3ars", "kalb", "kalab",
    "7omar", "7omir", "ghaby", "habal", "magnon", "fashal",
    "zebala", "wes5", "2ather", "taz", "ye3n", "ye3nkom",
    "ha2adykom", "ha2adyk", "hashkekom", "nadamt",
]

# ---------------------------------------------------------------------------
# Regexes + normalization
# ---------------------------------------------------------------------------
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
WORD_RE = re.compile(r"[\u0600-\u06FFa-z0-9]+")
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+"
)
_HARAKAT_RE = re.compile(r"[\u064B-\u0652\u0640]")
_ELONG_RE = re.compile(r"(.)\1{2,}")
FRANCO_RE = re.compile(r"[a-z]*[23745][a-z]*", re.IGNORECASE)


def normalize_ar(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = _HARAKAT_RE.sub("", text)
    t = re.sub(r"[إأآا]", "ا", t)
    t = re.sub(r"[ىي]", "ي", t)
    t = re.sub(r"[ةه]", "ه", t)
    t = _ELONG_RE.sub(r"\1", t)
    return t.lower()


CATEGORY_KEYWORDS_NORM = {
    cat: [normalize_ar(kw) for kw in kws]
    for cat, kws in CATEGORY_KEYWORDS.items()
}
ANGER_WORDS_NORM    = [normalize_ar(w) for w in ANGER_WORDS]
PRAISE_NORM         = [normalize_ar(w) for w in PRAISE_WORDS]
VAGUE_NEG_NORM      = [normalize_ar(w) for w in VAGUE_NEGATIVE]


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
def detect_language(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unknown"
    if ARABIC_RE.search(text):
        return "ar"
    if FRANCO_RE.search(text):
        return "franco"
    return "en"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _kw_weight(kw: str) -> int:
    if " " in kw:
        return 3
    if len(kw) > 3:
        return 2
    return 1


def _kw_matches(kw: str, text_norm: str, words: set) -> bool:
    if len(kw) <= 3 and " " not in kw:
        return kw in words
    return kw in text_norm


def categorize(text: str) -> str:
    """Complaint category if any keyword fires, otherwise praise / vague / other,
    with a short-text refinement."""
    if not isinstance(text, str) or not text.strip():
        return "other"

    text_norm = normalize_ar(text)
    words = set(WORD_RE.findall(text_norm))

    scores = {}
    for cat, kws in CATEGORY_KEYWORDS_NORM.items():
        s = sum(_kw_weight(kw) for kw in kws if _kw_matches(kw, text_norm, words))
        if s:
            scores[cat] = s

    if scores:
        return max(scores.items(),
                   key=lambda kv: (kv[1], -list(CATEGORY_KEYWORDS).index(kv[0])))[0]

    # no complaint keyword fired -> soft buckets
    word_count = len(text.split())
    is_positive = any(w in text_norm for w in PRAISE_NORM)
    is_negative = any(w in text_norm for w in VAGUE_NEG_NORM)

    if word_count <= 3:
        if is_positive and not is_negative:
            return "praise_short"
        if is_negative and not is_positive:
            return "vague_negative_short"
        # mixed/ambiguous short -> vague
        if is_positive or is_negative:
            return "praise_short" if is_positive else "vague_negative_short"

    if is_positive and not is_negative:
        return "praise"
    if is_negative and not is_positive:
        return "vague_negative"
    return "other"


def anger_score(text: str) -> int:
    if not isinstance(text, str) or not text.strip():
        return 0
    t = normalize_ar(text)
    return sum(_kw_weight(w) for w in ANGER_WORDS_NORM if w in t)


def priority_from_anger(score: int) -> str:
    if score >= 4:
        return "critical"
    if score >= 1:
        return "angry"
    return "normal"


def clean_text(t):
    if not isinstance(t, str):
        return None
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else None


# ---------------------------------------------------------------------------
# LOAD
# ---------------------------------------------------------------------------
def load_bronze() -> pd.DataFrame:
    finished = {
        f.name.replace(".parquet", ""): f
        for f in BRONZE_DIR.glob("reviews_*_eg_*.parquet")
        if "checkpoint" not in f.name and "reviews_all_" not in f.name
    }
    checkpoints = {
        f.name.replace("_checkpoint.parquet", ""): f
        for f in BRONZE_DIR.glob("reviews_*_eg_*_checkpoint.parquet")
        if "reviews_all_" not in f.name
    }
    to_load = dict(checkpoints)
    to_load.update(finished)

    if not to_load:
        raise FileNotFoundError(f"No bronze files in {BRONZE_DIR.resolve()}")

    print("Loading bronze files:")
    frames = []
    for name, f in sorted(to_load.items()):
        df = pd.read_parquet(f)
        tag = "checkpoint" if "checkpoint" in f.name else "final"
        op = re.match(r"reviews_(.+?_eg)_", f.name).group(1)
        if "operator" in df.columns:
            df["operator"] = df["operator"].fillna(op)
        else:
            df["operator"] = op
        print(f"  {f.name} [{tag}]: {len(df):,} rows")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# CLEAN + ENRICH
# ---------------------------------------------------------------------------
def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # dedup: prefer rows that have a reply
    df["_has_reply_raw"] = (
        df["repliedAt"].notna() if "repliedAt" in df.columns else False
    )
    df["_has_text_raw"] = df["content"].notna() if "content" in df.columns else False
    df = df.sort_values(["_has_reply_raw", "_has_text_raw"], ascending=False)
    before = len(df)
    df = df.drop_duplicates(subset="reviewId", keep="first")
    print(f"\nDuplicates removed: {before - len(df):,} "
          f"(kept {len(df):,} unique reviews)")
    df = df.drop(columns=["_has_reply_raw", "_has_text_raw"])

    # drop empty text
    df["content"] = df["content"].apply(clean_text)
    before = len(df)
    df = df[df["content"].notna()]
    print(f"Empty texts dropped: {before - len(df):,}")

    # dates
    df["review_at"] = pd.to_datetime(df["at"], errors="coerce", utc=True).dt.tz_localize(None)
    df["replied_at"] = pd.to_datetime(df.get("repliedAt"), errors="coerce", utc=True).dt.tz_localize(None)
    df["review_month"] = df["review_at"].dt.to_period("M").astype(str)
    df["in_common_window"] = df["review_at"] >= COMMON_START
    df["is_future_dated"] = df["review_at"] > pd.Timestamp.now()

    # score -> sentiment
    def bucket(s):
        if pd.isna(s):
            return None
        return "negative" if s <= 2 else ("neutral" if s == 3 else "positive")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["sentiment_group"] = df["score"].map(bucket)

    # replies
    reply = df.get("replyContent")
    df["has_reply"] = (reply.notna()
                       & reply.astype(str).str.strip().ne("")) if reply is not None else False
    df["reply_lag_days"] = (df["replied_at"] - df["review_at"]).dt.days
    df.loc[df["reply_lag_days"] < 0, "reply_lag_days"] = pd.NA

    # features
    df["text_length"] = df["content"].str.len()
    df["word_count"] = df["content"].str.split().str.len()
    df["has_emoji"] = df["content"].fillna("").str.contains(EMOJI_RE, regex=True)

    # language
    df["language"] = df["content"].apply(detect_language)

    # anger + priority
    df["anger_score"] = df["content"].apply(anger_score)
    df["priority"] = df["anger_score"].apply(priority_from_anger)

    # category (final)
    df["complaint_category"] = df["content"].apply(categorize)

    # angry_other: uncategorized 'other' with anger -> angry_other
    mask = (df["complaint_category"] == "other") & (df["anger_score"] >= 1)
    df.loc[mask, "complaint_category"] = "angry_other"

    return df


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------
def report(df: pd.DataFrame) -> None:
    print("\n================ DATA QUALITY REPORT ================")
    print(f"Total unique reviews : {len(df):,}")
    print(f"Date range           : {df['review_at'].min()} -> {df['review_at'].max()}")
    print(f"In common window (>= {COMMON_START.date()}): "
          f"{df['in_common_window'].sum():,} "
          f"({df['in_common_window'].mean()*100:.1f}%)")

    print("\nReviews per operator:")
    print(df["operator"].value_counts().to_string())

    print("\nAvg score per operator:")
    print(df.groupby("operator")["score"].mean().round(2).to_string())

    print("\nLanguage split:")
    print(df["language"].value_counts().to_string())

    print("\nComplaint categories (all reviews):")
    vc = df["complaint_category"].value_counts()
    pct = (vc / len(df) * 100).round(1)
    print(pd.DataFrame({"count": vc, "pct": pct}).to_string())

    print("\nCategory x operator (% within operator):")
    print(pd.crosstab(df["operator"], df["complaint_category"], normalize="index")
            .mul(100).round(1).to_string())

    print("\nPriority split:")
    print(df["priority"].value_counts().to_string())

    print("\nReply rate per operator (all data) [scrape-time measurement]:")
    print(df.groupby("operator")["has_reply"].mean().mul(100).round(1)
            .astype(str).add("%").to_string())

    print("\nSAME as above, restricted to common window:")
    recent = df[df["in_common_window"]]
    print(recent.groupby("operator")["has_reply"].mean().mul(100).round(1)
            .astype(str).add("%").to_string())

    print("======================================================\n")


def main() -> None:
    df = load_bronze()
    print(f"\nRaw rows loaded: {len(df):,}")
    df = clean(df)
    report(df)

    pq = SILVER_DIR / "reviews_clean.parquet"
    df.to_parquet(pq, index=False)
    csv = SILVER_DIR / "reviews_clean.csv"
    df.to_csv(csv, index=False, encoding="utf-8-sig")

    print(f"Silver v5 saved -> {pq}  ({len(df):,} rows, {len(df.columns)} cols)")
    print(f"                -> {csv}")


if __name__ == "__main__":
    main()