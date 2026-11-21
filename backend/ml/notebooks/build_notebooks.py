"""Generate the ML notebooks (then execute them with `python ml/notebooks/run_notebooks.py`).

Each notebook walks through EDA -> cleaning -> feature engineering -> train/test split ->
cross-validated comparison of at least two models -> metrics -> final choice, and ends by
calling the production pipeline's `train()`, which saves the .joblib + metrics JSON. The
notebooks reuse ml/pipelines/* so exploration and production can never drift apart.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent

SETUP = """\
import os, sys, warnings
from pathlib import Path

BACKEND = Path.cwd().resolve().parents[1]  # backend/ml/notebooks -> backend
sys.path.insert(0, str(BACKEND))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

pd.set_option("display.max_columns", 30)
plt.rcParams.update({"figure.figsize": (8, 4), "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3})
BLUE = "#2a78d6"
"""

DJANGO_SETUP = """\
# The forecast uses our own CRM data, so this notebook boots Django (SQLite/Postgres per .env).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"  # Jupyter runs an event loop
import django
django.setup()
"""


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def notebook(cells) -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.metadata["language_info"] = {"name": "python"}
    return nb


LEAD_SCORING = [
    md("""
# Lead scoring: which leads will convert?

**Goal:** predict the probability that a lead converts, explain *why* with SHAP, and use it
as a 0-100 score (hot ≥ 70, warm 40-69, cold < 40) on every lead in LeadPilot.

**Data:** the public *X Education* lead scoring dataset (Kaggle): 9,240 leads of an online
education company, target `Converted`.

**The key constraint:** the model must score *our* CRM leads, which don't have X Education's
columns. So we map both onto five features our CRM can also compute (see `ml/features.py`).
"""),
    code(SETUP),
    code("""
from ml.pipelines import datasets, lead_score
raw = datasets.load_leads()
print(raw.shape)
raw.head(3)
"""),
    md("## 1. Exploratory data analysis"),
    code("""
print("Conversion rate:", round(raw["Converted"].mean(), 3))
missing = raw.isna().mean().sort_values(ascending=False)
missing[missing > 0].head(12).round(3).to_frame("share missing")
"""),
    code("""
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
raw.groupby("Lead Source")["Converted"].agg(["mean", "size"]).query("size > 50") \\
   .sort_values("mean")["mean"].plot.barh(ax=axes[0], color=BLUE, title="Conversion rate by lead source")
raw.groupby("Last Activity")["Converted"].agg(["mean", "size"]).query("size > 50") \\
   .sort_values("mean")["mean"].plot.barh(ax=axes[1], color=BLUE, title="Conversion rate by last activity")
plt.tight_layout()
"""),
    code("""
fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))
for ax, col in zip(axes, ["TotalVisits", "Total Time Spent on Website"]):
    for label, grp in raw.groupby("Converted"):
        ax.hist(grp[col].clip(upper=grp[col].quantile(0.99)), bins=30, alpha=0.6,
                label="converted" if label else "not converted")
    ax.set_title(col); ax.legend()
plt.tight_layout()
"""),
    md("""
**Observations**
- 38.5% convert: imbalanced, but mildly. Class weights are enough; SMOTE is compared below.
- Time on the website separates the classes far better than visit count.
- "SMS Sent" and phone conversations convert 2-7x better than chat-widget leads.
- Many profile columns (`Specialization`, `City`, `Tags`…) are mostly blank or 'Select'
  placeholders, and our CRM has no equivalent, so they are **not** used.
"""),
    md("## 2. Cleaning + feature mapping to the CRM's feature space"),
    code("""
X, y = lead_score.to_features(raw)
print(X.shape); X.head()
"""),
    code("""
pd.concat([X["source"].value_counts(), X.groupby("source").size().pipe(lambda s: y.groupby(X["source"]).mean().round(3))],
          axis=1, keys=["leads", "conversion rate"])
"""),
    md("""
Mapping decisions (documented in `ml/pipelines/lead_score.py`):
`Lead Import` → *cold*, `Lead Add Form` → *event*, Google/Bing/Facebook → *ads*,
Reference → *referral*, everything else → *web*. SMS/phone → *call*, email events → *email*,
trade-show visit → *meeting*. `TotalVisits` is capped at 30 (a few bots visit 250×) and
its ~1.5% missing values are median-imputed inside the pipeline.
"""),
    md("## 3. Train/test split + cross-validated model comparison"),
    code("""
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
comparison = lead_score.compare_models(X_train, y_train)
comparison.round(4)
"""),
    md("### Imbalance: class weights vs SMOTE"),
    code("""
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

