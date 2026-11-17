import os
import subprocess
import sys
import tempfile
import time

import pandas as pd

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))

from default import ERSILIA_MODEL_IDS

bucket = "isaura-public"

# The isaura-public MinIO backend occasionally throttles multipart uploads
# ("please reduce your request rate") when too many parts land concurrently.
# Isaura already retries 3x internally with only a 1s sleep, which usually
# isn't enough backoff, so a busy server can still fail the whole push.
# Trim concurrency/part-count here (without overriding anything the caller
# already set) and retry the CLI call itself with longer backoff so one
# transient throttle doesn't abort the rest of the model loop.
os.environ.setdefault("MINIO_MAX_CONCURRENCY", "3")
os.environ.setdefault("MINIO_MULTIPART_CHUNKSIZE", str(32 * 1024 * 1024))

ISAURA_RETRIES = 4
ISAURA_BACKOFF_SECONDS = 20


def run_isaura(args, retries=ISAURA_RETRIES, backoff=ISAURA_BACKOFF_SECONDS):
    """Run an isaura CLI command, retrying with backoff on transient failures."""
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(args, check=True)
            return
        except subprocess.CalledProcessError:
            if attempt == retries:
                raise
            wait = backoff * attempt
            print(f"  {' '.join(args)} failed (attempt {attempt}/{retries}); retrying in {wait}s...")
            time.sleep(wait)


dest_dir = os.path.join(root, "..", "output", "ersilia_precalculations")
tmp_inputs = os.path.join(dest_dir, "batch_inputs")
tmp_outputs = os.path.join(dest_dir, "batch_outputs")

input_files = sorted([f for f in os.listdir(tmp_inputs) if f.startswith("smiles_") and f.endswith(".csv")])
input_numbers = set(int(f.replace("smiles_", "").replace(".csv", "")) for f in input_files)


for model_id, model_version in ERSILIA_MODEL_IDS.items():
    # outputs live in batch_outputs/<model>_<version>/<model>_<version>_<NNN>.csv
    run_name = f"{model_id}_{model_version}"
    output_folder = os.path.join(tmp_outputs, run_name)
    files = sorted([f for f in os.listdir(output_folder) if f.startswith(run_name + "_") and f.endswith(".csv")])
    print(f"Model ID: {model_id}, Model Version: {model_version}, Number of output files: {len(files)}")

    # Combine all batches into a single deduplicated input file for one "isaura write" call
    # per model, instead of one per batch.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        combined_path = tmp.name

    seen_keys = set()
    total_rows = 0
    header_written = False
    for file in files:
        src_path = os.path.join(output_folder, file)
        df = pd.read_csv(src_path)

        # Some models occasionally leave a blank/whitespace value instead of a real
        # prediction for a given molecule. A single such value makes pandas read that
        # whole column as object/string for this file, and concatenating files with
        # mixed float/string dtypes for the same column later breaks isaura's typed
        # parquet writer. Coerce every non-key/input column to numeric here so dtypes
        # stay consistent across all batches, turning any unparseable value into NaN.
        value_cols = [c for c in df.columns if c not in ("key", "input")]
        df[value_cols] = df[value_cols].apply(pd.to_numeric, errors="coerce")

        n_rows_before = len(df)
        # Drop duplicate keys before pushing anything - within this batch, or already
        # seen in an earlier one - so isaura's unique-key constraint never trips.
        df = df.drop_duplicates(subset="key", keep="first")
        df = df.loc[~df["key"].isin(seen_keys)]
        n_dupes = n_rows_before - len(df)
        if n_dupes:
            print(f"  {file}: dropping {n_dupes} duplicate-key row(s) (within this batch or already seen in an earlier one)")
        else:
            print(f"  {file}: 0 duplicates")
        seen_keys.update(df["key"])
        df.to_csv(combined_path, mode="a", header=not header_written, index=False)
        header_written = True
        total_rows += len(df)

    print(f"Writing {total_rows} rows for model {model_id} to Isaura Local via CLI...")
    try:
        run_isaura(["isaura", "write", "-i", combined_path, "-pn", bucket, "-m", model_id, "-v", model_version])
    finally:
        os.remove(combined_path)

    print(f"Pushing {model_id} to Isaura Cloud via CLI...")
    run_isaura(["isaura", "push", "-pn", bucket, "-m", model_id, "-v", model_version])
