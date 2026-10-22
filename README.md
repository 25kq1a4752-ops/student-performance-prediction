# Markbook: Student Performance Prediction System

Flask web app that predicts a student's likely final marks from attendance,
previous marks, assignment score and study hours, using a Random Forest model.

## Features
- Sign up and log in with your own username and password; each account sees only its own students
- Add students and term-by-term records (SQLite)
- ML prediction with an explanation of which factors helped or hurt
- Class dashboard with charts, search and filters
- Per-student progress chart and improvement suggestions

## Run in VS Code
```
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python train_model.py          # trains the model, prints accuracy
python seed_demo.py            # optional: adds 15 demo students
python app.py
```
Open http://127.0.0.1:5000 and click **Create an account**. If you ran `seed_demo.py`, you can also log in as **demo / demo12345**.

Before putting it on the internet: set a `SECRET_KEY` environment variable, serve it with a production server (for example `gunicorn app:app`) over HTTPS, and do not set `FLASK_DEBUG`.
If you used the older single-teacher version, its database is kept as `students_old_backup.db`.

## Dataset
The first run creates a **synthetic** practice dataset (`data/students.csv`).
For your report, replace it with a real dataset (for example the UCI Student
Performance dataset) using columns: `attendance, previous_marks,
assignment_score, study_hours, final_marks`, then run `python train_model.py`.

## Files
- `app.py` routes, database, accounts
- `predictor.py` prediction, explanation, suggestions
- `train_model.py` dataset creation and model training
- `templates/`, `static/` web pages and styling

Predictions are estimates meant to guide support, not to make decisions about students.
