import os
import joblib
import numpy as np
import pandas as pd
from train_model import FEATURES, MODEL_PATH, train

FEATURE_LABELS = {
    "attendance": "Attendance (%)",
    "previous_marks": "Previous marks (%)",
    "assignment_score": "Assignment score (%)",
    "study_hours": "Study hours per day",
}
LIMITS = {"attendance": (0, 100), "previous_marks": (0, 100),
          "assignment_score": (0, 100), "study_hours": (0, 12)}
CATEGORY_LABELS = {"good": "Doing well", "watch": "Could use a boost", "support": "Needs extra support"}

_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        if not os.path.exists(MODEL_PATH):
            train()
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def category_for(score):
    if score >= 70:
        return "good"
    if score >= 50:
        return "watch"
    return "support"


def tips_for(v):
    tips = []
    if v["attendance"] < 75:
        tips.append(f"Attendance is {v['attendance']:.0f}%. Getting back above 75% is the quickest way to lift results.")
    if v["assignment_score"] < 60:
        tips.append("Assignment scores are low. Start each assignment within a day of getting it and ask for feedback on the last one.")
    if v["study_hours"] < 2:
        tips.append("Study time is under 2 hours a day. Try two focused 45-minute sessions, with phone away.")
    if v["previous_marks"] < 50:
        tips.append("Earlier marks show gaps in basics. Revisit the weakest topics from the last exam before starting new ones.")
    if not tips:
        tips.append("Habits look healthy. Keep the routine and try past papers to stay sharp.")
    return tips


def predict_student(v):
    b = _load()
    model, means = b["model"], b["means"]
    x = pd.DataFrame([[v[f] for f in FEATURES]], columns=FEATURES)
    score = float(np.clip(model.predict(x)[0], 0, 100))
    contribs = []
    for f in FEATURES:
        x2 = x.copy()
        x2[f] = means[f]  # what if this factor were average?
        impact = score - float(model.predict(x2)[0])
        contribs.append({"label": FEATURE_LABELS[f], "impact": round(impact, 1)})
    contribs.sort(key=lambda c: abs(c["impact"]), reverse=True)
    return {"score": round(score, 1), "category": category_for(score),
            "contributions": contribs, "tips": tips_for(v), "mae": round(b["mae"], 1)}
