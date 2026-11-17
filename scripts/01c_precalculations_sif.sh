#!/bin/bash
set -euo pipefail
MODEL="$1"
ARRAY_SPEC="${2:-0-135}"
MAX_RUNNING="${3:-50}"   # array tasks of this job allowed to run at once
MEM="${4:-16G}"          # memory per array task
BASE="/aloy/home/acomajuncosa/Ersilia/ersilia-model-hub-maintained-inputs"

# Model version comes from src/default.py, so the image name matches 01b: <model>_<version>.sif
VERSION="$(python3 -c "
import sys
sys.path.insert(0, '$BASE/src')
from default import ERSILIA_MODEL_IDS
print(ERSILIA_MODEL_IDS['$MODEL'])
")" || { echo "Model '$MODEL' not found in src/default.py" >&2; exit 1; }

LOGDIR="$BASE/logs/${MODEL}_${VERSION}"
INPDIR="$BASE/output/ersilia_precalculations/batch_inputs"
RESDIR="$BASE/output/ersilia_precalculations/batch_outputs/${MODEL}_${VERSION}"
APPDIR="$BASE/output/apptainer/${MODEL}"

mkdir -p "$LOGDIR"
mkdir -p "$RESDIR"
mkdir -p "$BASE/tmp"

tmp="$(mktemp "$BASE/tmp/${MODEL}.sbatch.XXXXXX.sh")"


cat > "$tmp" <<EOF
#!/bin/bash
#SBATCH --job-name=$MODEL
#SBATCH --chdir=$BASE
#SBATCH --time=700:00:00
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --array=${ARRAY_SPEC}%${MAX_RUNNING}
#SBATCH --cpus-per-task=1
#SBATCH --mem=${MEM}
#SBATCH --output=$LOGDIR/%x_%a.out
#SBATCH --partition=spot_cpu
#SBATCH --nodelist=irbccn16,irbccn41,irbccn42
#SBATCH --requeue

export SINGULARITYENV_LD_LIBRARY_PATH=\$LD_LIBRARY_PATH
export SINGULARITY_BINDPATH="/home/sbnb:/aloy/home,/data/sbnb/data:/aloy/data,/data/sbnb/scratch:/aloy/scratch"
export LD_LIBRARY_PATH=/apps/manual/software/CUDA/11.6.1/lib64:/apps/manual/software/CUDA/11.6.1/targets/x86_64-linux/lib:/apps/manual/software/CUDA/11.6.1/extras/CUPTI/lib64/:/apps/manual/software/CUDA/11.6.1/nvvm/lib64/:\$LD_LIBRARY_PATH

# set -euo pipefail

alpha="\$SLURM_ARRAY_TASK_ID"
alpha_padded="\$(printf "%03d" "\$alpha")"

# Outputs are versioned: batch_outputs/<model>_<version>/<model>_<version>_<NNN>.csv.
# ersilia_apptainer writes its working files (.<model>_<version>_<NNN>.stdout.log / .stderr.log /
# .raw.csv / .csv.tmp) next to the output CSV. Point --output at $LOGDIR, next to the
# Slurm logs, so $RESDIR only ever holds finished CSVs: the CSV is moved there once the
# run succeeded. A failed task keeps its hidden logs in $LOGDIR for debugging.
work_csv="${LOGDIR}/${MODEL}_${VERSION}_\${alpha_padded}.csv"
final_csv="${RESDIR}/${MODEL}_${VERSION}_\${alpha_padded}.csv"
rm -f "\$work_csv"
cd "$LOGDIR"

# The tool's stdout/stderr go to those hidden files, not to Slurm. Follow them while the
# model runs so they also end up in the Slurm log.
log_stem="${LOGDIR}/.${MODEL}_${VERSION}_\${alpha_padded}"
tail -n 0 -F "\${log_stem}.stdout.log" "\${log_stem}.stderr.log" 2>/dev/null &
tail_pid=\$!

/aloy/home/acomajuncosa/Ersilia/envs/ersilia_apptainer/bin/ersilia_apptainer run \
  --sif "${APPDIR}/${MODEL}_${VERSION}.sif" \
  --input "${INPDIR}/smiles_\${alpha_padded}.csv" \
  --output "\$work_csv" \
  --verbose
rc=\$?

# let tail flush what the model wrote last, then stop it
sleep 2
kill "\$tail_pid" 2>/dev/null

# publish the finished CSV (a rename within the same filesystem, so never half-written)
if [ "\$rc" -eq 0 ] && [ -s "\$work_csv" ]; then
  mv -f "\$work_csv" "\$final_csv" || rc=1
elif [ "\$rc" -eq 0 ]; then
  echo "ersilia_apptainer exited 0 but \$work_csv is missing or empty" >&2
  rc=1
fi
exit "\$rc"

EOF

sbatch "$tmp"
rm -f "$tmp"