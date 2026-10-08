"""Settle the disagreements between your hand labels and the LLM's, blind.

    python src/review_disagreements.py

For every review where you and the LLM chose different categories, you see the
two labels as A and B in random order, without knowing which one is yours, and
pick the one that fits the category definitions better. Type a, b, or s if both
fit (the review is ambiguous). q quits; you can continue later.
"""

import csv
import random
import sys
import textwrap
from datetime import datetime, timezone

from db import connect
from paths import LABELS
from taxonomy import ISSUES, LABELS as NAMES

ADJUDICATION = LABELS / "adjudication.csv"


def wrap(text: str) -> str:
    return textwrap.fill(" ".join(text.split()), width=88, initial_indent="  ", subsequent_indent="  ")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = connect()
    rows = con.execute(
        """
        SELECT h.source, h.review_id, h.primary_issue AS human, l.primary_issue AS llm,
               s.rating, s.title, s.review_text, t.english
        FROM hand_labels h
        JOIN llm_labels l USING (source, review_id)
        JOIN label_sample s USING (source, review_id)
        LEFT JOIN translations t USING (source, review_id)
        WHERE h.primary_issue <> l.primary_issue
        ORDER BY md5(h.review_id || 'adjudicate')
        """
    ).fetchall()

    done = set()
    if ADJUDICATION.exists():
        with ADJUDICATION.open(encoding="utf-8", newline="") as f:
            done = {row["review_id"] for row in csv.DictReader(f)}
    todo = [r for r in rows if r[1] not in done]
    print(f"{len(done)} of {len(rows)} disagreements settled, {len(todo)} to go.\n")

    for n, (source, review_id, human, llm, rating, title, text, english) in enumerate(todo, start=len(done) + 1):
        # The same review always gets the same A/B order, so a restart doesn't reshuffle it.
        options = [("human", human), ("llm", llm)]
        random.Random(review_id).shuffle(options)

        print("=" * 92)
        print(f"[{n}/{len(rows)}]  {source}  {rating} star")
        if title:
            print(wrap(f"Title: {title}"))
        print(wrap(text))
        if english:
            print("\n  English:")
            print(wrap(english))
        print()
        for letter, (_, issue) in zip("AB", options):
            print(f"  {letter}. {NAMES[issue]:<22} {ISSUES[issue]}")

        while True:
            answer = input("\nWhich fits better? (a, b, s = both fit, q = quit): ").strip().lower()
            if answer == "q":
                print("Saved. Run again to continue.")
                return
            if answer in ("a", "b", "s"):
                verdict = "both" if answer == "s" else options["ab".index(answer)][0]
                is_new = not ADJUDICATION.exists()
                with ADJUDICATION.open("a", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["source", "review_id", "verdict", "labeled_at"])
                    if is_new:
                        writer.writeheader()
                    writer.writerow({
                        "source": source,
                        "review_id": review_id,
                        "verdict": verdict,
                        "labeled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    })
                break
            print("Type a, b, s or q.")

    print("All settled. Next: python src/evaluate.py")


if __name__ == "__main__":
    main()
