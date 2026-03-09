#!/bin/bash
set -euo pipefail
MODEL="$1"
BASE="/aloy/home/acomajuncosa/Ersilia/ersilia-model-hub-maintained-inputs"

LOGDIR="$BASE/logs/$MODEL"
INPDIR="$BASE/output/ersilia_precalculations/batch_inputs"
RESDIR="$BASE/output/ersilia_precalculations/batch_outputs/${MODEL}"
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
#SBATCH --array=0-135%1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --output=$LOGDIR/%x_%a.out
#SBATCH --partition=spot_cpu
#SBATCH --nodelist=irbccn16,irbccn41,irbccn42
#SBATCH --requeue

export SINGULARITYENV_LD_LIBRARY_PATH=\$LD_LIBRARY_PATH
export SINGULARITY_BINDPATH="/home/sbnb:/aloy/home,/data/sbnb/data:/aloy/data,/data/sbnb/scratch:/aloy/scratch"
export LD_LIBRARY_PATH=/apps/manual/software/CUDA/11.6.1/lib64:/apps/manual/software/CUDA/11.6.1/targets/x86_64-linux/lib:/apps/manual/software/CUDA/11.6.1/extras/CUPTI/lib64/:/apps/manual/software/CUDA/11.6.1/nvvm/lib64/:\$LD_LIBRARY_PATH

# set -euo pipefail
cd $RESDIR

alpha="\$SLURM_ARRAY_TASK_ID"
alpha_padded="\$(printf "%03d" "\$alpha")"

/aloy/home/acomajuncosa/Ersilia/envs/ersilia_apptainer/bin/ersilia_apptainer \
  --sif "${APPDIR}/${MODEL}.sif" \
  --input "${INPDIR}/smiles_\${alpha_padded}.csv" \
  --output "${RESDIR}/${MODEL}_\${alpha_padded}.csv" \
  --verbose

EOF

sbatch "$tmp"
rm -f "$tmp"