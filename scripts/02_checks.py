import os
import pandas as pd
from tqdm import tqdm
import sys


root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))

from default import ERSILIA_MODEL_IDS

dest_dir = os.path.join(root, "..", "output", "ersilia_precalculations")
tmp_inputs = os.path.join(dest_dir, "batch_inputs")
tmp_outputs = os.path.join(dest_dir, "batch_outputs")

input_files = sorted([f for f in os.listdir(tmp_inputs) if f.startswith("smiles_") and f.endswith(".csv")])
input_numbers = set(int(f.replace("smiles_", "").replace(".csv", "")) for f in input_files)
print(f"Total input files: {len(input_files)}")
print(f"Input file range: {min(input_numbers):03d} to {max(input_numbers):03d}\n")

expected_rows = {}
for f in input_files:
    batch_num = int(f.replace("smiles_", "").replace(".csv", ""))
    with open(os.path.join(tmp_inputs, f), "r") as fh:
        expected_rows[batch_num] = sum(1 for line in fh if line.strip()) - 1  # exclude header

for model_id, model_version in ERSILIA_MODEL_IDS.items():
    # outputs live in batch_outputs/<model>_<version>/<model>_<version>_<NNN>.csv
    run_name = f"{model_id}_{model_version}"
    output_folder = os.path.join(tmp_outputs, run_name)
    if not os.path.exists(output_folder):
        print(f"Model ID: {model_id}, Number of output files: 0 (output folder does not exist)\n")
        continue

    files = sorted([f for f in os.listdir(output_folder) if f.startswith(run_name + "_") and f.endswith(".csv")])
    num_files = len(files)
    print(f"Model ID: {model_id}, Number of output files: {num_files}")

    output_numbers = set()
    for f in files:
        num_str = f.replace(run_name + "_", "").replace(".csv", "")
        output_numbers.add(int(num_str))

    missing_numbers = sorted(input_numbers - output_numbers)
    print(f"Model ID: {model_id}")
    print(f"  Total output files: {len(files)}")
    print(f"  Missing files: {len(missing_numbers)}")
    if missing_numbers:
        print(f"  Missing batch numbers: {', '.join(f'{n:03d}' for n in missing_numbers)}")
    else:
        print(f"  All files present!")
    print()

    malformed_numbers = []
    for file in tqdm(files):
        batch_num = int(file.replace(run_name + "_", "").replace(".csv", ""))
        df = pd.read_csv(os.path.join(output_folder, file))

        malformed = False
        if list(df.columns[:2]) != ["key", "input"]:
            print(f"  File: {file}, missing key/input columns (found: {list(df.columns[:2])})")
            malformed = True
        if batch_num in expected_rows and len(df) != expected_rows[batch_num]:
            print(f"  File: {file}, row count mismatch: expected {expected_rows[batch_num]}, got {len(df)}")
            malformed = True
        if malformed:
            malformed_numbers.append(batch_num)

        nan_count = df.isna().sum().sum()
        if nan_count > 0:
            print(f"  File: {file}, NaNs: {nan_count}")

    print(f"  Malformed files (bad header / row count): {len(malformed_numbers)}")
    if malformed_numbers:
        print(f"  Malformed batch numbers: {', '.join(f'{n:03d}' for n in sorted(malformed_numbers))}")

    rerun_numbers = sorted(set(missing_numbers) | set(malformed_numbers))
    if rerun_numbers:
        print(f"  Batches needing rerun: {', '.join(f'{n:03d}' for n in rerun_numbers)}")
    print()