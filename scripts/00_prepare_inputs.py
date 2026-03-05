import os
import pandas as pd
from tqdm import tqdm
import sys

root = os.path.dirname(os.path.abspath(__file__))

data_dir = os.path.join(root, "..", "inputs")
dest_dir = os.path.join(root, "..", "output", "ersilia_precalculations")

if not os.path.exists(dest_dir):
    os.makedirs(dest_dir)

input_file = os.path.join(data_dir, "reference_library_smiles.csv")

tmp_inputs = os.path.join(dest_dir, "batch_inputs")
if not os.path.exists(tmp_inputs):
    os.mkdir(tmp_inputs)
    
tmp_outputs = os.path.join(dest_dir, "batch_outputs")
if not os.path.exists(tmp_outputs):
    os.mkdir(tmp_outputs)


chunksize = 10000

for i, chunk in tqdm(enumerate(pd.read_csv(input_file, chunksize=chunksize))):
    chunk_file = os.path.join(tmp_inputs, "smiles_{0}.csv".format(str(i).zfill(3)))
    chunk.to_csv(chunk_file, index=False)