cv = StratifiedKFold(5, shuffle=True, random_state=42)
smote_lr = ImbPipeline([("prep", lead_score.preprocessor()), ("smote", SMOTE(random_state=42)),
                        ("model", LogisticRegression(max_iter=2000))])
weighted_lr = lead_score.build(LogisticRegression(max_iter=2000, class_weight="balanced"))
pd.DataFrame({
    "class_weight='balanced'": cross_val_score(weighted_lr, X_train, y_train, cv=cv, scoring="f1"),
    "SMOTE": cross_val_score(smote_lr, X_train, y_train, cv=cv, scoring="f1"),
}).agg(["mean", "std"]).round(4)
"""),
    md("""
Both give near-identical F1 at this mild imbalance, so the production pipeline keeps the
simpler class weights (no synthetic rows, nothing extra to ship).
"""),
    md("## 4. Test-set evaluation of the best model"),
    code("""
from ml.pipelines.common import classification_metrics
best = comparison.iloc[0]["model"]
pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
model = lead_score.build(lead_score.candidates(pos_weight)[best]).fit(X_train, y_train)
proba = model.predict_proba(X_test)[:, 1]
test = classification_metrics(y_test, proba)
print(best); {k: v for k, v in test.items() if k not in ("confusion_matrix", "support")}
"""),
    code("""
from sklearn.metrics import RocCurveDisplay, ConfusionMatrixDisplay
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
RocCurveDisplay.from_predictions(y_test, proba, ax=axes[0], name=best, curve_kwargs={"color": BLUE})
ConfusionMatrixDisplay.from_predictions(y_test, (proba >= 0.5).astype(int), ax=axes[1], cmap="Blues", colorbar=False)
axes[1].grid(False); plt.tight_layout()
"""),
    md("## 5. Explainability with SHAP"),
    code("""
import shap
prep, est = model.named_steps["prep"], model.named_steps["model"]
Xt = prep.transform(X_test.iloc[:500])
Xt = Xt.toarray() if hasattr(Xt, "toarray") else Xt
names = list(prep.get_feature_names_out())
explainer = shap.TreeExplainer(est) if best != "logistic_regression" else shap.LinearExplainer(est, Xt)
values = explainer.shap_values(Xt)
values = values[1] if isinstance(values, list) else values
shap.summary_plot(values, Xt, feature_names=names, show=False, plot_size=(8, 4.5))
"""),
    md(
        "Per-lead explanations, as stored in `Lead.score_explanation` and shown in the *Why?* popover:"
    ),
    code("""
for factors in lead_score.explain(model, X_test.iloc[:2]):
    print([(f["label"], f["value"], f["direction"], f["impact"]) for f in factors])
"""),
    md("""
## 6. Final choice

The model with the highest mean 5-fold CV ROC-AUC is chosen (shown above), evaluated once on
the untouched 20% test set, then refit on all data and saved. Tree boosting wins because the
signal is non-linear (time on site saturates; last-activity interacts with source).
Runtime explanations use XGBoost's built-in TreeSHAP (`pred_contribs`), so the web app
doesn't need to import `shap`.
"""),
    code("""
metrics = lead_score.train(save=True)
{k: metrics[k] for k in ("chosen_model", "rows", "positive_rate")} | {"test_roc_auc": metrics["test"]["roc_auc"]}
"""),
]

CHURN = [
    md("""
# Churn: which customers are likely to leave?

**Data:** IBM *Telco Customer Churn* (7,043 customers, target `Churn`).
**Output in LeadPilot:** `Contact.churn_risk` (probability) for every customer with a won deal.

Money is in USD per month in Telco but in rupee deals in our CRM, so spend and product counts
are converted to **percentile ranks within each dataset**. Tenure stays in months.
"""),
    code(SETUP),
    code("""
from ml.pipelines import churn, datasets
raw = datasets.load_telco()
print(raw.shape, "churn rate:", round((raw["Churn"] == "Yes").mean(), 3))
raw.head(3)
"""),
    md("## 1. EDA"),
    code("""
