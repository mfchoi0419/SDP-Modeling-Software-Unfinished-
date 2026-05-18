# Project Notes

## What Was Cleaned

The GitHub-ready folder removes generated or machine-specific files such as virtual environments, cache folders, trained model binaries, SQLite databases, and previous training artifacts.

## What Was Annotated

Relevant Python files now include module-level documentation explaining their purpose. Important sections also include comments explaining why the code exists and how the major data/modeling steps work.

## Important Fixes Included

- Fixed the daily ambient average script so it groups by `temperature_c` instead of a non-existent `temp_c` column.
- Fixed the heat-loss lag feature name from `heat_loss_2_lag2` to `heat_loss_w_lag2`.
- Added NOAA helper functions used by `train_model.py`.
- Fixed `run_pipeline.py` argument/key typos that could prevent the pipeline from running correctly.
- Fixed an Open-Meteo result field typo in `open_meteo_history_ingest.py`.

## What Still Needs Real-World Testing

- Serial communication with Arduino hardware.
- Whether the SQLite schema matches all CSV and model expectations.
- Whether there are enough real biodigester rows for meaningful model training.
- Whether forecast-mode training has enough historical forecast rows to avoid falling back to NOAA mode.
date fix
