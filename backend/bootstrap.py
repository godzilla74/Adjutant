# backend/bootstrap.py
"""Load env config before any module reads env vars at import time.

Import this module as the FIRST local import in any entry point (main.py, test
setup, etc.) that needs env vars to be present when backend modules load.
"""
import os
from dotenv import load_dotenv

_config_path = os.environ.get("ADJUTANT_CONFIG", ".env")
load_dotenv(_config_path)
