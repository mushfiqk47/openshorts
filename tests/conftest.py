import os
import sys

# Make the repo root importable so tests can import the app modules directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tests always run the app in self-host (BYOK) mode. app.py freezes
# BILLING_ENABLED at import time and load_dotenv never overrides an existing
# variable, so this must be set here — before any test module imports app — or
# the suite's behavior would depend on the developer's personal .env.
os.environ["BILLING_ENABLED"] = "0"
# Same class of leak as above: config.py freezes these at import time, and the
# source-gate tests assume YouTube ingest enabled + the default 45s minimum.
# A developer's personal .env (e.g. DISABLE_YOUTUBE_URL=true) must not flip
# the suite from green to red.
os.environ["DISABLE_YOUTUBE_URL"] = "0"
os.environ["MIN_SOURCE_SECONDS"] = "45"
