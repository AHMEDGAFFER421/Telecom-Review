"""
Bronze-layer scraper: pulls ALL available Google Play reviews for a set of
telecom operator apps. No row cap - it walks the real pagination token Google
uses internally, so you get the full review history the app has, not a
truncated top-N sample.

pip install google-play-scraper pandas pyarrow

Usage:
    python scrape_telecom_reviews.py

Output:
    bronze/reviews_<app_label>_<YYYYMMDD>.parquet   (one file per app)
    bronze/reviews_all_<YYYYMMDD>.parquet           (combined)
"""

import time
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

# ---------------------------------------------------------------------------
# 1. CONFIG - fill in the apps you want. Vodafone Egypt's is confirmed below.
#    For the others, open the app's Play Store page in a browser and copy the
#    id= value from the URL, e.g.
#    https://play.google.com/store/apps/details?id=com.orange.egypt.myorange
#                                                    ^^^^^^^^^^^^^^^^^^^^^^^^
#    That string is what goes here. Takes 2 minutes for all four.
# ---------------------------------------------------------------------------
APPS = {
    # "vodafone_eg": "com.emeint.android.myservices",  # DONE - 164,400 rows scraped already
    "orange_eg": "com.orange.mobinilandme",
    "etisalat_eg": "com.etisalat",
    "we_eg": "com.ucare.we",
}

LANG = "en"       # switched from "ar" - orange/etisalat/we returned empty for arabic
COUNTRY = "eg"
BATCH_SIZE = 200  # max per request the library exposes
SLEEP_RANGE = (1.0, 2.5)  # polite delay between pages, avoids throttling

OUT_DIR = Path("bronze")
OUT_DIR.mkdir(exist_ok=True)


MAX_PAGES_PER_APP = 2000     # hard safety cap (400k reviews) - stops runaway loops
CHECKPOINT_EVERY = 50        # pages between partial saves, so nothing is lost


def scrape_all_reviews(app_id: str, lang: str, country: str, label: str, today: str) -> list[dict]:
    """Pull every review available for one app/lang/country combo.

    Stops on: no results, no continuation token, duplicate reviews showing up
    (proof the token looped), or the hard page cap. Saves a checkpoint file
    every CHECKPOINT_EVERY pages so a Ctrl+C or crash doesn't lose progress.
    """
    all_reviews = []
    seen_ids = set()
    token = None
    page = 0

    while page < MAX_PAGES_PER_APP:
        page += 1
        result, token = reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=BATCH_SIZE,
            continuation_token=token,
        )
        if not result:
            print(f"  [{app_id}] page {page}: empty batch, stopping.")
            break

        new_ids = [r["reviewId"] for r in result]
        dup_count = sum(1 for rid in new_ids if rid in seen_ids)

        if dup_count == len(new_ids):
            print(f"  [{app_id}] page {page}: all {len(new_ids)} reviews already seen "
                  f"- pagination looped, stopping here.")
            break

        for r in result:
            if r["reviewId"] not in seen_ids:
                seen_ids.add(r["reviewId"])
                all_reviews.append(r)

        print(f"  [{app_id}] page {page}: +{len(result) - dup_count} new "
              f"(total {len(all_reviews)})")

        if page % CHECKPOINT_EVERY == 0:
            ckpt_df = pd.DataFrame(all_reviews)
            ckpt_path = OUT_DIR / f"reviews_{label}_{today}_checkpoint.parquet"
            ckpt_df.to_parquet(ckpt_path, index=False)
            print(f"    checkpoint saved -> {ckpt_path} ({len(all_reviews)} rows)")

        if token is None:
            print(f"  [{app_id}] page {page}: no more pages, stopping.")
            break

        time.sleep(random.uniform(*SLEEP_RANGE))
    else:
        print(f"  [{app_id}] hit MAX_PAGES_PER_APP ({MAX_PAGES_PER_APP}) safety cap, stopping.")

    return all_reviews


def main():
    today = datetime.now().strftime("%Y%m%d")
    combined_frames = []

    for label, app_id in APPS.items():
        if app_id.startswith("PUT_"):
            print(f"Skipping {label}: no package id filled in yet.")
            continue

        print(f"\nScraping {label} ({app_id}) ...")
        raw = scrape_all_reviews(app_id, LANG, COUNTRY, label, today)

        if not raw:
            print(f"  No reviews returned for {label} in lang={LANG}. "
                  f"Try LANG='en' too - operators get reviews in both.")
            continue

        df = pd.DataFrame(raw)
        df["operator"] = label
        df["app_id"] = app_id
        df["scraped_at"] = datetime.utcnow().isoformat()

        out_path = OUT_DIR / f"reviews_{label}_{today}.parquet"
        df.to_parquet(out_path, index=False)
        print(f"  Saved {len(df)} rows -> {out_path}")

        combined_frames.append(df)

    if combined_frames:
        combined = pd.concat(combined_frames, ignore_index=True)
        combined_path = OUT_DIR / f"reviews_all_{today}.parquet"
        combined.to_parquet(combined_path, index=False)
        print(f"\nBronze layer done: {len(combined)} total rows -> {combined_path}")
    else:
        print("\nNothing scraped - fill in the package ids in APPS and rerun.")


if __name__ == "__main__":
    main()