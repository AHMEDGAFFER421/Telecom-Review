"""
VODAFONE ARABIC SCRAPE - one app only (com.emeint.android.myservices).
Copy-paste of the working scraper, config already set. Just run it.

Usage:
    python scrape_vodafone_ar.py

Output:
    bronze/reviews_vodafone_eg_ar_<YYYYMMDD>.parquet      (final, when done)
    bronze/reviews_vodafone_eg_ar_<YYYYMMDD>_checkpoint.parquet  (every 50 pages)

Safe to stop/restart: checkpoints save every 50 pages. Re-running starts from
page 1 again - the silver layer dedupes the overlap, nothing doubles.
"""

import time
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

# ---------------------------------------------------------------------------
# CONFIG - ONLY Vodafone, Arabic. Do not edit anything below this line.
# ---------------------------------------------------------------------------
APPS = {
    "vodafone_eg": "com.emeint.android.myservices",
}

LANG = "ar"
COUNTRY = "eg"
BATCH_SIZE = 200
SLEEP_RANGE = (1.0, 2.5)

OUT_DIR = Path("bronze")
OUT_DIR.mkdir(exist_ok=True)

MAX_PAGES_PER_APP = 3000     # safety cap (600k reviews) - genuine end conditions
                             # (empty/looped/no-token) stop it long before this
CHECKPOINT_EVERY = 50
RETRY_ON_EMPTY = 3
RETRY_DELAY = 15
APP_COOLDOWN = 20


def scrape_all_reviews(app_id: str, lang: str, country: str, label: str, today: str) -> list[dict]:
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
            retried_ok = False
            for attempt in range(1, RETRY_ON_EMPTY + 1):
                print(f"  [{app_id}] page {page}: empty batch, retry {attempt}/{RETRY_ON_EMPTY} "
                      f"in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                result, token = reviews(
                    app_id, lang=lang, country=country,
                    sort=Sort.NEWEST, count=BATCH_SIZE, continuation_token=token,
                )
                if result:
                    retried_ok = True
                    break

            if not retried_ok:
                print(f"  [{app_id}] page {page}: still empty after {RETRY_ON_EMPTY} retries, "
                      f"trusting it's genuinely done.")
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
            ckpt_path = OUT_DIR / f"reviews_{label}_{lang}_{today}_checkpoint.parquet"
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
        print(f"\nScraping {label} ({app_id}) in lang={LANG} ...")
        raw = scrape_all_reviews(app_id, LANG, COUNTRY, label, today)

        if not raw:
            print(f"  No reviews returned for {label} in lang={LANG} even after retries.")
            continue

        df = pd.DataFrame(raw)
        df["operator"] = label
        df["app_id"] = app_id
        df["scraped_at"] = datetime.now(timezone.utc).isoformat()

        out_path = OUT_DIR / f"reviews_{label}_{LANG}_{today}.parquet"
        df.to_parquet(out_path, index=False)
        print(f"  Saved {len(df)} rows -> {out_path}")

        combined_frames.append(df)

    if combined_frames:
        combined = pd.concat(combined_frames, ignore_index=True)
        combined_path = OUT_DIR / f"reviews_all_{LANG}_{today}.parquet"
        combined.to_parquet(combined_path, index=False)
        print(f"\nVodafone Arabic scrape done: {len(combined)} total rows -> {combined_path}")
    else:
        print("\nNothing scraped - check the internet connection and rerun.")


if __name__ == "__main__":
    main()