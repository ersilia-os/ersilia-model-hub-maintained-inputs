import os
import pandas as pd
from tqdm import tqdm
import subprocess
import sys

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))

from default import ERSILIA_MODEL_IDS


dest_dir = os.path.join(root, "..", "output", "ersilia_precalculations")
tmp_inputs = os.path.join(dest_dir, "batch_inputs")
tmp_outputs = os.path.join(dest_dir, "batch_outputs")


file_names = []
for fn in os.listdir(tmp_inputs):
    if fn.startswith("smiles_") and fn.endswith(".csv"):
        file_names.append(fn)
file_names = sorted(file_names)

batch_ids = []

for fn in tqdm(file_names):
    if fn.startswith("smiles_") and fn.endswith(".csv"):
        batch_id = fn.split("_")[1].split(".")[0]
        batch_ids += [int(batch_id)]
        for model_id in ERSILIA_MODEL_IDS.keys():
            output_folder = os.path.join(tmp_outputs, model_id)
            if not os.path.exists(output_folder):
                os.mkdir(output_folder)
            output_file = os.path.join(output_folder, "{0}_{1}.csv".format(model_id, batch_id))
            if os.path.exists(output_file):
                print("Skipping existing file:", output_file)
                continue
            chunk_input_file = os.path.join(tmp_inputs, fn)
            cmd = "ersilia serve {0}; ersilia -v run -i {1} -o {2} --batch_size 1000; ersilia close".format(model_id, chunk_input_file, output_file)
            subprocess.run(cmd, shell=True, check=True)
