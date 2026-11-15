import os
import sys

# Make the repo root importable so tests can import the app modules directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tests always run the app in self-host (BYOK) mode. app.py freezes
# BILLING_ENABLED at import time and load_dotenv never overrides an existing
# variable, so this must be set here — before any test module imports app — or
# the suite's behavior would depend on the developer's personal .env.
os.environ["BILLING_ENABLED"] = "0"

# Same dependency-on-personal-.env problem for the ASR endpoint: the developer's
# .env may point transcription at a remote Colab server, and one transcribe test
# that quietly POSTs to a live tunnel is neither hermetic nor free. Freeze it
# empty (like BILLING_ENABLED above): load_dotenv never overrides an existing
# variable, so an empty value blocks the .env one; tests that need the remote
# path set their own.
os.environ["NEMO_ASR_URL"] = ""
