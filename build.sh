source ./env-wsl/bin/activate
python3 -m pip install -r requirements.txt
pyinstaller --onefile main.py -n vcs-tasks-linux