# Telecom Egypt — Google Play Review Analysis

End-to-end data analysis comparing customer experience across the 4 major 
Egyptian mobile operators using Google Play Store reviews.

**Operators:** Vodafone Egypt · Etisalat Egypt · Orange Egypt · WE Egypt  
**Data:** 1.23M unique reviews (scraped Sept 2026)  
**Stack:** Python (scrape + clean + categorize) → Power BI

---

## Key Findings

- **WE Egypt is the outlier** — Avg rating 2.65 vs Etisalat's 4.34. It has the highest volume of negative reviews (57%) and **0 replies to reviews** across its entire Google Play history.
- **Etisalat is the benchmark** — Highest rating, 85% reply rate, and 95% of replies sent within 24 hours.
- **App bugs dominate** — 27% of all complaints across the 4 apps are related to app bugs/crashes (highest in Vodafone and Orange).
- **Vodafone's reply rate (16%) is anomalous** — Even when restricting the data to the same 2022+ window, Vodafone's engagement remains significantly lower than Orange (40%) and Etisalat (85%).

## Methodology & Analytical Decisions

- **Analysis Window:** Cross-operator comparisons use reviews from **2022-03-10 onward** (898,665 reviews). *Reason:* Vodafone's Play Store listing only exposes reviews from that date. Comparing full history (e.g., Etisalat back to 2012) against Vodafone would be unfair. 
- **Categorization:** Rule-based (not ML). Keywords cover English, Modern Standard Arabic, Egyptian dialect, and Franco-Arab. 
- **Priority Flag:** Anger/profanity words (e.g., حرامية, زفت) do not decide the category. Instead, they set a separate `priority` column (`critical`, `angry`, `normal`) to keep the category and sentiment signals independent.
- **Reply Rate:** Measured from developer replies visible on Google Play at the time of scraping.

## Pipeline

```text
bronze/ (raw parquet) → silver_clean_v5.py → silver/ (clean, enriched parquet)
                                                   ↓
                                          Telecom 2.pbix (Dashboard)
