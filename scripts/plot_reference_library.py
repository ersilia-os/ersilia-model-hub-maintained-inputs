"""
Summary plots of the reference library.

Run with:
    conda run -n ersilia python scripts/plot_reference_library.py

Outputs (output/plots/):
    01_source_distribution.png   — compound count per source library
    02_mw_distribution.png       — MW histogram overlaid per source
    03_property_distributions.png — 3×2 panel of all property distributions
    04_property_by_source.png    — violin plots of MW and LogP by source
    properties_cache.parquet     — cached computed molecular properties
"""

import os
import multiprocessing as mp

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors

import stylia
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(ROOT, "inputs", "cluster_representatives_final.csv")
OUT_DIR = os.path.join(ROOT, "output", "plots")
CACHE_FILE = os.path.join(OUT_DIR, "properties_cache.parquet")

PRIORITY_MAP = {
    1: "DrugBank",
    2: "Drug Repurposing Hub",
    3: "Antibacterial",
    4: "ChEBI",
    5: "ChEMBL",
}

# Source display order (smallest → largest for bar chart)
SOURCE_ORDER = ["Drug Repurposing Hub", "DrugBank", "Antibacterial", "ChEBI", "ChEMBL"]

stylia.set_style("ersilia")
pal = stylia.CategoricalPalette("ersilia")
COLORS = dict(zip(SOURCE_ORDER, pal.get(len(SOURCE_ORDER))))

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Property computation
# ---------------------------------------------------------------------------

