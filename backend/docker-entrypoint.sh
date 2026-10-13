#!/bin/sh
set -e
# Train the ML model on first start (takes a few seconds), then serve.
if [ ! -f "${ML_MODEL_PATH:-models/solution_model.joblib}" ]; then
  echo "Training ML model..."
  python -m app.cli train
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
