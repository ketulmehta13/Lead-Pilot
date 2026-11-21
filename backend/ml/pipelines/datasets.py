"""Public training datasets: where they come from and how to fetch them.

Run `python manage.py ml_download_data` once; files land in backend/ml/data/raw/ (gitignored).
"""

from __future__ import annotations

import io
import logging
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from .common import PROCESSED_DIR, RAW_DIR

logger = logging.getLogger(__name__)

DATASETS: dict[str, dict[str, str]] = {
    "leads": {
        "file": "leads_x_education.csv",
        "url": "https://raw.githubusercontent.com/shinde-chandrakant/Lead-Scoring-Case-Study/master/Leads.csv",
        "about": "X Education lead scoring (Kaggle), GitHub mirror. 9,240 leads, target `Converted`.",
    },
    "telco": {
        "file": "telco_churn.csv",
        "url": "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv",
        "about": "IBM Telco Customer Churn. 7,043 customers, target `Churn`.",
    },
    "retail": {
        "file": "online_retail.zip",
        "url": "https://archive.ics.uci.edu/static/public/352/online+retail.zip",
        "about": "UCI Online Retail (2010-2011 UK e-commerce transactions).",
    },
    "sentiment": {
        "file": "sentiment_sentences.zip",
        "url": "https://archive.ics.uci.edu/static/public/331/sentiment+labelled+sentences.zip",
        "about": "UCI Sentiment Labelled Sentences (Amazon, Yelp, IMDb). 3,000 sentences, 0/1.",
    },
}


def path(key: str) -> Path:
    return RAW_DIR / DATASETS[key]["file"]


def download(keys: list[str] | None = None, force: bool = False) -> list[Path]:
    """Download missing datasets (all by default)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    done = []
    for key in keys or list(DATASETS):
        target = path(key)
        if target.exists() and not force:
            done.append(target)
            continue
        logger.info("Downloading %s ...", DATASETS[key]["url"])
        request = urllib.request.Request(DATASETS[key]["url"], headers={"User-Agent": "leadpilot"})
        with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310 - fixed URLs
            target.write_bytes(response.read())
        done.append(target)
    return done


def _require(key: str) -> Path:
    p = path(key)
    if not p.exists():
        raise FileNotFoundError(f"{p.name} is missing. Run: python manage.py ml_download_data")
    return p


def load_leads() -> pd.DataFrame:
    return pd.read_csv(_require("leads"))


def load_telco() -> pd.DataFrame:
    return pd.read_csv(_require("telco"))


def load_retail() -> pd.DataFrame:
    """Online Retail as a DataFrame. The 23 MB .xlsx is slow to parse, so cache it as CSV."""
    cached = PROCESSED_DIR / "online_retail.csv"
    if cached.exists():
        return pd.read_csv(cached, dtype={"InvoiceNo": str, "StockCode": str},
                           parse_dates=["InvoiceDate"])  # fmt: skip
    with zipfile.ZipFile(_require("retail")) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".xlsx"))
        df = pd.read_excel(io.BytesIO(zf.read(name)), dtype={"InvoiceNo": str, "StockCode": str})
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cached, index=False)
    return df


def load_sentiment() -> pd.DataFrame:
    """3,000 labelled sentences: columns text, label (1 = positive), source."""
    frames = []
    with zipfile.ZipFile(_require("sentiment")) as zf:
        for name in zf.namelist():
            if name.endswith("_labelled.txt") and not name.startswith("__MACOSX"):
                source = Path(name).name.split("_")[0]
                rows = [
                    line.rsplit("\t", 1)
                    for line in zf.read(name).decode("utf-8", errors="replace").splitlines()
                    if "\t" in line
                ]
                frame = pd.DataFrame(rows, columns=["text", "label"])
                frame["source"] = source
                frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    df["text"] = df["text"].str.strip()
    df["label"] = df["label"].str.strip().astype(int)
    return df
