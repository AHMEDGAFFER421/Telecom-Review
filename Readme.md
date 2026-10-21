# Telecom Egypt: Google Play App Review Analysis

An end-to-end analytics project on **1.23 million Google Play reviews** of the four Egyptian telecom operator apps: **Ana Vodafone, My Etisalat (e&), My Orange and My WE**. It covers scraping, a bronze/silver data pipeline in Python, a star-schema model, and a 4-page Power BI report.

**Question:** How do the four operators compare on customer sentiment, responsiveness and app quality, and where do complaints concentrate?

![Overview](screenshots/01_overview.png)

---

## Key findings

| Operator | Reviews | Avg score | % Negative | Reply rate* |
|---|---|---|---|---|
| My Etisalat | 450,621 | 4.34 | 14% | 85% |
| Ana Vodafone | 400,195 | 4.27 | 15% | 16% |
| My Orange | 188,665 | 3.78 | 28% | 28% |
| My WE | 189,112 | 2.65 | 57% | none recorded |

Table figures cover each operator's full available history (see Limitations). \*Reply rate = reviews with a developer reply visible at scrape time (Sept 2026).

**Like-for-like: reviews from 2022-03-10 onward** (898,665 reviews, the window all four apps share)

| Operator | Reviews | Avg score | % Negative | Reply rate |
|---|---|---|---|---|
| My Etisalat | 277,331 | 4.29 | 15.1% | 89.8% |
| Ana Vodafone | 400,195 | 4.27 | 15.4% | 16.3% |
| My Orange | 98,117 | 3.60 | 33.0% | 40.1% |
| My WE | 123,022 | 2.57 | 59.2% | none recorded |

The ranking is the same on both views. On the shared window, Orange's negative share (33%) is more than double Etisalat's and Vodafone's.

- **WE is the outlier.** Lowest average score (2.65), 57% negative reviews, and no developer replies recorded in the data.
- **Etisalat sets the benchmark.** Highest score and the highest reply rate (about 90% of reviews from 2022 onward). Replies are fast too: over 99% of replies with a recorded timestamp came within 24 hours.
- **Orange replies slowly and selectively.** Roughly 1 in 4 reviews overall (40% since 2022) get a reply, with an average lag of about 1.5 days.
- **Vodafone's reply rate stays low on a like-for-like window.** Reviews from 2022-03-10 onward: Vodafone 16%, Orange 40%, Etisalat 90%.
- **App bugs are the biggest complaint theme.** 27.1% of negative reviews fall in the app-bug category, ahead of network/coverage (11.6%) and billing (7.6%).
- **Release-level bug complaints can be traced.** Bug-related negative reviews spike around specific releases in each app (see the Bug Trends page).

---

## Insights and recommendations

The dashboard is mostly descriptive (what happened) with some diagnostic cuts (where complaints concentrate, which releases spike). It cannot prove cause and effect, so the actions below are hypotheses the data supports, not proven fixes.

| What the data shows | Suggested action |
|---|---|
| **WE is the priority problem.** 57% negative, 2.65 average score, no replies recorded. Its app-bug complaints are 20% of all its reviews (others 10-17%) and network complaints 8.6% (others 3-6%). | Start replying to negative reviews, and triage app stability and network complaints first. |
| **App bugs are the largest complaint category at every operator**, and 27.1% of all negative reviews. | Invest in QA and release monitoring. Watch negative app-bug reviews in the first weeks after each release as an early warning. |
| **Reply coverage varies widely.** Etisalat replies to about 85% of reviews, mostly same-day. Orange replies to 28% with an average 1.5-day lag. Vodafone replies to 16%. | Vodafone and Orange should raise reply coverage, starting with negative reviews, and Orange should shorten its lag. Run it as a pilot: this data cannot show that replying raises scores. |
| **Network complaints show up in app reviews** (11.6% of negative reviews overall). | Route them to the network team as a cheap early-warning signal for coverage problems. |

**What I would do next with more time:**
- Validate the keyword categories against a hand-labelled sample.
- Turn Bug Trends into a rate (bug complaints divided by reviews on that version) so busy releases are not overstated.
- Re-run the operator comparison on the common window only.
- Add sentiment and score by release, not just bug counts.

---

## Recommendations

These come from review data alone, so treat them as hypotheses to test, not proven causes.

| Operator | What the data shows | Recommendation |
|---|---|---|
| My WE | 57% negative, 2.65 avg score, no replies recorded. 20% of its reviews are tagged app-bug, against 10-17% for the others | Fix app stability first, and start replying on Play, beginning with the lowest-rated reviews |
| My Orange | 40% reply rate since 2022 (28% overall), about 1.5 days average lag, 33% negative since 2022 | Reply to negative reviews first and shorten response time. Etisalat shows a high reply rate is achievable |
| Ana Vodafone | Strong score (4.27) but a 16% reply rate that has stayed flat since 2022 | The cheapest win is replying to the roughly 15% of reviews that are negative, not to everything |
| My Etisalat | Best score and reply rate | Keep as the internal benchmark, and investigate the bug-complaint spikes around releases 20 and 22 |
| All four | App bugs are 27.1% of negative reviews, the largest single theme | Watch negative reviews in the weeks after each release, as the Bug Trends page does, and put QA effort there |

