"""Developer fixture for files_browser.cjs; disposable data and mocked Windows launches."""
from pathlib import Path
import os
from unittest.mock import patch
from flask import jsonify
from jarvis import create_app, storage

if __name__ == '__main__':
    root=Path(__file__).resolve().parent.parent
    app=create_app(root/'.ui-check/files-final-browser.db')
    app.view_functions['files.locations']=lambda:jsonify(supported=False,locations=[])
    with storage.connect(app.config['DATABASE']) as db:
        db.execute("INSERT INTO settings VALUES('computer_enabled','1') ON CONFLICT(key) DO UPDATE SET value='1'")
    with patch('jarvis.windows.supported',return_value=True),patch('jarvis.windows.execute',return_value='TEST ONLY: Windows driver mocked.'):
        app.run(host='127.0.0.1',port=int(os.environ.get('JARVIS_TEST_PORT','5035')),debug=False)
