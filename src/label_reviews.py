"""Label the sampled 1-2 star reviews with Gemini.

    python src/label_reviews.py             # label everything not labeled yet
    python src/label_reviews.py --limit 50  # a short trial run

Progress is saved after every batch, so the script can be stopped and run again,
for example when the free tier's daily limit is reached.
"""

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import Literal

import duckdb
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

from paths import DB_PATH, LLM_LABELS, ROOT, TRANSLATIONS
from taxonomy import ISSUES

DEFAULT_MODEL = "gemini-3.5-flash-lite"
MAX_REVIEW_CHARS = 1500

Issue = Literal[tuple(ISSUES)]


class ReviewLabel(BaseModel):
    review_id: str
    primary_issue: Issue
    mentions_delivery: bool = Field(
        description="True if the review mentions delivery time or shipping at all."
    )
    english: str = Field(
        description="English translation if the review is not in English, otherwise an empty string."
    )


class BatchLabels(BaseModel):
    labels: list[ReviewLabel]


CATEGORY_LINES = "\n".join(f"- {key}: {text}" for key, text in ISSUES.items())

PROMPT = f"""You label customer reviews from online stores. Every review below has a 1 or 2 star rating.

For each review, choose the ONE category that best explains why the customer is unhappy.
If several apply, choose the one that most explains the low rating.

Categories:
{CATEGORY_LINES}

Also set mentions_delivery to true if the review mentions delivery time or shipping at all,
even when that is not the main issue.
If a review is not in English, put an English translation in `english`; otherwise leave it empty.
Return exactly one label per review, with its review_id copied exactly.

Reviews (JSON):
"""


def pending_reviews(limit: int | None) -> list[dict]:
    done = set()
    if LLM_LABELS.exists():
        with LLM_LABELS.open(encoding="utf-8", newline="") as f:
            done = {row["review_id"] for row in csv.DictReader(f)}

    con = duckdb.connect(str(DB_PATH), read_only=True)
    # Reviews picked for hand labeling go first, so the accuracy check can start early.
    rows = con.execute(
        """
        SELECT s.source, s.review_id, s.title, s.review_text,
               h.review_id IS NOT NULL AS in_hand_sample
        FROM label_sample s
        LEFT JOIN hand_label_sample h USING (source, review_id)
        ORDER BY in_hand_sample DESC, md5(s.review_id)
        """
    ).fetchall()
    con.close()

    todo = [
        {"source": src, "review_id": rid, "title": title or "", "text": (text or "")[:MAX_REVIEW_CHARS]}
        for src, rid, title, text, _ in rows
        if rid not in done
    ]
    return todo[:limit] if limit else todo


def append_rows(path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def label_batch(client: genai.Client, model: str, batch: list[dict]) -> list[ReviewLabel]:
    payload = [{"review_id": r["review_id"], "title": r["title"], "text": r["text"]} for r in batch]
    response = client.models.generate_content(
        model=model,
        contents=PROMPT + json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BatchLabels,
        ),
    )
    return BatchLabels.model_validate_json(response.text).labels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Label at most this many reviews in this run.")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--pause", type=float, default=5.0, help="Seconds between requests.")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY in the .env file first (see .env.example).")
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    client = genai.Client(api_key=api_key)

    todo = pending_reviews(args.limit)
    print(f"{len(todo)} reviews to label with {model}")

    labeled = 0
    failures = 0
    i = 0
    while i < len(todo):
        batch = todo[i : i + args.batch_size]
        try:
            labels = label_batch(client, model, batch)
        except (errors.ClientError, errors.ServerError, ValidationError) as e:
            # 429 = rate limit, 5xx = overloaded, ValidationError = malformed JSON. All worth a retry.
            if isinstance(e, errors.ClientError) and e.code != 429:
                raise
            failures += 1
            if failures > 3:
                print(f"Giving up for now ({e.__class__.__name__}). If this is a 429, the free tier's")
                print("daily limit is probably used up. Progress is saved; run the script again later.")
                break
            wait = 30 * 2 ** (failures - 1)
            print(f"{e.__class__.__name__}, retrying in {wait}s")
            time.sleep(wait)
            continue
        failures = 0

        by_id = {r["review_id"]: r for r in batch}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        label_rows, translation_rows, seen = [], [], set()
        for label in labels:
            review = by_id.get(label.review_id)
            if review is None or label.review_id in seen:
                continue
            seen.add(label.review_id)
            label_rows.append({
                "source": review["source"],
                "review_id": label.review_id,
                "primary_issue": label.primary_issue,
                "mentions_delivery": label.mentions_delivery,
                "model": model,
                "labeled_at": now,
            })
            if label.english.strip():
                translation_rows.append({
                    "source": review["source"],
                    "review_id": label.review_id,
                    "english": label.english.strip(),
                })

        append_rows(LLM_LABELS, ["source", "review_id", "primary_issue", "mentions_delivery", "model", "labeled_at"], label_rows)
        append_rows(TRANSLATIONS, ["source", "review_id", "english"], translation_rows)
        labeled += len(label_rows)
        missing = len(batch) - len(label_rows)
        note = f" ({missing} missing, retried next run)" if missing else ""
        print(f"  {labeled}/{len(todo)} labeled{note}")

        i += args.batch_size
        if i < len(todo):
            time.sleep(args.pause)

    print(f"Done: {labeled} new labels in {LLM_LABELS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
