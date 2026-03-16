"""
Build reference library from ChEMBL and other chemical libraries.

Pipeline (mirrors notebooks 01, 02, 03 in order):
  1.  Deduplicate ChEMBL SDF by InChIKey
  2.  Filter ChEMBL by physicochemical properties
  3.  Cluster ChEMBL with BitBirch (threshold=0.5), pick representatives
  4.  Load other libraries (ChEBI, Antibacterial, Drug Repurposing Hub, DrugBank)
  5.  Standardize and assign InChIKeys to all libraries
  6.  Add molecules not already in ChEMBL representatives → master_dataset_smiles.csv
  7.  Deduplicate master dataset by InChIKey
  8.  Filter master dataset by same physicochemical thresholds
  9.  Filter by allowed atoms
  10. Cluster master dataset with BitBirch (threshold=0.7)
  11. Select one representative per cluster (DrugBank > Drug Repurposing Hub >
      Antibacterial > ChEBI > ChEMBL) → reference_set.csv
"""

import argparse
import csv
import gc
import os

import bblean
import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, PandasTools, rdMolDescriptors
from rdkit.Chem.inchi import MolToInchiKey
from rdkit.Chem.MolStandardize import rdMolStandardize
from tqdm import tqdm

RDLogger.DisableLog("rdApp.*")

# ---------------------------------------------------------------------------
# Physicochemical filter thresholds (shared by ChEMBL and master dataset)
# ---------------------------------------------------------------------------
MIN_MW, MAX_MW = 200, 700
MIN_HA, MAX_HA = 5, 60
MIN_RINGS, MAX_RINGS = 0, 6
MIN_LOGP, MAX_LOGP = -2, 7
MAX_HBD = 7
MAX_HBA = 12
MAX_RB = 20

# Atoms allowed in the final library
ALLOWED_ATOMS = {"C", "H", "N", "O", "S", "P", "F", "Cl", "Br", "I"}

# ---------------------------------------------------------------------------
# RDKit standardization helpers (initialized once)
# ---------------------------------------------------------------------------
_lfc = rdMolStandardize.LargestFragmentChooser()
_normalizer = rdMolStandardize.Normalizer()
_uncharger = rdMolStandardize.Uncharger()


def standardize_and_get_inchikey(mol, strip_stereo=True):
    """
    Standardize a molecule and return (mol_clean, inchikey, canonical_smiles).
    Returns (None, None, None) on failure.
    """
    if mol is None:
        return None, None, None
    try:
        mol = _lfc.choose(mol)
        mol = rdMolStandardize.Cleanup(mol)
        mol = _normalizer.normalize(mol)
        mol = _uncharger.uncharge(mol)
        Chem.SanitizeMol(mol)
        if strip_stereo:
            Chem.RemoveStereochemistry(mol)
        ik = MolToInchiKey(mol)
        smiles = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=not strip_stereo)
        mol_clean = Chem.MolFromSmiles(smiles)
        if mol_clean is None:
            return None, None, None
        Chem.SanitizeMol(mol_clean)
        return mol_clean, ik, smiles
    except Exception:
        return None, None, None


def standardize_smiles(smiles_str, strip_stereo=True):
    """
    Standardize a SMILES string and return (inchikey, canonical_smiles).
    Returns (None, None) on failure.
    """
    if not isinstance(smiles_str, str) or not smiles_str.strip():
        return None, None
    try:
        mol = Chem.MolFromSmiles(smiles_str)
        if mol is None:
            return None, None
        mol = _lfc.choose(mol)
        mol = rdMolStandardize.Cleanup(mol)
        mol = _normalizer.normalize(mol)
        mol = _uncharger.uncharge(mol)
        Chem.SanitizeMol(mol)
        if strip_stereo:
            Chem.RemoveStereochemistry(mol)
        ik = MolToInchiKey(mol)
        can_smi = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=not strip_stereo)
        return ik, can_smi
    except Exception:
        return None, None


