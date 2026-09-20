# Input data contract

Place only authorized production inputs under `data/input/`, or override the location with `REPLICATION_DATA_PATH` / `--data-path`. The input directory is ignored by Git.

The repository currently has no complete schema because the original production strategy adapter is unavailable. The adapter must validate its exact files, collections, fields, point-in-time rules, dates, and coverage before calculation. It must fail when required observations are missing and must not substitute demo or synthetic data.
