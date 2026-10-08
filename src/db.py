"""Read-only access to the DuckDB file, with the label CSVs available as tables."""

import duckdb
import pandas as pd

from paths import DB_PATH, HAND_LABELS, LLM_LABELS, TRANSLATIONS, read_sql

LABEL_FILES = {
    "llm_labels": (LLM_LABELS, ["source", "review_id", "primary_issue", "mentions_delivery", "model", "labeled_at"]),
    "hand_labels": (HAND_LABELS, ["source", "review_id", "primary_issue", "labeled_at"]),
    "translations": (TRANSLATIONS, ["source", "review_id", "english"]),
}


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for name, (path, columns) in LABEL_FILES.items():
        df = pd.read_csv(path, dtype=str) if path.exists() else pd.DataFrame(columns=columns, dtype=str)
        if name == "llm_labels":
            df["mentions_delivery"] = df["mentions_delivery"].map({"True": True, "False": False})
        con.register(name, df)
    return con


def query(con: duckdb.DuckDBPyConnection, sql_file: str) -> pd.DataFrame:
    return con.execute(read_sql(sql_file)).df()
