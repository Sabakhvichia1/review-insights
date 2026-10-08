"""Check the LLM's labels against your hand labels and against Olist's delivery records.

    python src/evaluate.py

Writes data/labels/evaluation.json, which the notebook and dashboard read.
"""

import json
import sys

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, cohen_kappa_score

from db import connect, query
from paths import LABELS as LABELS_DIR
from taxonomy import ISSUES

LATE = ["late", "not delivered"]
ADJUDICATION = LABELS_DIR / "adjudication.csv"


def agreement(con) -> dict:
    pairs = con.execute(
        """
        SELECT h.source, h.review_id, h.primary_issue AS human, l.primary_issue AS llm
        FROM hand_labels h
        JOIN llm_labels l USING (source, review_id)
        """
    ).df()
    if pairs.empty:
        raise SystemExit("No review has both a hand label and an LLM label yet.")

    groups = [("both", pairs), *pairs.groupby("source")]
    by_source = {
        name: {
            "reviews": len(df),
            "accuracy": round(accuracy_score(df.human, df.llm), 3),
            "kappa": round(cohen_kappa_score(df.human, df.llm), 3),
        }
        for name, df in groups
    }

    print("Agreement with hand labels")
    for name, stats in by_source.items():
        print(f"  {name:<7} {stats['reviews']:>4} reviews   accuracy {stats['accuracy']:.0%}   kappa {stats['kappa']:.2f}")
    print()
    print(classification_report(pairs.human, pairs.llm, labels=list(ISSUES), zero_division=0))

    confusion = pairs.groupby(["human", "llm"]).size().reset_index(name="reviews")
    disagreements = pairs[pairs.human != pairs.llm]
    print(f"{len(disagreements)} disagreements; most common:")
    common = disagreements.groupby(["human", "llm"]).size().sort_values(ascending=False).head(5)
    for (human, llm), n in common.items():
        print(f"  you: {human:<22} LLM: {llm:<22} {n}")

    # Individual labels can disagree while the totals still match. The findings rest on totals.
    shares = (
        pairs.melt(id_vars=["source", "review_id"], value_vars=["human", "llm"], var_name="labeler", value_name="issue")
        .groupby(["source", "issue", "labeler"]).size().unstack("labeler", fill_value=0).reset_index()
    )
    print("\nSame reviews, category totals (you vs LLM):")
    for row in shares.sort_values(["source", "human"], ascending=[True, False]).itertuples():
        print(f"  {row.source:<7} {row.issue:<22} you {row.human:>3}   LLM {row.llm:>3}")

    return {
        "by_source": by_source,
        "confusion": confusion.to_dict(orient="records"),
        "shares_same_reviews": shares.to_dict(orient="records"),
        "disagreement_ids": disagreements.review_id.tolist(),
        "adjudication": adjudication(disagreements),
    }


def adjudication(disagreements: pd.DataFrame) -> dict:
    """Blind second look at each disagreement (src/review_disagreements.py)."""
    if not ADJUDICATION.exists():
        return {}
    verdicts = pd.read_csv(ADJUDICATION, dtype=str)
    verdicts = verdicts[verdicts.review_id.isin(disagreements.review_id)]
    counts = verdicts.verdict.value_counts().reindex(["llm", "human", "both"], fill_value=0)
    result = {
        "settled": int(len(verdicts)),
        "disagreements": int(len(disagreements)),
        "llm_fit_better": int(counts["llm"]),
        "hand_label_fit_better": int(counts["human"]),
        "both_fit": int(counts["both"]),
    }
    print(f"\nBlind review of {result['settled']} of {result['disagreements']} disagreements:")
    print(f"  LLM's label fit better: {result['llm_fit_better']}   "
          f"hand label fit better: {result['hand_label_fit_better']}   both fit: {result['both_fit']}")
    return result


def delivery_records_check(con) -> dict:
    rec = query(con, "08_labels_vs_delivery_records.sql")
    if rec.empty:
        return {}
    said_late = rec[rec.llm_says_late_delivery]
    late_orders = rec[rec.delivery_status.isin(LATE)]
    said_late_n = int(said_late.reviews.sum())
    late_orders_n = int(late_orders.reviews.sum())
    confirmed = int(said_late[said_late.delivery_status.isin(LATE)].reviews.sum())
    caught = int(late_orders[late_orders.llm_says_late_delivery].reviews.sum())
    result = {
        "llm_late_labels": said_late_n,
        "confirmed_by_records": confirmed,
        "precision": round(confirmed / said_late_n, 3) if said_late_n else None,
        "reviews_on_late_orders": late_orders_n,
        "labeled_late_delivery": caught,
        "recall": round(caught / late_orders_n, 3) if late_orders_n else None,
    }
    print("\nOlist: LLM 'late delivery' labels vs actual delivery dates")
    if result["precision"] is not None:
        print(f"  {confirmed} of {said_late_n} 'late delivery' labels were on orders that really were late "
              f"or never arrived ({result['precision']:.0%})")
    if result["recall"] is not None:
        print(f"  {caught} of {late_orders_n} low ratings on late or missing orders were labeled "
              f"'late delivery' ({result['recall']:.0%})")
    return result


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = connect()
    result = {"hand_labels": agreement(con), "delivery_records": delivery_records_check(con)}
    out = LABELS_DIR / "evaluation.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nSaved {out.name}")


if __name__ == "__main__":
    main()