**Next steps for the analysis**
- Normalise bug complaints by review volume per release, so the chart shows a rate and not a count.
- Validate the keyword categories on a hand-labelled sample (a few hundred reviews).
- Test whether a developer reply is associated with a higher score (association only; this data cannot prove cause).

---

## Pipeline

```
Google Play (public reviews, country = eg)
        |   google-play-scraper, Arabic + English runs per app
        v
bronze/   raw parquet per run (+ checkpoints every 50 pages)
        |   silver_clean_v5.py
        v
silver/   one cleaned, enriched table (parquet + CSV)
        |   Power Query + DAX
        v
Power BI  star schema + 4-page report
```

**Bronze: scraping.** 200 reviews per page, newest first, following the continuation token with retries on empty pages. Each app is scraped in Arabic and English because the two runs return different review sets. Raw files are kept per run and never overwritten.

**Silver: cleaning and enrichment** (`silver_clean_v5.py`):
- Loads finished bronze files (checkpoints only as a fallback) and fills the operator from the filename.
- Dedupes on `reviewId` (2.47M raw rows to 1.23M unique), preferring rows that carry a reply.
- Drops empty texts, parses dates, and adds derived columns: sentiment group from score, reply flag and reply lag, text length, word count, emoji flag, language, complaint category, anger score and priority, and a common-window flag.
- Language is detected by script: Arabic script is `ar`, Latin text with Arabizi digits is `franco`, other Latin text is `en`.
- Complaint categories are **rule-based keyword matching** (English, Modern Standard Arabic, Egyptian dialect and Arabizi): network/coverage, billing, app bug, customer service. Reviews with no complaint keyword fall into praise, vague-negative or other buckets (short vs. longer). Anger words set a separate priority flag and do not decide the category.

**Model:** `reviews_clean` (fact) with `dim_operator`, `dim_category`, `dim_language` and `dim_date`. Measures are written in DAX (reply rate, negative share, average reply lag, top complaint share and others).

---

## Dashboard pages

| Page | What it shows |
|---|---|
| Overview | KPI cards, per-operator scorecards, volume trend, quick insights, top complaint |
| Trends | Volume, average score, reply rate and negative share by year |
| Responsiveness | Reply rate, negative share, reply lag, quick insights |
| Bug Trends | Negative app-bug reviews by major release, one chart per app |

![Trends](screenshots/02_trends.png)
![Responsiveness](screenshots/03_responsiveness.png)
![Bug Trends](screenshots/04_bug_trends.png)

---

## Limitations (read before quoting numbers)

1. **History differs per operator.** Oldest reviews in the data: Etisalat 2012, Orange 2014, WE 2018, Vodafone March 2022. Operator totals cover each app's available history, so they are not like-for-like. The `in_common_window` flag (reviews from 2022-03-10 onward, 73% of the data) is in the model for fair comparisons, and the like-for-like table above uses it.
2. **Vodafone's history stops at March 2022.** Older Vodafone reviews do exist on the Play Store (checked manually, back to at least 2018), but the scraper's pagination stopped short of them for this app. The cause was not determined.
3. **Reply rate is a snapshot.** It reflects replies visible in Sept 2026, not each operator's historical behaviour. WE shows 0%, meaning no replies recorded. It may simply not reply through Play.
4. **Categories are keyword rules, not a model.** They were not validated against a hand-labelled sample. About 13% of reviews remain in "other", and 52% are short praise with no complaint content.
5. **Bug Trends counts complaints, not rates.** A tall point can mean a version had more users rather than a worse update. About 14% of reviews have no app version and are excluded from that page.
6. **Version numbering differs per app.** Vodafone uses year-style versions (e.g. 2022.3.4); the year is dropped, so release numbers repeat across years. Use the Year filter to isolate one year.
7. **Language detection is approximate** (script-based).
8. **Play Store reviews are self-selected** and do not represent all customers.
9. **2026 is a partial year** (data through September).

---

## Reproduce

```bash
pip install pandas pyarrow google-play-scraper
python scrape_operators.py        # bronze: scrape each app, Arabic and English
python silver_clean_v5.py         # silver: bronze/ -> silver/reviews_clean.*
```

Then open the Power BI file and point the `reviews_clean` query at your `silver/reviews_clean.csv` (the path in Power Query is machine-specific). If you add or remove silver columns, update the column-type list in the query.

**Data is not included** in this repo: the files are several hundred MB and contain public reviewer usernames. Run the scripts to regenerate it.

---

## Repo structure

```
bronze/              (not tracked: raw parquet)
silver/              (not tracked: cleaned output)
scrape_operators.py
silver_clean_v5.py
screenshots/
README.md
```

## Tools

Python (pandas, pyarrow, google-play-scraper), Power Query (M), DAX, Power BI Desktop.

## Author

Your Name · [LinkedIn](#) · [GitHub](#)
