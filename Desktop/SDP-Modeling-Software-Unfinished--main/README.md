# SDP Modeling Software

This repository contains the Python modeling and data-pipeline software for a Senior Design biodigester/CHP system. The software ingests weather and biodigester operating data, stores data in SQLite, trains machine-learning models, evaluates model health, and can send a predicted CHP runtime command to an Arduino-based controller.

## Project Goals

- Predict whether the biodigester will need heat.
- Estimate next-day temperature or heat-loss behavior from weather/history data.
- Backfill weather history from Open-Meteo.
- Append daily Open-Meteo forecasts for future model inputs.
- Train and evaluate Random Forest models.
- Support future integration with a CHP engine controller.

## Main Files

| File | Purpose |
|---|---|
| `run_pipeline.py` | End-to-end pipeline for optional ingestion, weather backfill, training, evaluation, and artifact creation. |
| `data_loader.py` | Shared SQL loading, feature engineering, lag features, and heat-loss calculations. |
| `forecast_ingest.py` | Downloads Open-Meteo forecast data and writes it to SQLite. |
| `open_meteo_history_ingest.py` | Backfills historical weather data from Open-Meteo archive data. |
| `ingest.py` | Generic CSV/XLSX-to-SQLite ingester controlled by `sources.json`. |
| `train_model.py` | Trains a weather-based Random Forest regression model. |
| `train_heat_classifier.py` | Trains a classifier for whether the biodigester needs heat tomorrow. |
| `evaluate_model_health.py` | Compares a trained model against recent rows and a baseline. |
| `run_controller.py` | Uses trained models to compute runtime and send a command over serial. |
| `read_ambient_temp.py` | Reads Arduino serial temperature output and appends a daily CSV row. |

## Folder Structure

```text
SDP-Modeling-Software/
├── Data/                       # CSV datasets used for training and inspection
├── Initializers/               # Database setup and labeling helpers
├── sources.json                # Column mapping configuration for ingestion
├── run_pipeline.py             # Main workflow
├── data_loader.py              # Feature engineering/data loading utilities
├── requirements.txt            # Python dependencies
├── .gitignore                  # Files intentionally excluded from GitHub
└── README.md                   # Project documentation
```

## Files Intentionally Excluded from GitHub

The cleaned version excludes files that are either machine-specific, generated, or too large for normal GitHub commits:

- `.venv/`
- `__pycache__/`
- `.DS_Store`
- `*.pkl` trained model files
- `*.db` SQLite database files
- `artifacts/` generated model runs

These files can be regenerated locally by running the setup and training scripts.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize the SQLite database:

```bash
python Initializers/db_init.py
```

## Example Commands

Backfill weather history and train the pipeline:

```bash
python run_pipeline.py
```

Fetch forecast data during the pipeline run:

```bash
python run_pipeline.py --fetch-forecast
```

Train the NOAA-only temperature model:

```bash
python train_model.py
```

Train the heat/no-heat classifier:

```bash
python train_heat_classifier.py
```

Read one ambient temperature from Arduino serial and append a daily row:

```bash
python read_ambient_temp.py
```

## Notes for Future Development

- Update the serial port in `run_controller.py` and `read_ambient_temp.py` to match the machine running the code.
- Keep generated model files and databases out of GitHub unless there is a specific reason to track them.
- Use `artifacts/` for generated model outputs and evaluation metrics.
- Add more rows to the biodigester dataset for better model performance.

## Suggested GitHub Topics

`python`, `machine-learning`, `random-forest`, `biodigester`, `renewable-energy`, `weather-data`, `chemical-engineering`, `forecasting`, `sqlite`, `senior-design`
