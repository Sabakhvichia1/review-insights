"""Load the raw Olist CSVs and Amazon Beauty reviews into one DuckDB file.

Run once after downloading the data:
    python src/load_data.py
"""

import duckdb

from paths import DB_PATH, RAW_AMAZON, RAW_OLIST, read_sql

OLIST_TABLES = {
    "olist_orders": "olist_orders_dataset.csv",
    "olist_reviews": "olist_order_reviews_dataset.csv",
    "olist_items": "olist_order_items_dataset.csv",
    "olist_products": "olist_products_dataset.csv",
    "olist_customers": "olist_customers_dataset.csv",
    "olist_sellers": "olist_sellers_dataset.csv",
    "olist_category_names": "product_category_name_translation.csv",
}


def load_olist(con: duckdb.DuckDBPyConnection) -> None:
    for table, filename in OLIST_TABLES.items():
        path = RAW_OLIST / filename
        if not path.exists():
            raise SystemExit(f"Missing {path}. Download the Olist dataset from Kaggle first.")
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT * FROM read_csv(?, header = true, quote = '\"', escape = '\"')",
            [str(path)],
        )
        rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table:<22} {rows:>8,} rows")


def load_amazon(con: duckdb.DuckDBPyConnection) -> None:
    if not RAW_AMAZON.exists():
        raise SystemExit(f"Missing {RAW_AMAZON}.")
    # Keep 2016-2018 so the period matches Olist. The user id is only used to
    # build a stable review id and is not stored. About 2,000 reviews appear
    # more than once in the file; DISTINCT ON keeps one copy.
    con.execute(
        """
        CREATE OR REPLACE TABLE amazon_reviews AS
        SELECT DISTINCT ON (review_id) * FROM (
        SELECT
            'amz_' || md5(user_id || asin || CAST("timestamp" AS VARCHAR)) AS review_id,
            CAST(rating AS INTEGER)                  AS rating,
            title,
            "text"                                   AS review_text,
            parent_asin                              AS product_id,
            epoch_ms("timestamp")                    AS reviewed_at,
            helpful_vote,
            verified_purchase
        FROM read_json(
            ?,
            format = 'newline_delimited',
            columns = {
                rating: 'DOUBLE', title: 'VARCHAR', "text": 'VARCHAR',
                asin: 'VARCHAR', parent_asin: 'VARCHAR', user_id: 'VARCHAR',
                "timestamp": 'BIGINT', helpful_vote: 'INTEGER', verified_purchase: 'BOOLEAN'
            }
        )
        WHERE epoch_ms("timestamp") BETWEEN TIMESTAMP '2016-01-01' AND TIMESTAMP '2018-12-31 23:59:59'
        )
        """,
        [str(RAW_AMAZON)],
    )
    rows = con.execute("SELECT count(*) FROM amazon_reviews").fetchone()[0]
    print(f"{'amazon_reviews':<22} {rows:>8,} rows (2016-2018)")


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    load_olist(con)
    load_amazon(con)
    con.execute(read_sql("01_views.sql"))
    print("Views created: olist_order_facts, olist_review_facts, low_rating_reviews, "
          "label_sample, hand_label_sample")
    con.close()


if __name__ == "__main__":
    main()
