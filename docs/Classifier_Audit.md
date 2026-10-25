# Classifier Audit

The complaint categories in this project come from keyword rules, not a trained model. Before relying on them I checked them by hand twice. This file records what I checked, what was wrong, what I changed, and what is still wrong. It contains numbers and short glosses only, no review text.

## Summary

| | Audit 1 | Audit 2 |
|---|---|---|
| Sample | 50 reviews, 5 per category | 80 reviews from `other` (40 rated 1-2 stars, 40 rated 4-5), March 2022 onward |
| Verdict | 31 correct, 8 ambiguous, 11 wrong | Most low-rated `other` reviews were real complaints the rules could not name, and several high-rated ones were praise |
| Main cause | Generic words ("app", "program") matched praise and sent it to `app_bug` | "جدا" (very) counted as praise, Arabic prefixes broke matching, emoji-only reviews and typos were missed |
| Fix | Praise guard for `app_bug` (v7.1) | Rule and dictionary changes (v7.2) |

## Audit 1: one pass over every category

I took 5 random reviews per category (seed 42) and judged each label as correct, ambiguous or wrong.

| Category | Correct | Ambiguous | Wrong |
|---|---|---|---|
| praise | 5 | 0 | 0 |
| praise_short | 5 | 0 | 0 |
| network_coverage | 4 | 1 | 0 |
| vague_negative | 4 | 1 | 0 |
| vague_negative_short | 4 | 0 | 1 |
| billing | 3 | 1 | 1 |
| customer_service | 2 | 3 | 0 |
| angry_other | 2 | 1 | 2 |
| other | 2 | 0 | 3 |
| **app_bug** | **0** | **1** | **4** |
| **Total** | **31** | **8** | **11** |

The sample is small, so it shows where the rules are weak, not how accurate they are overall.

**What stood out**

- All 5 `app_bug` reviews were rated 4-5 stars, and 4 were plain praise ("great app"). The keyword list contains "app", "program" and "update", so any review that mentions the app matched `app_bug` before the praise check ever ran.
- `other` contained praise written with typos or unusual words.
- A few short complaints with a topic word went to the wrong group ("bad internet" was labelled as a vague negative, not network).

## Fix 1 (v7.1): praise guard for `app_bug`

A review labelled `app_bug` that has a praise word and no problem word is relabelled `praise`.

I measured the effect on all 178,531 `app_bug` reviews (all dates):

| | Before | After |
|---|---|---|
| `app_bug` reviews | 178,531 | 102,007 |
| Rated 4-5 stars | 96,593 | 24,366 |
| Rated 1-2 stars | 74,370 | 71,814 |
| Low-rating share | 43.5% | 74.7% |

76,524 reviews moved to `praise`. Of those, 2,556 were rated 1-2 stars (3.4% of the low-rated `app_bug` reviews), probably complaints that contain a praise word. I accepted that cost.

## Audit 2: the `other` category

`other` held 147,135 rated reviews in the window (16%), and 40% of them were low-rated, well above the 24.6% baseline. That means complaints were hiding there. I sampled 40 low-rated and 40 high-rated `other` reviews (seed 7).

**Root causes found**

1. **"جدا" (very) was in the praise list.** It is an intensifier, so "very bad" matched both praise and negative. Reviews of 3 words or fewer fell into `praise_short`, and longer ones into `other`. I confirmed this directly: the two-word phrase "very bad" was labelled `praise_short` before the fix.
2. **Arabic prefixes broke keyword matching.** Word-boundary matching removed false hits but also stopped "the balance", "and excellent" and "I charge" from matching their keywords, because a letter is attached to the front. This was a side effect of my earlier fix.
3. **Emoji-only reviews** (a thumbs-up, a heart) were about 20% of the high-rated sample and had no category.
4. **Missing words:** "worst", "dirtiest", typos of "excellent", "above excellent", "internet" (Arabic spelling), and forms of "doesn't work" and "won't open".
5. **Label noise, not a classifier error:** 7 of the 80 reviews (9%) had a rating that contradicts the text (a 5-star review saying "very bad", a 1-star saying "excellent"). I can't fix that in the rules.

