# Ersilia Reference Library Precalculations

Use the following pipeline to generate precalculations for the Ersilia Reference Library:

_First make sure the right input file (`reference_library_smiles.csv`) is availabe in your `/data` folder_

## 01. Fetch models
Check the [list]() of models to run precalculations for and take the highest priority models that are not yet assigned to anyone. Make sure to update the list so that we don't repeat efforts.
Fetch the models one by one through the Ersilia CLI, using the `--from_dockerhub` option and specifying the version in the Excel file, not latest.

## 02. Update the default.py
Update the model list in default.py with the right EOS IDs (do not commit changes in this file to avoid git conflicts)

## 03. Run the precalculations script
`nohup python 00_precalculations.py 2>&1 &`

## 04. Check results
Before considering a model finished, check the calculations went well. A first iteration to be improved can be run from `01_checks.py`