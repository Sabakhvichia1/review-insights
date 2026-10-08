"""Label the check sample yourself, one review at a time.

    python src/hand_label.py

Type 1-7 and Enter to pick a category, s to skip, q to quit.
You can stop at any time and continue later. Label before you look at the
LLM's answers, so the check stays fair.
"""

import csv
import sys
import textwrap
from datetime import datetime, timezone

import duckdb

from paths import DB_PATH, HAND_LABELS, TRANSLATIONS
from taxonomy import ISSUES, LABELS


def load_done() -> set[str]:
    if not HAND_LABELS.exists():
        return set()
    with HAND_LABELS.open(encoding="utf-8", newline="") as f:
        return {row["review_id"] for row in csv.DictReader(f)}


def load_translations() -> dict[str, str]:
    if not TRANSLATIONS.exists():
        return {}
    with TRANSLATIONS.open(encoding="utf-8", newline="") as f:
        return {row["review_id"]: row["english"] for row in csv.DictReader(f)}


def save(source: str, review_id: str, issue: str) -> None:
    is_new = not HAND_LABELS.exists()
    with HAND_LABELS.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "review_id", "primary_issue", "labeled_at"])
        if is_new:
            writer.writeheader()
        writer.writerow({
            "source": source,
            "review_id": review_id,
            "primary_issue": issue,
            "labeled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })


def wrap(text: str) -> str:
    return textwrap.fill(" ".join(text.split()), width=88, initial_indent="  ", subsequent_indent="  ")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        "SELECT source, review_id, rating, title, review_text FROM hand_label_sample "
        "ORDER BY md5(review_id || 'order')"
    ).fetchall()
    con.close()

    done = load_done()
    translations = load_translations()
    todo = [r for r in rows if r[1] not in done]
    keys = list(ISSUES)
    menu = "\n".join(f"  {i}. {LABELS[k]:<22} {ISSUES[k]}" for i, k in enumerate(keys, start=1))

    print(f"{len(done)} of {len(rows)} done, {len(todo)} to go.\n")
    for n, (source, review_id, rating, title, text) in enumerate(todo, start=len(done) + 1):
        print("=" * 92)
        print(f"[{n}/{len(rows)}]  {source}  {rating} star")
        if title:
            print(wrap(f"Title: {title}"))
        print(wrap(text))
        if review_id in translations:
            print("\n  English:")
            print(wrap(translations[review_id]))
        print("\n" + menu)

        while True:
            answer = input("\nCategory (1-7, s = skip, q = quit): ").strip().lower()
            if answer == "q":
                print("Saved. Run again to continue.")
                return
            if answer == "s":
                break
            if answer.isdigit() and 1 <= int(answer) <= len(keys):
                save(source, review_id, keys[int(answer) - 1])
                break
            print("Type a number from 1 to 7, s or q.")

    print("All done. Next: python src/evaluate.py")


if __name__ == "__main__":
    main()
