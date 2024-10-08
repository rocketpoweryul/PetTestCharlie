@echo off

:: Deactivate any currently active conda environment
echo Deactivating any current conda environment...
conda deactivate

:: Activate the pettestcharlie environment
echo Activating the conda environment 'pettestcharlie'...
call conda activate pettestcharlie

:: Run the app.py script
echo Running app.py...
python app.py

:: Pause to keep the terminal open
echo Script complete. Press any key to exit.
pause
