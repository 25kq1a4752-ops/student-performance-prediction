"""Train the prediction model.

Run:  python train_model.py

If data/students.csv does not exist, a synthetic practice dataset is created.
To use real data, put your own CSV at data/students.csv with these columns:
attendance, previous_marks, assignment_score, study_hours, final_marks
"""
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE, "data", "students.csv")
MODEL_PATH = os.path.join(BASE, "model", "model.joblib")
FEATURES = ["attendance", "previous_marks", "assignment_score", "study_hours"]
TARGET = "final_marks"


def make_synthetic(n=1500, seed=42):
    rng = np.random.default_rng(seed)
    attendance = np.clip(rng.normal(80, 12, n), 35, 100)
    previous = np.clip(rng.normal(65, 15, n), 15, 100)
    assignment = np.clip(0.4 * previous + 0.6 * rng.normal(70, 14, n), 10, 100)
    study = np.clip(rng.normal(2.5, 1.2, n), 0, 8)
    final = (0.45 * previous + 0.20 * assignment + 0.20 * attendance
             + 2.5 * np.minimum(study, 5) + rng.normal(0, 4, n))
    df = pd.DataFrame({
        "attendance": attendance.round(1),
        "previous_marks": previous.round(1),
        "assignment_score": assignment.round(1),
        "study_hours": study.round(1),
        TARGET: np.clip(final, 0, 100).round(1),
    })
    return df


def train():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    if not os.path.exists(DATA_PATH):
        make_synthetic().to_csv(DATA_PATH, index=False)
        print("Created synthetic dataset at", DATA_PATH)
    df = pd.read_csv(DATA_PATH).dropna(subset=FEATURES + [TARGET])
    X, y = df[FEATURES], df[TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=200, min_samples_leaf=3, random_state=42, n_jobs=-1)
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    mae, r2 = mean_absolute_error(y_te, pred), r2_score(y_te, pred)
    print(f"Test MAE: {mae:.2f} marks | R2: {r2:.3f} | rows: {len(df)}")
    # refit on all data for the final model
    model.fit(X, y)
    joblib.dump({"model": model, "means": X.mean().to_dict(), "mae": mae, "r2": r2}, MODEL_PATH)
    print("Saved model to", MODEL_PATH)


if __name__ == "__main__":
    train()
