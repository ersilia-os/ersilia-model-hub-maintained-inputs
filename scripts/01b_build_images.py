import subprocess
import sys
import os

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, "..", "src"))

from default import ERSILIA_MODEL_IDS

for model in ERSILIA_MODEL_IDS:

    dest_dir = os.path.join(root, "..", "output", "apptainer", model)
    os.makedirs(dest_dir, exist_ok=True)

    def_path = os.path.join(dest_dir, f"{model}.def")
    sif_path = os.path.join(dest_dir, f"{model}.sif")

    open(def_path, "w").write(f"""Bootstrap: docker
From: ersiliaos/{model}:latest

%post
    mkdir -p /opt/ersilia
    mv /root/bundles /opt/ersilia/bundles
    mv /root/model /opt/ersilia/model
    chmod -R 755 /opt/ersilia
    export ERSILIA_PATH=/opt/ersilia

%environment
    export ERSILIA_PATH=/opt/ersilia
""")
    
    subprocess.run(["singularity", "build", sif_path, def_path], check=True)
    subprocess.run(["apptainer", "cache", "clean", "-f"])