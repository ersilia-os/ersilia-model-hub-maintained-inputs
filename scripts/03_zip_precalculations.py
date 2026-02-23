import os
import sys
import zipfile

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))

from default import ERSILIA_MODEL_IDS

dest_dir = os.path.join(root, "..", "output", "ersilia_precalculations")
tmp_outputs = os.path.join(dest_dir, "batch_outputs")

zip_dir = os.path.join(root, "..", "stored_outputs")
os.makedirs(zip_dir, exist_ok=True)


for model_id in ERSILIA_MODEL_IDS:
    files = sorted(
        f for f in os.listdir(tmp_outputs)
        if f.startswith(model_id + "_") and f.endswith(".csv")
    )
    num_files = len(files)
    print(f"Model ID: {model_id}, Number of output files: {num_files}")

    if not files:
        print(f"⚠️ No files found for model {model_id}")
        continue

    zip_path = os.path.join(zip_dir, f"{model_id}.zip")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            full_path = os.path.join(tmp_outputs, f)
            zf.write(full_path, arcname=f)

    print(f"✅ Created {zip_path} ({len(files)} files)")