"""Dashboard for the review analysis.

    streamlit run app.py
"""

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from db import connect, query  # noqa: E402
from paths import LABELS as LABELS_DIR  # noqa: E402
from taxonomy import ISSUES, LABELS  # noqa: E402

SOURCE_NAMES = {"olist": "Olist (Brazil)", "amazon": "Amazon Beauty (US)"}
SOURCE_COLORS = {"Olist (Brazil)": "#2563eb", "Amazon Beauty (US)": "#ea580c"}
ISSUE_ORDER = [LABELS[k] for k in ISSUES]

st.set_page_config(page_title="Why customers leave bad reviews", layout="wide")


def style(fig, height=380):
    fig.update_layout(
        template="simple_white",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        legend_title_text="",
        font=dict(size=13),
    )
    return fig


def load_evaluation() -> dict | None:
    path = LABELS_DIR / "evaluation.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


con = connect()
by_delay = query(con, "02_rating_by_delay.sql")
by_status = query(con, "03_low_ratings_by_delivery.sql")
by_state = query(con, "04_late_by_state.sql")
by_category = query(con, "05_late_by_category.sql")
issue_mix = query(con, "06_issue_mix.sql")
olist_issue_by_delivery = query(con, "07_olist_issue_by_delivery.sql")
by_order_type = query(con, "09_order_type_ratings.sql")
missing_by_order_type = query(con, "10_missing_items_by_order_type.sql")
evaluation = load_evaluation()

for df in (issue_mix, olist_issue_by_delivery):
    df["issue"] = df["primary_issue"].map(LABELS)
issue_mix["marketplace"] = issue_mix["source"].map(SOURCE_NAMES)

st.title("Why do customers leave 1-2 star reviews?")
st.caption(
    "Olist, a Brazilian online marketplace (2016-2018 orders), compared with Amazon Beauty reviews "
    "from the same years. Complaint reasons were labeled by Gemini and checked against hand labels "
    "and delivery records."
)

summary, delivery, reasons, accuracy, reader = st.tabs(
    ["Summary", "Delivery and ratings", "Complaint reasons", "Can we trust the labels?", "Read the reviews"]
)

