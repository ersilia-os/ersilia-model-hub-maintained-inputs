import os
import pandas as pd
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

for model_id in ERSILIA_MODEL_IDS:
    files = sorted([f for f in os.listdir(tmp_outputs) if f.startswith(model_id + "_") and f.endswith(".csv")])
    num_files = len(files)
    print(f"Model ID: {model_id}, Number of output files: {num_files}")

    output_numbers = set()
    for f in files:
        num_str = f.replace(model_id + "_", "").replace(".csv", "")
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
    for file in files:
        df = pd.read_csv(os.path.join(tmp_outputs, file))
        nan_count = df.isna().sum().sum()
        print(f"  File: {file}, NaNs: {nan_count}")