import os
import pandas as pd
import sys


root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))

from default import ERSILIA_MODEL_IDS


model_ids = [model_id for model_id, _ in ERSILIA_MODEL_IDS]
for model_id in model_ids:
    files = [f for f in os.listdir(tmp_outputs) if f.startswith(model_id + "_") and f.endswith(".csv")]
    num_files = len(files)
    print(f"Model ID: {model_id}, Number of output files: {num_files}")
    for file in files:
        df = pd.read_csv(os.path.join(tmp_outputs, file))
        nan_count = df.isna().sum().sum()
        print(f"  File: {file}, NaNs: {nan_count}")