raw["TotalCharges"] = pd.to_numeric(raw["TotalCharges"], errors="coerce")
print("Blank TotalCharges:", raw["TotalCharges"].isna().sum(), "(all tenure 0:",
      raw.loc[raw["TotalCharges"].isna(), "tenure"].eq(0).all(), ")")
fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))
raw.groupby("Contract")["Churn"].apply(lambda s: (s == "Yes").mean()).plot.bar(ax=axes[0], color=BLUE, title="Churn by contract", rot=0)
for label, grp in raw.groupby("Churn"):
    axes[1].hist(grp["tenure"], bins=24, alpha=0.6, label=f"churn={label}")
    axes[2].hist(grp["MonthlyCharges"], bins=24, alpha=0.6, label=f"churn={label}")
axes[1].set_title("Tenure (months)"); axes[2].set_title("Monthly charges"); axes[1].legend()
plt.tight_layout()
"""),
    md("""
- Month-to-month customers churn ~4x more than 2-year contracts → a *commitment* feature.
- New customers (low tenure) and high monthly charges churn more.
- The 11 blank `TotalCharges` are brand-new customers (tenure 0): filled with 0, not dropped.
"""),
    md("## 2. Feature mapping"),
    code("""
X, y = churn.to_features(raw)
X.describe().round(3)
"""),
    md("## 3. Split + cross-validated comparison"),
    code("""
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
comparison = churn.compare_models(X_train, y_train)
comparison.round(4)
"""),
    code("""
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
cv = StratifiedKFold(5, shuffle=True, random_state=42)
pd.DataFrame({
    "class_weight='balanced'": cross_val_score(churn.build(LogisticRegression(max_iter=2000, class_weight="balanced")), X_train, y_train, cv=cv, scoring="f1"),
    "SMOTE": cross_val_score(ImbPipeline([("scale", StandardScaler()), ("smote", SMOTE(random_state=42)), ("model", LogisticRegression(max_iter=2000))]), X_train, y_train, cv=cv, scoring="f1"),
}).agg(["mean", "std"]).round(4)
"""),
    md("## 4. Test-set evaluation"),
    code("""
from ml.pipelines.common import classification_metrics
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay
best = comparison.iloc[0]["model"]
pw = float((y_train == 0).sum() / (y_train == 1).sum())
model = churn.build(churn.candidates(pw)[best]).fit(X_train, y_train)
proba = model.predict_proba(X_test)[:, 1]
test = classification_metrics(y_test, proba)
print(best, {k: round(v, 4) for k, v in test.items() if isinstance(v, float)})
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
RocCurveDisplay.from_predictions(y_test, proba, ax=axes[0], name=best, curve_kwargs={"color": BLUE})
ConfusionMatrixDisplay.from_predictions(y_test, (proba >= 0.5).astype(int), ax=axes[1], cmap="Blues", colorbar=False)
axes[1].grid(False); plt.tight_layout()
"""),
    md("""
## 5. Final choice

Highest CV ROC-AUC wins. With class weights the model trades precision for **recall**: for
churn that's the right trade (missing a leaving customer costs more than an extra check-in).
In the CRM, *committed* = repeat buyer or a deal currently in proposal/negotiation.
"""),
    code("""
metrics = churn.train(save=True)
{k: metrics[k] for k in ("chosen_model", "rows")} | {"test_roc_auc": metrics["test"]["roc_auc"], "test_recall": metrics["test"]["recall"]}
"""),
]

SEGMENTATION = [
    md("""
# Segmentation: RFM + K-Means

**Data:** UCI *Online Retail* (UK e-commerce transactions, Dec 2010 - Dec 2011).
**Output in LeadPilot:** `Contact.segment` ∈ {Champions, Loyal, At Risk, Lost} for customers.

RFM = **R**ecency (days since last purchase), **F**requency (number of orders),
**M**onetary (total spend). Converted to percentile scores (1 = best) so UK basket values and
rupee B2B deals live on the same 0-1 scale.
"""),
    code(SETUP),
    code("""
from ml.pipelines import datasets, segment
raw = datasets.load_retail()
print(raw.shape); raw.head(3)
"""),
    md("## 1. Cleaning"),
    code("""
print("no customer id:", raw["CustomerID"].isna().sum(),
      "| cancellations:", raw["InvoiceNo"].astype(str).str.startswith("C").sum(),
      "| non-positive qty/price:", ((raw["Quantity"] <= 0) | (raw["UnitPrice"] <= 0)).sum())