def _compute_row(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return (np.nan,) * 6
    return (
        Descriptors.MolWt(mol),
        Crippen.MolLogP(mol),
        rdMolDescriptors.CalcNumHBD(mol),
        rdMolDescriptors.CalcNumHBA(mol),
        rdMolDescriptors.CalcNumRotatableBonds(mol),
        rdMolDescriptors.CalcNumRings(mol),
    )


def compute_properties(df):
    print(f"Computing properties for {len(df):,} compounds using {mp.cpu_count()} cores...")
    with mp.Pool(mp.cpu_count()) as pool:
        results = pool.map(_compute_row, df["SMILES"].tolist())
    props = pd.DataFrame(
        results,
        columns=["MW", "LogP", "HBD", "HBA", "RotBonds", "Rings"],
        index=df.index,
    )
    return pd.concat([df, props], axis=1).dropna(subset=["MW"])


# ---------------------------------------------------------------------------
# Plot 1: Source distribution (horizontal bar chart)
# ---------------------------------------------------------------------------

def plot_source_distribution(df):
    counts = df.groupby("source").size().reindex(SOURCE_ORDER)

    fig, axs = stylia.create_figure(nrows=1, ncols=1, width=0.7, height=0.45)
    ax = axs.next()

    y_pos = np.arange(len(SOURCE_ORDER))
    bars = ax.barh(
        y_pos,
        counts.values,
        color=[COLORS[s] for s in SOURCE_ORDER],
        height=0.6,
    )

    # Count labels
    for bar, val in zip(bars, counts.values):
        ax.text(
            bar.get_width() * 1.02,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,}",
            va="center",
            ha="left",
            fontsize=stylia.FONTSIZE,
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(SOURCE_ORDER)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    stylia.label(ax, xlabel="Number of compounds (log scale)", title="Reference library: compounds by source")

    path = os.path.join(OUT_DIR, "01_source_distribution.png")
    stylia.save_figure(path)
    plt.close()
    print(f"Saved {path}")


# ---------------------------------------------------------------------------
# Plot 2: MW distribution per source
# ---------------------------------------------------------------------------

def plot_mw_distribution(df):
    fig, axs = stylia.create_figure(nrows=1, ncols=1, width=1.0, height=0.5)
    ax = axs.next()

    bins = np.linspace(200, 700, 51)
    for source in SOURCE_ORDER:
        sub = df.loc[df["source"] == source, "MW"]
        # Normalise to density so sources are comparable despite size differences
        ax.hist(
            sub.clip(200, 700),
            bins=bins,
            density=True,
            alpha=0.55,
            color=COLORS[source],
            label=f"{source} (n={len(sub):,})",
            linewidth=0,
        )

    ax.legend(fontsize=stylia.FONTSIZE_SMALL)
    stylia.label(ax, xlabel="Molecular weight (Da)", ylabel="Density", title="Molecular weight distribution by source")

    path = os.path.join(OUT_DIR, "02_mw_distribution.png")
    stylia.save_figure(path)
    plt.close()
    print(f"Saved {path}")


# ---------------------------------------------------------------------------
# Plot 3: Multi-panel property distributions (full library)
# ---------------------------------------------------------------------------

PROP_SPECS = [
    ("MW",       "Molecular weight (Da)",      50),
    ("LogP",     "LogP",                       40),
    ("HBD",      "H-bond donors",              None),
    ("HBA",      "H-bond acceptors",           None),
    ("RotBonds", "Rotatable bonds",            None),
    ("Rings",    "Number of rings",            None),
]


def plot_property_distributions(df):
    ec = stylia.ErsiliaColors()
    fill_color = ec.get("purple", alpha=0.7)
    edge_color = ec.plum

    fig, axs = stylia.create_figure(nrows=3, ncols=2, width=1.0, height=1.1)

    for i, (col, xlabel, n_bins) in enumerate(PROP_SPECS):
        ax = axs[i // 2, i % 2]
        data = df[col].dropna()

        if n_bins is None:
            # Integer-valued property — one bar per value
            vals = data.astype(int)
            counts = vals.value_counts().sort_index()
            ax.bar(counts.index, counts.values, color=fill_color, linewidth=0)
        else:
            ax.hist(data, bins=n_bins, color=fill_color, linewidth=0)

        stylia.label(ax, xlabel=xlabel, ylabel="Count")

    fig.suptitle("Property distributions — reference library", fontsize=stylia.FONTSIZE_BIG, y=1.01)

    path = os.path.join(OUT_DIR, "03_property_distributions.png")
    stylia.save_figure(path)
    plt.close()
    print(f"Saved {path}")


# ---------------------------------------------------------------------------
# Plot 4: Violin plots of MW and LogP by source
# ---------------------------------------------------------------------------

def plot_property_by_source(df):
    fig, axs = stylia.create_figure(nrows=1, ncols=2, width=1.0, height=0.55)

    for col_i, (prop, ylabel) in enumerate([("MW", "Molecular weight (Da)"), ("LogP", "LogP")]):
        ax = axs.next()

        data_by_source = [df.loc[df["source"] == s, prop].dropna().values for s in SOURCE_ORDER]

        parts = ax.violinplot(
            data_by_source,
            positions=range(len(SOURCE_ORDER)),
            showmedians=True,
            showextrema=False,
            widths=0.7,
        )

        for pc, source in zip(parts["bodies"], SOURCE_ORDER):
            pc.set_facecolor(COLORS[source])
            pc.set_alpha(0.75)
            pc.set_linewidth(0)

        parts["cmedians"].set_color(stylia.ErsiliaColors().plum)
        parts["cmedians"].set_linewidth(stylia.LINEWIDTH_THICK)

        ax.set_xticks(range(len(SOURCE_ORDER)))
        ax.set_xticklabels(SOURCE_ORDER, rotation=35, ha="right", fontsize=stylia.FONTSIZE_SMALL)
        stylia.label(ax, ylabel=ylabel)

    fig.suptitle("Property distributions by source", fontsize=stylia.FONTSIZE_BIG, y=1.01)

    path = os.path.join(OUT_DIR, "04_property_by_source.png")
    stylia.save_figure(path)
    plt.close()
    print(f"Saved {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading reference library...")
    df = pd.read_csv(INPUT_FILE)
    df["source"] = df["priority"].map(PRIORITY_MAP)
    print(f"  {len(df):,} compounds, {df['source'].nunique()} sources")

    if os.path.exists(CACHE_FILE):
        print(f"Loading cached properties from {CACHE_FILE}")
        props_df = pd.read_parquet(CACHE_FILE)
    else:
        props_df = compute_properties(df)
        props_df.to_parquet(CACHE_FILE, index=False)
        print(f"Cached properties to {CACHE_FILE}")

    print("\nGenerating plots...")
    plot_source_distribution(props_df)
    plot_mw_distribution(props_df)
    plot_property_distributions(props_df)
    plot_property_by_source(props_df)
    print("\nDone. Plots written to", OUT_DIR)


if __name__ == "__main__":
    main()