# --- Summary -------------------------------------------------------------------
with summary:
    status = by_status.set_index("delivery_status")
    delivered = status.loc[["on time", "late"], "reviews"].sum()
    late_pct = status.loc["late", "reviews"] / delivered * 100
    problem_rows = status.loc[status.index.isin(["late", "not delivered"])]
    low_from_late = problem_rows["share_of_low_ratings_pct"].sum()
    orders_late_or_missing = problem_rows["share_of_reviews_pct"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Olist reviews analyzed", f"{int(status['reviews'].sum()):,}")
    c2.metric("Delivered orders that were late", f"{late_pct:.1f}%")
    c3.metric("Avg rating, on time vs late", f"{status.loc['on time', 'avg_rating']:.2f} vs {status.loc['late', 'avg_rating']:.2f}")
    c4.metric("Low ratings from late or missing orders", f"{low_from_late:.0f}%")

    st.markdown(
        f"- Late or missing orders are **{orders_late_or_missing:.0f}%** of Olist reviews but "
        f"**{low_from_late:.0f}%** of its 1-2 star reviews."
    )
    shape = by_order_type.set_index("order_type")
    st.markdown(
        f"- Even when delivered on time, orders from several sellers get 1-2 stars "
        f"**{shape.loc['several sellers', 'low_rating_pct']:.0f}%** of the time, against "
        f"**{shape.loc['one item', 'low_rating_pct']:.0f}%** for one-item orders. Their items arrive in "
        f"separate parcels, and most of these complaints are about a missing item."
    )
    if not issue_mix.empty:
        top = issue_mix.sort_values("share_pct", ascending=False).groupby("source").head(1).set_index("source")
        for src in ["olist", "amazon"]:
            if src in top.index:
                row = top.loc[src]
                st.markdown(
                    f"- The most common complaint on **{SOURCE_NAMES[src]}** is "
                    f"**{row['issue'].lower()}** ({row['share_pct']:.0f}% of sampled 1-2 star reviews)."
                )
    if evaluation:
        both = evaluation["hand_labels"]["by_source"]["both"]
        st.markdown(
            f"- The LLM agreed with hand labels on **{both['accuracy']:.0%}** of {both['reviews']} reviews "
            f"(Cohen's kappa {both['kappa']:.2f})."
        )

# --- Delivery and ratings ------------------------------------------------------
with delivery:
    st.subheader("Ratings fall sharply once an order is late")
    left, right = st.columns(2)
    fig = px.bar(by_delay, x="delay_bucket", y="avg_rating", text="avg_rating",
                 labels={"delay_bucket": "Delivered vs the promised date", "avg_rating": "Average rating (1-5)"})
    fig.update_traces(marker_color="#2563eb", textposition="outside")
    fig.update_yaxes(range=[0, 5.4])
    left.plotly_chart(style(fig), width="stretch")

    fig = px.bar(by_delay, x="delay_bucket", y="one_star_pct", text="one_star_pct",
                 labels={"delay_bucket": "Delivered vs the promised date", "one_star_pct": "1-star reviews (%)"})
    fig.update_traces(marker_color="#dc2626", textposition="outside")
    right.plotly_chart(style(fig), width="stretch")

    st.subheader("Where late deliveries happen")
    left, right = st.columns(2)
    left.markdown("**By customer state** (500+ delivered orders)")
    left.dataframe(by_state, hide_index=True, width="stretch")
    right.markdown("**Top 15 product categories**")
    right.dataframe(by_category, hide_index=True, width="stretch")

# --- Complaint reasons ---------------------------------------------------------
with reasons:
    if issue_mix.empty:
        st.info("No LLM labels yet. Run `python src/label_reviews.py` first.")
    else:
        st.subheader("What 1-2 star reviews complain about")
        fig = px.bar(issue_mix, y="issue", x="share_pct", color="marketplace", barmode="group",
                     orientation="h", text="share_pct", color_discrete_map=SOURCE_COLORS,
                     category_orders={"issue": ISSUE_ORDER},
                     labels={"issue": "", "share_pct": "Share of sampled 1-2 star reviews (%)"})
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
        st.plotly_chart(style(fig, 460), width="stretch")
        counts = issue_mix.groupby("marketplace")["reviews"].sum()
        st.caption(" · ".join(f"{name}: {n} reviews labeled" for name, n in counts.items()))

        st.subheader("Olist: complaints when the order was on time")
        fig = px.bar(olist_issue_by_delivery, y="issue", x="share_pct", color="delivery", barmode="group",
                     orientation="h", text="share_pct", category_orders={"issue": ISSUE_ORDER},
                     color_discrete_map={"on time": "#16a34a", "late or not delivered": "#dc2626"},
                     labels={"issue": "", "share_pct": "Share of Olist 1-2 star reviews (%)"})
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
        st.plotly_chart(style(fig, 460), width="stretch")

        st.subheader("Olist: orders with several items look incomplete")
        left, right = st.columns(2)
        fig = px.bar(by_order_type, x="order_type", y="low_rating_pct", text="low_rating_pct",
                     labels={"order_type": "", "low_rating_pct": "1-2 star reviews, on-time orders (%)"})
        fig.update_traces(marker_color="#7c3aed", texttemplate="%{text:.1f}%", textposition="outside")
        left.plotly_chart(style(fig), width="stretch")
        fig = px.bar(missing_by_order_type, x="order_type", y="wrong_or_missing_pct", text="wrong_or_missing_pct",
                     labels={"order_type": "", "wrong_or_missing_pct": "Low ratings about a wrong or missing item (%)"})
        fig.update_traces(marker_color="#7c3aed", texttemplate="%{text:.0f}%", textposition="outside")
        right.plotly_chart(style(fig), width="stretch")
        counts = ", ".join(f"{r.order_type}: {r.low_ratings}" for r in missing_by_order_type.itertuples())
        st.caption(f"Right chart is based on the labeled sample ({counts} reviews), so the small groups are rough.")

# --- Label accuracy ------------------------------------------------------------
with accuracy:
    if not evaluation:
        st.info("Hand-label the check sample (`python src/hand_label.py`), then run `python src/evaluate.py`.")
    else:
        st.subheader("LLM labels vs hand labels")
        cols = st.columns(3)
        for col, key in zip(cols, ["both", "olist", "amazon"]):
            stats = evaluation["hand_labels"]["by_source"].get(key)
            if stats:
                col.metric(f"{SOURCE_NAMES.get(key, 'Both marketplaces')} ({stats['reviews']} reviews)",
                           f"{stats['accuracy']:.0%} agree", f"kappa {stats['kappa']:.2f}", delta_color="off")

        confusion = pd.DataFrame(evaluation["hand_labels"]["confusion"])
        matrix = (confusion.pivot_table(index="human", columns="llm", values="reviews", fill_value=0)
                  .reindex(index=list(ISSUES), columns=list(ISSUES), fill_value=0)
                  .astype(int)
                  .rename(index=LABELS, columns=LABELS))
        fig = px.imshow(matrix, text_auto=True, color_continuous_scale="Blues",
                        labels={"x": "LLM label", "y": "Hand label", "color": "Reviews"})
        fig.update_coloraxes(showscale=False)
        st.plotly_chart(style(fig, 480), width="stretch")

        st.subheader("Category totals on the same reviews")
        st.caption("Individual labels disagree more often than the totals do. The findings rest on the totals.")
        shares = pd.DataFrame(evaluation["hand_labels"]["shares_same_reviews"])
        shares["marketplace"] = shares["source"].map(SOURCE_NAMES)
        shares["category"] = shares["issue"].map(LABELS)
        st.dataframe(
            shares[["marketplace", "category", "human", "llm"]]
            .rename(columns={"human": "Hand labels", "llm": "LLM labels"})
            .sort_values(["marketplace", "Hand labels"], ascending=[False, False]),
            hide_index=True,
        )

        adj = evaluation["hand_labels"].get("adjudication")
        if adj:
            st.subheader("Blind second look at the disagreements")
            c1, c2, c3 = st.columns(3)
            c1.metric("LLM's label fit the definitions better", adj["llm_fit_better"])
            c2.metric("Hand label fit better", adj["hand_label_fit_better"])
            c3.metric("Both fit (ambiguous review)", adj["both_fit"])

        records = evaluation.get("delivery_records")
        if records and records.get("precision") is not None:
            st.subheader("Olist: LLM 'late delivery' labels vs actual delivery dates")
            c1, c2 = st.columns(2)
            c1.metric("Labeled 'late delivery' and the order really was late or missing",
                      f"{records['precision']:.0%}", f"{records['confirmed_by_records']} of {records['llm_late_labels']}",
                      delta_color="off")
            c2.metric("Low ratings on late or missing orders labeled 'late delivery'",
                      f"{records['recall']:.0%}", f"{records['labeled_late_delivery']} of {records['reviews_on_late_orders']}",
                      delta_color="off")

# --- Read the reviews ----------------------------------------------------------
with reader:
    if issue_mix.empty:
        st.info("No LLM labels yet.")
    else:
        c1, c2 = st.columns(2)
        source = c1.selectbox("Marketplace", list(SOURCE_NAMES), format_func=SOURCE_NAMES.get)
        issue = c2.selectbox("Complaint reason", list(ISSUES), format_func=LABELS.get)
        examples = con.execute(
            """
            SELECT s.rating, s.title, s.review_text, t.english
            FROM llm_labels l
            JOIN label_sample s USING (source, review_id)
            LEFT JOIN translations t USING (source, review_id)
            WHERE l.source = ? AND l.primary_issue = ?
            ORDER BY md5(l.review_id)
            LIMIT 12
            """,
            [source, issue],
        ).df()
        if examples.empty:
            st.write("No reviews with this label.")
        for row in examples.itertuples():
            with st.container(border=True):
                st.markdown(f"**{'★' * int(row.rating)}{'☆' * (5 - int(row.rating))}**  {row.title or ''}")
                st.write(row.review_text)
                if isinstance(row.english, str) and row.english:
                    st.caption(f"English: {row.english}")
