"""Isolated browser-test server: a new disposable database for every run."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app


if __name__ == '__main__':
    with TemporaryDirectory(prefix='nomad-e2e-') as directory:
        os.environ['NOMAD_DB'] = str(Path(directory) / 'test.sqlite3')
        os.environ['NOMAD_DEMO'] = '1'
        app = create_app()
        app.state.service.seed_demo()
        uvicorn.run(app, host='127.0.0.1', port=8009)
