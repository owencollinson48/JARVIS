"""Explicit user-run Windows setup. Does not overwrite an existing scheduled task."""
import os
from pathlib import Path
import subprocess
import sys

if __name__=='__main__':
    if os.name!='nt':raise SystemExit('Run this on your Windows PC only.')
    root=Path(__file__).resolve().parent
    command=subprocess.list2cmdline([sys.executable,str(root/'task_worker.py'),'--once'])
    subprocess.run(['schtasks','/Create','/TN','JARVIS-ApprovedChecks','/SC','MINUTE','/MO','5','/TR',command,'/RL','LIMITED'],check=True)
    print('Created JARVIS-ApprovedChecks. Computer must be on; Task Scheduler settings control sign-in requirements. No paid channel was enabled by this installer.')