def process_df_chemistry(df, smiles_col, inchikey_col, strip_stereo=True):
    """Standardize a SMILES column in a DataFrame, adding inchikey_col and Canonical_SMILES."""
    print(f"  Standardizing '{smiles_col}' ({len(df)} rows)...")
    results = [standardize_smiles(s, strip_stereo) for s in tqdm(df[smiles_col], leave=False)]
    df[inchikey_col] = [r[0] for r in results]
    df["Canonical_SMILES"] = [r[1] for r in results]
    print(f"  Valid: {df[inchikey_col].notna().sum()}/{len(df)}")
    return df


# ---------------------------------------------------------------------------
# Property filtering helpers
# ---------------------------------------------------------------------------

def passes_property_filters(mol):
    """Return True if the molecule passes all physicochemical thresholds."""
    mw = Descriptors.MolWt(mol)
    if not (MIN_MW <= mw <= MAX_MW):
        return False
    ha = mol.GetNumHeavyAtoms()
    if not (MIN_HA <= ha <= MAX_HA):
        return False
    rings = rdMolDescriptors.CalcNumRings(mol)
    if not (MIN_RINGS <= rings <= MAX_RINGS):
        return False
    logp = Crippen.MolLogP(mol)
    if not (MIN_LOGP <= logp <= MAX_LOGP):
        return False
    if rdMolDescriptors.CalcNumHBD(mol) > MAX_HBD:
        return False
    if rdMolDescriptors.CalcNumHBA(mol) > MAX_HBA:
        return False
    if rdMolDescriptors.CalcNumRotatableBonds(mol) > MAX_RB:
        return False
    return True