tx = segment.clean_retail(raw)
print("clean transactions:", len(tx), "customers:", tx["CustomerID"].nunique())
"""),
    md("## 2. RFM features"),
    code("""
rfm = segment.rfm_table(tx)
fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))
for ax, col in zip(axes, rfm.columns):
    ax.hist(np.log1p(rfm[col]), bins=40, color=BLUE); ax.set_title(f"log(1 + {col})")
plt.tight_layout()
rfm.describe().round(1)
"""),
    md(
        "Heavily skewed (a few huge wholesale buyers), which is another reason to use percentile scores rather than raw values."
    ),
    code("""
scores = segment.rfm_scores(rfm)
scores.describe().round(3)
"""),
    md("## 3. Choosing k: elbow + silhouette"),
    code("""
k_table = segment.evaluate_k(scores)
fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))
axes[0].plot(k_table["k"], k_table["inertia"], marker="o", color=BLUE); axes[0].set_title("Inertia (elbow)")
axes[1].bar(k_table["k"], k_table["silhouette"], color=BLUE); axes[1].set_title("Silhouette")
plt.tight_layout(); k_table.round(3)
"""),
    md("""
k=2 has the highest silhouette but only says "good vs bad". The inertia curve bends at
k=3-4, and k=4 maps onto the four standard RFM segments the sales team can act on, so we
take **k=4** and report its silhouette honestly alongside the others.
"""),
    md("## 4. Fit, name and profile the segments"),
    code("""
metrics = segment.train(save=True)
pd.DataFrame(metrics["profile"])
"""),
    code("""
pd.DataFrame(metrics["centroids"]).T.round(3)
"""),
    md("""
Names come from centroids: highest R+F+M → **Champions**, lowest → **Lost**, of the middle two
the one with lower recency → **At Risk** (they used to buy), the other → **Loyal**.
"""),
]

SENTIMENT = [
    md("""
# Ticket sentiment → automatic priority

**Data:** UCI *Sentiment Labelled Sentences*: 3,000 review sentences from Amazon, Yelp and
IMDb labelled positive (1) / negative (0).

**In LeadPilot:** every ticket gets `sentiment` (positive / neutral / negative),
`sentiment_score` (-1…+1) and a priority:
negative **and** urgent → high; negative **or** urgent → medium; otherwise low.
"""),
    code(SETUP),
    code("""
from ml.pipelines import datasets, sentiment
df = datasets.load_sentiment()
print(df.shape); print(df.groupby("source")["label"].agg(["size", "mean"]))
df.sample(5, random_state=1)
"""),
    md("## 1. EDA"),
    code("""
df["words"] = df["text"].str.split().str.len()
df["words"].plot.hist(bins=40, color=BLUE, title="Words per sentence")
df["words"].describe().round(1)
"""),
    md(
        "Perfectly balanced (50/50) and short texts. TF-IDF on unigrams + bigrams is a strong baseline for this size."
    ),
    md("## 2. Split + compare TF-IDF + Logistic Regression vs Naive Bayes"),
    code("""
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(df["text"], df["label"], test_size=0.2, stratify=df["label"], random_state=42)
comparison = sentiment.compare_models(X_train, y_train)
comparison.round(4)
"""),
    md("## 3. Test-set evaluation"),
    code("""
from sklearn.metrics import classification_report, ConfusionMatrixDisplay
best = comparison.iloc[0]["model"]
model = sentiment.candidates()[best].fit(X_train, y_train)
print(best)
print(classification_report(y_test, model.predict(X_test), target_names=["negative", "positive"]))
ConfusionMatrixDisplay.from_predictions(y_test, model.predict(X_test), display_labels=["negative", "positive"], cmap="Blues", colorbar=False)
plt.grid(False)
"""),
    md("Most informative words (logistic regression coefficients):"),
    code("""
if best.endswith("logistic_regression"):
    vocab = np.array(model.named_steps["tfidf"].get_feature_names_out())
    coef = model.named_steps["model"].coef_[0]
    order = np.argsort(coef)
    print("negative:", ", ".join(vocab[order[:15]]))
    print("positive:", ", ".join(vocab[order[-15:]]))
"""),
    md("## 4. From sentiment to ticket priority"),
    code("""
