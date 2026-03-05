# Ersilia Reference Library Precalculations

Use the following pipeline to generate precalculations for the Ersilia Reference Library, which is stored in ready-to-use format in the `/inputs` directory.

## 00_prepare_inputs
Prepare the input library in batches of 10000 SMILES and create the output folders.

## 01_precalculations_dockerhub
This script will run the Ersilia calculations for all the models specified in the default list under `src/default.py`. The script assumes models are fetched previously. For safety, manually fetch `--from_dockerhub` the model list with the specified version required.

If you want to run them in the background, we recommend using nohup: `nohup python 01_precalculations_dockerhub.py 2>&1 &`

## 01b_precalculations_sif
For running models in an HPC cluster using SIF images, read the documentation in [ersilia-apptainer](https://github.com/ersilia-os/ersilia-apptainer) and make sure you have the apptainer package installed. Convert and collect the .sif images of the models in the `output/sif_images` folder and run the bash script passing as variables:
* Model ID ($1)
* Path to repository (path to the cloned ersilia-model-hub-maintained-inputs repository)

## 02_checks
This script does a quick check to ensure all the smiles were calculated (if a batch failed, the number is printed). It also counts the number of NaN values in each batch.

## 03_zip_precalculations
Optional: secure the calculations as a zip file under `output/stored_outputs`

## 04_upload_to_isaura
This step will upload the specified models to the isaura-public store. You can later remove them from your local Isaura stroe if you want. For large models (those producing > 100 outputs per molecule) there is an intermediate batching step to facilitate the upload. This step requires having [Isaura](https://github.com/ersilia-os/isaura) properly installed.