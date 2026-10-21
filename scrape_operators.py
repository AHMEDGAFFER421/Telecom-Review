"""
Unified Bronze-layer scraper for all telecom operators.
Pulls all available Google Play reviews with checkpointing and retry logic.
"""

import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from google_play_scraper import Sort, reviews

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
APPS = {
    "orange_eg": "com.orange.mobinilandme",
    "etisalat_eg": "com.etisalat",
    "we_eg": "com.ucare.we",
    "vodafone_eg": "com.emeint.android.myservices",
}

LANG = "ar"
COUNTRY = "eg"
BATCH_SIZE = 200
SLEEP_RANGE = (1.0, 2.5)

OUT_DIR = Path("bronze")
OUT_DIR.mkdir(exist_ok=True)

MAX_PAGES_PER_APP = 3000
CHECKPOINT_EVERY = 50
RETRY_ON_EMPTY = 3
RETRY_DELAY = 15


def scrape_app(
    app_id: str, lang: str, country: str, label: str, today: str
) -> List[Dict[str, Any]]:
    """Scrapes all reviews for a single app with retries and checkpoints."""
    all_reviews: List[Dict[str, Any]] = []
    seen_ids = set()
    token = None
    page = 0

    while page < MAX_PAGES_PER_APP:
        page += 1

        try:
            result, token = reviews(
                app_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=BATCH_SIZE,
                continuation_token=token,
            )
        except Exception as e:  # pylint: disable=broad-except
            print(f"  [{app_id}] page {page}: Error {e}. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            page -= 1  # Don't count this as a page
            continue

        if not result:
            # Retry logic for empty batches
            retried_ok = False
            for attempt in range(1, RETRY_ON_EMPTY + 1):
                print(
                    f"  [{app_id}] page {page}: empty batch, "
                    f"retry {attempt}/{RETRY_ON_EMPTY} in {RETRY_DELAY}s..."
                )
                time.sleep(RETRY_DELAY)
                try:
                    result, token = reviews(
                        app_id,
                        lang=lang,
                        country=country,
                        sort=Sort.NEWEST,
                        count=BATCH_SIZE,
                        continuation_token=token,
                    )
                except Exception:  # pylint: disable=broad-except
                    pass  # Ignore network errors during retry
                if result:
                    retried_ok = True
                    break

            if not retried_ok:
                print(f"  [{app_id}] page {page}: still empty. Stopping.")
                break

        new_ids = [r["reviewId"] for r in result]
        dup_count = sum(1 for rid in new_ids if rid in seen_ids)

        if dup_count == len(new_ids):
            print(f"  [{app_id}] page {page}: all reviews already seen. Stopping.")
            break

        for r in result:
            if r["reviewId"] not in seen_ids:
                seen_ids.add(r["reviewId"])
                all_reviews.append(r)

        print(
            f"  [{app_id}] page {page}: +{len(result) - dup_count} new "
            f"(total {len(all_reviews)})"
        )

        if page % CHECKPOINT_EVERY == 0:
            ckpt_path = OUT_DIR / f"reviews_{label}_{lang}_{today}_checkpoint.parquet"
            pd.DataFrame(all_reviews).to_parquet(ckpt_path, index=False)
            print(f"    checkpoint saved -> {ckpt_path}")

        if token is None:
            print(f"  [{app_id}] page {page}: no more pages, stopping.")
            break

        time.sleep(random.uniform(*SLEEP_RANGE))
    else:
        print(f"  [{app_id}] hit MAX_PAGES_PER_APP ({MAX_PAGES_PER_APP}). Stopping.")

    return all_reviews


def main() -> None:
    """Main execution loop."""
    today = datetime.now().strftime("%Y%m%d")

    for label, app_id in APPS.items():
        print(f"\n--- Scraping {label} ({app_id}) ---")
        raw_reviews = scrape_app(app_id, LANG, COUNTRY, label, today)

        if raw_reviews:
            df = pd.DataFrame(raw_reviews)
            df["operator"] = label
            df["scraped_at"] = datetime.now(timezone.utc).isoformat()

            out_path = OUT_DIR / f"reviews_{label}_{LANG}_{today}.parquet"
            df.to_parquet(out_path, index=False)
            print(f"  Saved {len(df)} rows -> {out_path}")
        else:
            print(f"  No reviews scraped for {label}.")


if __name__ == "__main__":
    main()
