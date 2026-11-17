"""Configuration/response checks; never connect to a database."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]

class SecretConfigTests(unittest.TestCase):
    def test_exported_database_url_takes_priority_over_local_file(self):
        value='postgresql+psycopg://test:example@localhost:5432/test'
        env={**os.environ,'DATABASE_URL':value}
        result=subprocess.run([sys.executable,'-c',
            'import os; from backend.database import DATABASE_URL; assert DATABASE_URL == os.environ["DATABASE_URL"]'],
            cwd=ROOT,env=env,capture_output=True)
        self.assertEqual(result.returncode,0,'Environment URL priority check failed.')

    def test_missing_configuration_fails_without_secret_fallback(self):
        env={**os.environ,'PYTHON_DOTENV_DISABLED':'1'}
        env.pop('DATABASE_URL',None)
        result=subprocess.run([sys.executable,'-c','import backend.database'],cwd=ROOT,env=env,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'DATABASE_URL is required',result.stderr)
        self.assertNotIn(b'postgresql+psycopg://',result.stderr)

    def test_db_health_does_not_expose_raw_error(self):
        from backend.main import app
        from backend.database import get_db
        class FailingDB:
            def execute(self,*args,**kwargs): raise RuntimeError('PRIVATE_CREDENTIAL_MARKER')
        def dependency(): yield FailingDB()
        previous=app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db]=dependency
        try:
            response=TestClient(app).get('/health/db')
            self.assertEqual(response.status_code,500)
            self.assertNotIn('PRIVATE_CREDENTIAL_MARKER',response.text)
            self.assertIn('DATABASE_URL',response.json()['detail'])
        finally:
            if previous is None: app.dependency_overrides.pop(get_db,None)
            else: app.dependency_overrides[get_db]=previous

if __name__=='__main__': unittest.main()