## Fix 2 (v7.2)

- Removed "جدا" and its variants from the praise list. Compound praise like "very good" still matches through the praise word.
- Allowed one prefix (و، ب، ل، ف، ك، ا، ال، وال، بال، لل) before Arabic keywords of 3+ letters.
- Reviews with both a praise and a negative cue now return `other`. They used to return `praise_short`.
- Emoji-only reviews: positive emoji become `praise_short`, negative ones `vague_negative_short`.
- Added about 45 words to the praise, negative, anger, app-bug and network lists. The original lists are untouched, and the additions sit in their own section.

## Checking v7.2 without fooling myself

The 80 reviews were used to find the problems, so improvements on them don't count as evidence. I checked on samples I had not tuned on:

| Check | Result |
|---|---|
| 50 reviews from Audit 1 | 8 labels changed: 5 better, 1 neutral, 2 worse |
| 3,000 old `app_bug` reviews | 136 changed (4.5%). About 92 were complaints that moved to billing, network or customer service. About 44 were praise reviews that now carry a topic label |
| Intensifier test | "very bad" went from `praise_short` to `vague_negative_short` |

The two worse cases were a praise typo that the new rules don't know, and a praise review that mentions customer service and now takes the topic label. Both are kinds of error I knew about and accepted.

**Effect on the full dataset (March 2022 onward)**

| | v7.1 | v7.2 |
|---|---|---|
| Low-rated `praise_short` reviews | 21,972 | 15,030 (down 32%) |
| Rated reviews in `other` | 147,135 (16%) | 103,257 (11%) |
| `other` reviews, all dates | 238,250 | 171,330 |

**Effect on the findings (low-rating share)**

| Category | v7.1 | v7.2 |
|---|---|---|
| customer_service | 80.5% | 77.6% |
| app_bug | 76.1% | 75.2% |
| billing | 68.2% | 66.5% |
| network_coverage | 63.4% | 65.9% |
| other | 40.0% | 37.4% |

The order of the top two did not change. Billing and network moved to within 0.6 points of each other, so the write-up does not rank those two.

## What is still wrong

- **One label per review.** A review about billing and the app gets a single category.
- **Topic labels include praise.** A happy review that mentions the balance is labelled `billing`. The topic charts count "mentions", which is why the findings talk about the share of low-rated reviews inside a topic, not complaint types.
- **`other` is still 11% of rated reviews.** Much of it is feature complaints (daily gifts, the wheel of fortune, data allowances), names, and gibberish.
- **Praise typos are a long tail.** I fixed the common ones, and new misspellings keep appearing.
- **Negation is not handled.** "Not good" matches the praise word.
- **Some noisy words remain.** "تحديث" (update) and "مش" (not) are in the problem list, and they also appear in positive reviews.
- **Anger words overlap billing words** ("thieves", "stole"), so a billing review can look angrier than others.

I stopped tuning here on purpose. More rules on this sample would fit its quirks, and the remaining errors are the kind a keyword approach can't solve. A multilingual model would be the next step, and it would need a labelled set, which these two audits could seed.

## Reproduce

```python
import pandas as pd

df = pd.read_parquet("silver/reviews_private.parquet")

# Audit 1: 5 reviews per category
a1 = (df.groupby("complaint_category", group_keys=False)
        .sample(n=5, random_state=42))

# Audit 2: 40 low-rated and 40 high-rated "other" reviews, in the window
o = df[(df.complaint_category == "other") & df.in_common_window & df.content.str.len().gt(0)]
low  = o[o.score <= 2].sample(40, random_state=7)
high = o[o.score >= 4].sample(40, random_state=7)
```

The private file contains review text and is not in the repository.
