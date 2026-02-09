import os
import pandas as pd
import sys


from isaura.manage import (
  IsauraWriter,
  IsauraCopy,
  IsauraPush,

)

from default import ERSILIA_MODEL_IDS


bucket = "ersilia-precalculations" 
acces = "public"

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))



dest_dir = os.path.join(root, "..", "output", "ersilia_precalculations")
tmp_inputs = os.path.join(dest_dir, "batch_inputs")
tmp_outputs = os.path.join(dest_dir, "batch_outputs")

input_files = sorted([f for f in os.listdir(tmp_inputs) if f.startswith("smiles_") and f.endswith(".csv")])
input_numbers = set(int(f.replace("smiles_", "").replace(".csv", "")) for f in input_files)

versions_path = os.path.join(root, "..", "data", "models_versions.csv")
versions_df = pd.read_csv(versions_path)
versions_df["major_version"] = versions_df["Release"].fillna("").astype(str).str.extract(r"^(v\d+)")
model_versions = dict(zip(versions_df["Identifier"], versions_df["major_version"]))


for model_id in ERSILIA_MODEL_IDS:
    model_version = model_versions.get(model_id) or "v1"
    files = sorted([f for f in os.listdir(tmp_outputs) if f.startswith(model_id + "_") and f.endswith(".csv")])
    print(f"Model ID: {model_id}, Model Version: {model_version}, Number of output files: {len(files)}")
    for file in files:
        print(os.path.join(tmp_outputs, file))
        (f'Uploading file {file} for model {model_id} to Isaura Local...')
        with IsauraWriter(
        input_csv=os.path.join(tmp_outputs, file),
        model_id=model_id,
        model_version=model_version,
        bucket=bucket,     
        access=acces,            

        ) as w:
            
            w.write()

    print(f"Uploading files to Isaura Cloud for model {model_id}...")
    IsauraCopy(model_id=model_id, model_version=model_version, bucket=bucket).copy()
    IsauraPush(model_id=model_id, model_version=model_version, bucket="isaura-public").push()
