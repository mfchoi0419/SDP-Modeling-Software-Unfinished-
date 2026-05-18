"""
train_heat_classifier.py

Purpose:
    Trains a classifier that predicts whether the biodigester is likely to need heat tomorrow.

Notes:
    This file is part of the Senior Design biodigester/CHP modeling software.
    Comments were added to make the repository easier to review on GitHub.
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib
from pathlib import Path

THRESHOLD_TEMP = 35.0
DATA_PATH = Path("Data/Biodigester_daily_data.csv")
MODEL_PATH = Path("heat_classifier_model.pkl")

print(f"Loading data from:  {DATA_PATH.resolve()}")

if not DATA_PATH.exists():
    raise FileNotFoundError(f"Could not find {DATA_PATH}. Check the path and filename.")

data = pd.read_csv(DATA_PATH)

if "needs_heat_tomorrow" not in data.columns:
    raise ValueError("needs_heat_tomorrow column missing. Run add_heat_label.py first")

feature_cols = ["ambient_T_avg_today"]

X = data[feature_cols]
y = data["needs_heat_tomorrow"]

print(f"Dataset shape: {X.shape}, labels: {y.unique()}")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

clf = RandomForestClassifier(
    n_estimators=200,
    max_depth=None,
    random_state=42
)

clf.fit(X_train, y_train)

y_pred = clf.predict(X_test)

acc = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, zero_division=0)
rec = recall_score(y_test, y_pred, zero_division=0)

print(f"Accuracy:  {acc:.3f}")
print(f"Precision: {prec:.3f}")
print(f"Recall:    {rec:.3f}")

joblib.dump(clf, MODEL_PATH)
print(f"Classifier model saved to {MODEL_PATH.resolve()}")