def filter_sdf_by_properties(sdf_in, sdf_out, csv_out):
    """Read an SDF, apply property filters, write passing molecules to SDF + CSV."""
    supplier = Chem.SDMolSupplier(sdf_in, sanitize=True, removeHs=True)
    writer = Chem.SDWriter(sdf_out)
    total = invalid = filtered_out = kept = 0

    with open(csv_out, "w", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(["SMILES", "MW", "HeavyAtomCount", "RingCount", "LogP", "HBD", "HBA", "RotatableBonds"])

        for mol in tqdm(supplier, desc=f"  Filtering {os.path.basename(sdf_in)}"):
            total += 1
            if mol is None:
                invalid += 1
                continue
            try:
                smi = Chem.MolToSmiles(mol, canonical=True)
                mw = Descriptors.MolWt(mol)
                ha = mol.GetNumHeavyAtoms()
                rings = rdMolDescriptors.CalcNumRings(mol)
                logp = Crippen.MolLogP(mol)
                hbd = rdMolDescriptors.CalcNumHBD(mol)
                hba = rdMolDescriptors.CalcNumHBA(mol)
                rb = rdMolDescriptors.CalcNumRotatableBonds(mol)
            except Exception:
                invalid += 1
                continue

            if not passes_property_filters(mol):
                filtered_out += 1
                continue

            writer.write(mol)
            cw.writerow([smi, mw, ha, rings, logp, hbd, hba, rb])
            kept += 1

    writer.close()
    print(f"  Read: {total}  |  Invalid: {invalid}  |  Filtered out: {filtered_out}  |  Kept: {kept}")
    return kept


# ---------------------------------------------------------------------------
# Step 1 + 7 – Deduplication
# ---------------------------------------------------------------------------

def deduplicate_sdf(sdf_in, sdf_out):
    """Deduplicate an SDF by InChIKey (strips stereo). Returns count of unique mols."""
    supplier = Chem.SDMolSupplier(sdf_in, sanitize=False, removeHs=True)
    writer = Chem.SDWriter(sdf_out)
    seen = set()
    total = invalid = duplicates = written = 0

    for mol in tqdm(supplier, desc=f"  Deduplicating {os.path.basename(sdf_in)}"):
        total += 1
        mol_clean, ik, _ = standardize_and_get_inchikey(mol, strip_stereo=True)
        if mol_clean is None or ik is None:
            invalid += 1
            continue
        if ik in seen:
            duplicates += 1
            continue
        seen.add(ik)
        writer.write(mol_clean)
        written += 1

    writer.close()
    print(f"  Read: {total}  |  Invalid: {invalid}  |  Duplicates: {duplicates}  |  Unique: {written}")
    return written


def deduplicate_smiles_csv(csv_in, sdf_out):
    """Deduplicate a SMILES CSV by InChIKey. Returns count of unique mols."""
    supplier = Chem.SmilesMolSupplier(csv_in, delimiter=",", titleLine=True)
    writer = Chem.SDWriter(sdf_out)
    seen = set()
    total = invalid = duplicates = written = 0

    for mol in tqdm(supplier, desc=f"  Deduplicating {os.path.basename(csv_in)}"):
        total += 1
        mol_clean, ik, _ = standardize_and_get_inchikey(mol, strip_stereo=True)
        if mol_clean is None or ik is None:
            invalid += 1
            continue
        if ik in seen:
            duplicates += 1
            continue
        seen.add(ik)
        writer.write(mol_clean)
        written += 1

    writer.close()
    print(f"  Read: {total}  |  Invalid: {invalid}  |  Duplicates: {duplicates}  |  Unique: {written}")
    return written


# ---------------------------------------------------------------------------
# Step 3 + 10 – BitBirch clustering
# ---------------------------------------------------------------------------

def cluster_smiles(smiles_list, threshold, branching=128, nbits=2048):
    """Run BitBirch clustering on a list of SMILES. Returns cluster label array."""
    print(f"  Computing ECFP4 fingerprints for {len(smiles_list)} molecules...")
    fps = bblean.fps_from_smiles(smiles_list, kind="ecfp4", pack=True, n_features=nbits)
    bb = bblean.BitBirch(threshold=threshold, branching_factor=branching, merge_criterion="diameter")
    print(f"  Fitting BitBirch (threshold={threshold})...")
    bb.fit(fps)
    clusters = bb.get_cluster_mol_ids()
    labels = np.zeros(len(fps), dtype=np.int32)
    for cid, members in enumerate(clusters):
        for idx in members:
            labels[idx] = cid
    print(f"  Clusters: {len(clusters)}")
    return labels


# ---------------------------------------------------------------------------
# Step 9 – Allowed-atom filter
# ---------------------------------------------------------------------------

def filter_allowed_atoms(csv_in, csv_out, smiles_col="SMILES"):
    """Keep only molecules composed entirely of ALLOWED_ATOMS."""
    df = pd.read_csv(csv_in)
    smiles_list = df[smiles_col].astype(str).tolist()

    kept = []
    for smi in tqdm(smiles_list, desc="  Atom filter"):
        if "." in smi or "*" in smi:
            continue
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        if all(atom.GetSymbol() in ALLOWED_ATOMS for atom in mol.GetAtoms()):
            kept.append(smi)

    pd.DataFrame({smiles_col: kept}).to_csv(csv_out, index=False)
    print(f"  Kept {len(kept)}/{len(smiles_list)} molecules")
    return kept


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Build reference library from ChEMBL and other sources.")
    p.add_argument("--chembl_sdf",           required=True,  help="Path to chembl_36.sdf")
    p.add_argument("--chebi_sdf",            required=True,  help="Path to chebi.sdf")
    p.add_argument("--antibacterial_sdf",    required=True,  help="Path to Antibacterial SDF")
    p.add_argument("--drug_repurposing_csv", required=True,  help="Path to drug_repurposing_hub.csv")
    p.add_argument("--drugbank_csv",         required=True,  help="Path to drugbank_smiles.csv")
    p.add_argument("--outdir",               default=".",    help="Output directory (default: current dir)")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    def out(name):
        return os.path.join(args.outdir, name)

    # -----------------------------------------------------------------------
    # NOTEBOOK 01 – ChEMBL processing
    # -----------------------------------------------------------------------
    print("\n=== Step 1: Deduplicate ChEMBL ===")
    deduplicate_sdf(args.chembl_sdf, out("chembl_dedup.sdf"))

    print("\n=== Step 2: Filter ChEMBL by properties ===")
    filter_sdf_by_properties(
        out("chembl_dedup.sdf"),
        out("chembl_filtered.sdf"),
        out("chembl_filtered_props.csv"),
    )

    print("\n=== Step 3: Cluster ChEMBL (threshold=0.5) ===")
    supplier = Chem.SDMolSupplier(out("chembl_filtered.sdf"), sanitize=True, removeHs=True)
    chembl_smiles = [Chem.MolToSmiles(m) for m in supplier if m is not None]

    labels = cluster_smiles(chembl_smiles, threshold=0.5)

    # One representative per cluster (first occurrence)
    seen_clusters = {}
    for idx, cid in enumerate(labels):
        if cid not in seen_clusters:
            seen_clusters[cid] = idx
    rep_indices = list(seen_clusters.values())
    rep_smiles = [chembl_smiles[i] for i in rep_indices]

    pd.DataFrame({"SMILES": chembl_smiles, "cluster": labels}).to_csv(
        out("chembl_clusters.csv"), index=False
    )
    pd.DataFrame({"SMILES": rep_smiles}).to_csv(
        out("chembl_representatives.csv"), index=False
    )
    print(f"  ChEMBL representatives: {len(rep_smiles)}")

    # -----------------------------------------------------------------------
    # NOTEBOOK 02 – Add other libraries
    # -----------------------------------------------------------------------
    print("\n=== Step 4: Load and standardize all libraries ===")

    chembl_rep = pd.read_csv(out("chembl_representatives.csv"))
    chembl_rep = process_df_chemistry(chembl_rep, "SMILES", "INCHIKEY")
    chembl_rep["Original_Library"] = "Filtered ChEMBL"

    chebi = PandasTools.LoadSDF(args.chebi_sdf)
    chebi = process_df_chemistry(chebi, "SMILES", "INCHIKEY")

    antibacterial = PandasTools.LoadSDF(args.antibacterial_sdf)
    antibacterial = process_df_chemistry(antibacterial, "Smile", "INCHIKEY")

    drug_repurposing = pd.read_csv(args.drug_repurposing_csv)
    drug_repurposing = process_df_chemistry(drug_repurposing, "smiles", "INCHIKEY")

    drugbank = pd.read_csv(args.drugbank_csv)
    drugbank = process_df_chemistry(drugbank, "Smiles", "INCHIKEY")

    print("\n=== Step 5: Identify molecules novel to ChEMBL ===")
    chembl_inchikeys = set(chembl_rep["INCHIKEY"].dropna().str.strip())

    other_libraries = {
        "ChEBI": chebi,
        "Antibacterial": antibacterial,
        "Drug Repurposing Hub": drug_repurposing,
        "DrugBank SMILES": drugbank,
    }

    novel_parts = []
    for name, df in other_libraries.items():
        df["INCHIKEY"] = df["INCHIKEY"].astype(str).str.strip()
        novel_df = df[~df["INCHIKEY"].isin(chembl_inchikeys)].copy()
        novel_df["Original_Library"] = name
        novel_parts.append(novel_df[["INCHIKEY", "Canonical_SMILES", "Original_Library"]])
        print(f"  {name}: {len(novel_df)} novel molecules")

    novel = pd.concat(novel_parts, ignore_index=True)
    novel = novel.drop_duplicates(subset=["INCHIKEY"], keep="first")

    print("\n=== Step 6: Build master dataset ===")
    chembl_subset = chembl_rep[["INCHIKEY", "Canonical_SMILES", "Original_Library"]].copy()

    master = pd.concat([chembl_subset, novel], ignore_index=True)
    master = master.rename(columns={"Canonical_SMILES": "SMILES"})
    master.dropna(subset=["SMILES"], inplace=True)

    master[["SMILES"]].to_csv(out("master_dataset_smiles.csv"), index=False)
    print(f"  Master dataset: {len(master)} molecules → master_dataset_smiles.csv")

    # Free memory from large library DataFrames
    del chebi, antibacterial, drug_repurposing, drugbank, novel, novel_parts
    gc.collect()

    # -----------------------------------------------------------------------
    # NOTEBOOK 03 – Merged dataset filtering
    # -----------------------------------------------------------------------
    print("\n=== Step 7: Deduplicate master dataset ===")
    deduplicate_smiles_csv(out("master_dataset_smiles.csv"), out("master_dataset_dedup.sdf"))

    print("\n=== Step 8: Filter master dataset by properties ===")
    filter_sdf_by_properties(
        out("master_dataset_dedup.sdf"),
        out("master_dataset_filtered.sdf"),
        out("master_dataset_filtered_props.csv"),
    )

    # Convert filtered SDF to SMILES CSV
    supplier = Chem.SDMolSupplier(out("master_dataset_filtered.sdf"), sanitize=True, removeHs=True)
    filtered_smiles = [Chem.MolToSmiles(m) for m in supplier if m is not None]
    pd.DataFrame({"SMILES": filtered_smiles}).to_csv(out("master_dataset_smiles_filtered.csv"), index=False)
    print(f"  Filtered SMILES: {len(filtered_smiles)}")

    print("\n=== Step 9: Filter by allowed atoms ===")
    kept_smiles = filter_allowed_atoms(
        out("master_dataset_smiles_filtered.csv"),
        out("master_dataset_smiles_filtered_2.csv"),
    )

    print("\n=== Step 10: Cluster master dataset (threshold=0.7) ===")
    labels = cluster_smiles(kept_smiles, threshold=0.7)

    df_clusters = pd.DataFrame({"SMILES": kept_smiles, "cluster": labels})
    df_clusters = process_df_chemistry(df_clusters, "SMILES", "INCHIKEY-Canonical")
    df_clusters.to_csv(out("reference_set_clusters.csv"), index=False)

    print("\n=== Step 11: Select representatives by library priority ===")
    # Reload libraries (lightweight — only INCHIKEY columns needed)
    def load_inchikeys(path, smiles_col, inchikey_col_name):
        df = pd.read_csv(path) if path.endswith(".csv") else PandasTools.LoadSDF(path)
        df = process_df_chemistry(df, smiles_col, "IK_tmp")
        return set(df["IK_tmp"].dropna())

    db_keys = set(pd.read_csv(args.drugbank_csv)
                  .pipe(lambda df: process_df_chemistry(df, "Smiles", "IK"))["IK"].dropna())
    dr_keys = set(pd.read_csv(args.drug_repurposing_csv)
                  .pipe(lambda df: process_df_chemistry(df, "smiles", "IK"))["IK"].dropna())
    ab_df = PandasTools.LoadSDF(args.antibacterial_sdf)
    ab_keys = set(process_df_chemistry(ab_df, "Smile", "IK")["IK"].dropna())
    cb_df = PandasTools.LoadSDF(args.chebi_sdf)
    cb_keys = set(process_df_chemistry(cb_df, "SMILES", "IK")["IK"].dropna())

    def assign_priority(ik):
        if ik in db_keys:
            return 1  # DrugBank
        if ik in dr_keys:
            return 2  # Drug Repurposing Hub
        if ik in ab_keys:
            return 3  # Antibacterial
        if ik in cb_keys:
            return 4  # ChEBI
        return 5      # ChEMBL

    df_clusters["priority"] = df_clusters["INCHIKEY-Canonical"].apply(assign_priority)

    representatives = (
        df_clusters
        .sort_values(["cluster", "priority"])
        .drop_duplicates(subset=["cluster"], keep="first")
        .drop_duplicates(subset=["INCHIKEY-Canonical"], keep="first")
    )

    representatives.to_csv(out("cluster_representatives_final.csv"), index=False)

    df_rep = representatives[["SMILES"]].copy()
    df_rep.to_csv(out("reference_set.csv"), index=False)

    print(f"\n=== Done ===")
    print(f"  Representatives: {len(representatives)} from {df_clusters['cluster'].nunique()} clusters")
    print(f"  Final output: {out('reference_set.csv')}")


if __name__ == "__main__":
    main()
