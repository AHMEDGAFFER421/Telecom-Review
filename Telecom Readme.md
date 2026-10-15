# Telecom Egypt — Google Play Review Analysis

End-to-end data analysis comparing customer experience across the 4 major 
Egyptian mobile operators using Google Play Store reviews.

**Operators:** Vodafone Egypt · Etisalat Egypt · Orange Egypt · WE Egypt  
**Data:** 1.23M unique reviews (scraped Sept 2026)  
**Stack:** Python (scrape + clean + categorize) → Power BI

---

## Findings

- **WE Egypt is the outlier** — avg rating 2.65 vs Etisalat's 4.34, 
  57% negative reviews, and **0 replies to reviews** across its entire 
  Google Play history.
- **Etisalat is the benchmark** — highest rating, 85% reply rate, 
  95% of replies within 24 hours.
- **App bugs are the top complaint category** across all 4 operators.
- **Vodafone's reply rate (16%) is anomalous** even within the common 
  2022+ window.

## Methodology

- **Analysis window:** cross-operator comparisons use reviews from 
  2022-03-10 onward (898,665 reviews). Vodafone's Play listing only 
  exposes reviews from that date, so comparing full history would be unfair.
- **Categorization:** rule-based, not ML. Keywords cover English, 
  Modern Standard Arabic, Egyptian dialect, and Franco-Arab.
- **Priority flag:** anger/profanity sets a separate priority column 
  instead of deciding category, keeping signals independent.
- **Reply rate:** measured from developer replies visible on Google Play 
  at scrape time.

## Pipeline

    bronze/  →  silver_clean_v5.py  →  silver/reviews_clean.parquet
                                              ↓
                                     Telecom 2.pbix (dashboard)

## Privacy

No personally identifiable information is included. User names, profile 
images, review URLs, and review IDs are dropped. Phone numbers and emails 
inside review text are scrubbed.

## Setup

    pip install -r requirements.txt
    python scrape_operators.py
    python scrape_vodafone_ar.py
    python -X utf8 silver_clean_v5.py
    # then open Telecom 2.pbix in Power BI Desktop

## Screenshots

See `screenshots/` for all 4 dashboard pages.