examples = [
    "This is unacceptable! The app has been down all morning and our team can't log in. Fix it immediately.",
    "Please reset my password asap, I have a demo in an hour.",
    "The new reports page is confusing and slow, not happy with it.",
    "Can you send a copy of last month's invoice?",
    "Thanks, the support team was excellent and very friendly!",
]
pd.DataFrame(sentiment.classify(model, examples), index=[e[:60] + "…" for e in examples])
"""),
    md("""
## 5. Final choice and limits

Highest CV ROC-AUC wins (shown above). Reviews are not support tickets, so two safeguards:
a **neutral band** (0.40 < P(positive) < 0.60) avoids over-confident labels on factual
requests, and **urgency is a transparent keyword rule** (outage, can't log in, refund,
immediately…), because reviews never talk about urgency. Agents can always override the
priority; an overridden ticket is never re-prioritised by the model.
"""),
    code("""
metrics = sentiment.train(save=True)
{k: metrics[k] for k in ("chosen_model", "rows")} | {"test_roc_auc": metrics["test"]["roc_auc"], "test_f1": metrics["test"]["f1"]}
"""),
]

FORECAST = [
    md("""
# Sales forecast: next 3 months of won revenue

**Data:** LeadPilot's own won deals, summed per month (run `seed_demo` first for demo data).
**Candidates:** linear regression on lag-1/2/3 + trend + month-of-year seasonality, a smaller
trend + seasonality regression, a ridge (regularized) regression, and two baselines (naive and
3-month moving average), all scored in a **rolling-origin backtest** (each month predicted
only from earlier months: no peeking into the future).
"""),
    code(SETUP),
    code(DJANGO_SETUP),
    code("""
from django.utils import timezone
from ml import services
from ml.pipelines import forecast
closed = services._won_deals(None)
series = forecast.monthly_series(closed, end=pd.Timestamp(timezone.now()))
print(len(closed), "won deals over", len(series), "months")
series.tail(6).to_frame("revenue")
"""),
    md("## 1. EDA"),
    code("""
ax = series.plot(marker="o", color=BLUE, title="Won revenue per month (₹)")
ax.set_ylabel("₹"); plt.tight_layout()
"""),
    md("## 2. Features: lags, trend, seasonality"),
    code("""
forecast.design(series).tail(5).round(2)
"""),
    md("## 3. Rolling-origin backtest (last 6 months)"),
    code("""
bt = forecast.backtest(series)
methods = forecast.score_methods(bt)
display(methods.round(0))
ax = bt.set_index("month")[["actual", *forecast.METHODS]].plot(marker="o")
ax.set_title("Backtest: one-step-ahead predictions"); plt.tight_layout()
"""),
    md("""
**Final choice:** the method with the lowest backtest RMSE makes the forecast (first row
above). With only ~2 years of noisy monthly data, a simple baseline can beat the regressions:
the full lag model has 6 parameters for ~15 training rows and overfits. We report that honestly
instead of forcing the regression; as history grows, the trend/seasonality regressions get
more rows and the same selection rule will pick them when they genuinely win.
The band is ±1.96 × the chosen method's backtest RMSE (≈95% if errors are roughly normal),
widening by √h.
"""),
    md("## 4. Forecast"),
    code("""
result = forecast.forecast(series)
fc = pd.DataFrame(result["forecast"]).set_index("month")
hist = series.iloc[-12:]
ax = plt.gca()
ax.plot([str(p) for p in hist.index], hist.values, marker="o", color=BLUE, label="actual")
ax.plot(fc.index, fc["forecast"], marker="o", linestyle="--", color=BLUE, label=f"forecast ({result['chosen']})")
ax.fill_between(fc.index, fc["lower"], fc["upper"], color=BLUE, alpha=0.15, label="~95% range")
ax.legend(); plt.xticks(rotation=45); plt.tight_layout()
fc.round(0)
"""),
    code("""
metrics = forecast.train(closed, save=True)
{k: metrics.get(k) for k in ("chosen_model", "rows")} | metrics.get("test", {})
"""),
]

NOTEBOOKS = {
    "lead_scoring.ipynb": LEAD_SCORING,
    "churn.ipynb": CHURN,
    "segmentation.ipynb": SEGMENTATION,
    "ticket_sentiment.ipynb": SENTIMENT,
    "forecast.ipynb": FORECAST,
}


def main() -> None:
    for name, cells in NOTEBOOKS.items():
        nbf.write(notebook(cells), HERE / name)
        print("wrote", name)


if __name__ == "__main__":
    main()
