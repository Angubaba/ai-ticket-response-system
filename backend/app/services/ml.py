"""Local ML solution predictor: TF-IDF (word + char n-grams) -> Logistic Regression.

Each class label *is* the one-line solution, so prediction is a single supervised step
and the output is always a human-approved sentence (no free-text generation at this stage).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import classification_report
from sklearn.pipeline import FeatureUnion, Pipeline

from ..config import settings

log = logging.getLogger(__name__)

ESCALATION_SOLUTION = "Escalate to a human support agent for manual triage."


class ModelUnavailable(RuntimeError):
    pass


@dataclass
class Prediction:
    solution: str
    confidence: float
    category: str | None
    low_confidence: bool
    alternatives: list[tuple[str, float]]


def _text(subject: str, description: str) -> str:
    # subject is a strong signal, so repeat it to up-weight it
    return f"{subject}. {subject}. {description}"


def build_pipeline() -> Pipeline:
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, stop_words="english")),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2)),
        ]
    )
    clf = LogisticRegression(C=10.0, max_iter=2000, class_weight="balanced")
    return Pipeline([("features", features), ("clf", clf)])


def train(dataset_path: Path | None = None, model_path: Path | None = None) -> dict:
    dataset_path = dataset_path or settings.ml_dataset_path
    model_path = model_path or settings.ml_model_path

    df = pd.read_csv(dataset_path).dropna(subset=["subject", "description", "solution"])
    X = [_text(s, d) for s, d in zip(df["subject"], df["description"])]
    y = df["solution"].tolist()
    category_of = df.groupby("solution")["category"].agg(lambda s: s.mode().iat[0]).to_dict()

    # Honest-ish evaluation: stratified 5-fold CV predictions
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    preds = cross_val_predict(build_pipeline(), X, y, cv=cv)
    report = classification_report(y, preds, output_dict=True, zero_division=0)

    pipe = build_pipeline().fit(X, y)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipe, "category_of": category_of}, model_path)

    return {
        "rows": len(df),
        "classes": len(set(y)),
        "cv_accuracy": round(report["accuracy"], 4),
        "cv_macro_f1": round(report["macro avg"]["f1-score"], 4),
        "model_path": str(model_path),
    }


class SolutionModel:
    def __init__(self, model_path: Path | None = None, min_confidence: float | None = None):
        self.model_path = model_path or settings.ml_model_path
        self.min_confidence = settings.ml_min_confidence if min_confidence is None else min_confidence
        self._bundle = None
        self._lock = threading.Lock()

    def _load(self):
        if self._bundle is not None:
            return self._bundle
        with self._lock:
            if self._bundle is None:
                if not Path(self.model_path).exists():
                    raise ModelUnavailable(
                        f"ML model file not found at {self.model_path}. Run `python -m app.cli train`."
                    )
                try:
                    self._bundle = joblib.load(self.model_path)
                except Exception as e:  # corrupt / incompatible sklearn version
                    raise ModelUnavailable(f"ML model could not be loaded: {e}") from e
        return self._bundle

    @property
    def available(self) -> bool:
        try:
            self._load()
            return True
        except ModelUnavailable:
            return False

    def predict(self, subject: str, description: str) -> Prediction:
        bundle = self._load()
        pipe: Pipeline = bundle["pipeline"]
        proba = pipe.predict_proba([_text(subject, description)])[0]
        order = np.argsort(proba)[::-1]
        classes = pipe.classes_
        top = int(order[0])
        conf = float(proba[top])
        alts = [(str(classes[i]), round(float(proba[i]), 4)) for i in order[1:3]]

        if conf < self.min_confidence:
            return Prediction(ESCALATION_SOLUTION, conf, None, True, [(str(classes[top]), round(conf, 4)), *alts])
        return Prediction(
            solution=str(classes[top]),
            confidence=round(conf, 4),
            category=bundle["category_of"].get(str(classes[top])),
            low_confidence=False,
            alternatives=alts,
        )


_model: SolutionModel | None = None


def get_model() -> SolutionModel:
    global _model
    if _model is None:
        _model = SolutionModel()
    return _model
