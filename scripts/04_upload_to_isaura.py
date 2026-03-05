import os
import pandas as pd
import sys
from pathlib import Path

from isaura.manage import (
  IsauraWriter,
  IsauraPush,

)

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))

from default import ERSILIA_MODEL_IDS

bucket = "isaura-public" 
acces = "public"

dest_dir = os.path.join(root, "..", "output", "ersilia_precalculations")
tmp_inputs = os.path.join(dest_dir, "batch_inputs")
tmp_outputs = os.path.join(dest_dir, "batch_outputs")

input_files = sorted([f for f in os.listdir(tmp_inputs) if f.startswith("smiles_") and f.endswith(".csv")])
input_numbers = set(int(f.replace("smiles_", "").replace(".csv", "")) for f in input_files)


for model_id, model_version in ERSILIA_MODEL_IDS.items():
    output_folder = os.path.join(tmp_outputs, model_id)
    files = sorted([f for f in os.listdir(output_folder) if f.startswith(model_id + "_") and f.endswith(".csv")])
    print(f"Model ID: {model_id}, Model Version: {model_version}, Number of output files: {len(files)}")
    check = pd.read_csv(os.path.join(output_folder, files[0]))
    print("Number of columns: ", len(check.columns))
    if len(check.columns) > 100:
      batched = []
      for file in files:
          in_path = os.path.join(output_folder, file)
          output_batch_folder = os.path.join(tmp_outputs, f"{model_id}_batched")
          os.makedirs(output_batch_folder, exist_ok=True)
          for part_idx, chunk in enumerate(pd.read_csv(in_path, chunksize=1000), start=1):
              out_name = f"{Path(file).stem}_part{part_idx:03d}.csv"
              out_path = os.path.join(output_batch_folder, out_name)
              chunk.to_csv(out_path, index=False)
              batched.append(out_name)
      for file in batched:
          (f'Uploading file {file} for model {model_id} to Isaura Local...')
          with IsauraWriter(
          input_csv=os.path.join(output_batch_folder, file),
          model_id=model_id,
          model_version=model_version,
          bucket=bucket,     
          access=acces,            
          ) as w:   
              w.write()
      print("batches uploaded, removing the batched files")
      os.remove(output_batch_folder)
    else:
      for file in files:
          (f'Uploading file {file} for model {model_id} to Isaura Local...')
          with IsauraWriter(
          input_csv=os.path.join(output_folder, file),
          model_id=model_id,
          model_version=model_version,
          bucket=bucket,     
          access=acces,            
          ) as w:
              w.write()

    print(f"Uploading files to Isaura Cloud for model {model_id}...")
    IsauraPush(model_id=model_id, model_version=model_version, bucket="isaura-public").push()
