from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_OLIST = DATA / "raw" / "olist"
RAW_AMAZON = DATA / "raw" / "amazon" / "All_Beauty.jsonl"
DB_PATH = DATA / "reviews.duckdb"
SQL = ROOT / "sql"
LABELS = DATA / "labels"
PROCESSED = DATA / "processed"

LLM_LABELS = LABELS / "llm_labels.csv"
HAND_LABELS = LABELS / "hand_labels.csv"
TRANSLATIONS = PROCESSED / "translations.csv"


def read_sql(name: str) -> str:
    return (SQL / name).read_text(encoding="utf-8")
