"""
Multi-Sort Scraper: Bypasses Google Play's pagination limits.
Rotates through NEWEST, MOST_RELEVANT, and RATING sorts, and both AR/EN languages,
to pull historical data (Vodafone back to 2018) that a standard newest-first scrape misses.
"""
import time
import random
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from google_play_scraper import Sort, reviews

APPS = {
    "orange_eg": "com.orange.mobinilandme",
    "etisalat_eg": "com.etisalat",
    "we_eg": "com.ucare.we",
    "vodafone_eg": "com.emeint.android.myservices",
}

# The magic combo: 3 sorts x 2 languages = 6 different queries per app!
SORTS = [Sort.NEWEST, Sort.MOST_RELEVANT, Sort.RATING]
LANGS = ["ar", "en"] # EN catches Franco-Arab text
COUNTRY = "eg"
BATCH_SIZE = 200
OUT_DIR = Path("bronze")
OUT_DIR.mkdir(exist_ok=True)

def scrape_query(app_id, sort_order, lang, country, seen_ids):
    token = None
    page = 0
    
    while page < 500:
        page += 1
        try:
            result, token = reviews(
                app_id, lang=lang, country=country,
                sort=sort_order, count=BATCH_SIZE, continuation_token=token
            )
        except Exception:
            break
            
        if not result:
            break

        for r in result:
            if r["reviewId"] not in seen_ids:
                seen_ids.add(r["reviewId"])
                yield r 

        if token is None:
            break
        time.sleep(random.uniform(0.5, 1.5))

def main():
    today = datetime.now().strftime("%Y%m%d")
    
    for label, app_id in APPS.items():
        print(f"\n=======================================================")
        print(f"Scraping {label} ({app_id}) across AR/EN and all sorts...")
        print(f"=======================================================")
        
        seen_ids = set()
        all_reviews = []
        
        for lang in LANGS:
            for sort_order in SORTS:
                print(f"  -> Trying {sort_order.name} | Lang: {lang.upper()}")
                for review in scrape_query(app_id, sort_order, lang, COUNTRY, seen_ids):
                    all_reviews.append(review)
                
                print(f"     Total unique reviews so far: {len(all_reviews):,}")
                time.sleep(random.uniform(1.0, 2.0))

        if all_reviews:
            df = pd.DataFrame(all_reviews)
            df["operator"] = label
            df["scraped_at"] = datetime.now(timezone.utc).isoformat()
            
            out_path = OUT_DIR / f"reviews_{label}_multi_{today}.parquet"
            df.to_parquet(out_path, index=False)
            print(f"\n[DONE] Saved {len(df):,} TOTAL unique rows for {label} -> {out_path}")

if __name__ == "__main__":
    main()