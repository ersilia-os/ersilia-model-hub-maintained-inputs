import pandas as pd
import os

split_size = 10000
DATA = pd.read_csv("../data/chembl_reference_set_filtered.csv.tar.gz")
DATA["split"] = (DATA.index // split_size).astype(str).str.zfill(3)

splits = sorted(set(DATA['split']))
os.makedirs(os.path.join(".", "..", "data", "splits"), exist_ok=True)

# For each split
for split in splits:
    df = pd.DataFrame()
    df['smiles'] = DATA[DATA['split'] == split]['smiles'].tolist()
    df.to_csv(os.path.join(".", "..", "data", "splits", f"ErsiliaREF_{split}.csv"), index=False)
