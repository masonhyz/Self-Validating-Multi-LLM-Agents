import os

# ---------------------------------------------------------------------------
# Model selection — swap OUTPUT_MODEL to try different generators
# ---------------------------------------------------------------------------
VERIFIER_MODEL = "glm-4.7:cloud"
CRITIC_MODEL   = "glm-4.7:cloud"
OUTPUT_MODEL   = "cogito-2.1:671b-cloud"
# OUTPUT_MODEL = "gemma3:27b-cloud"
# OUTPUT_MODEL = "qwen3.5:397b-cloud"
# OUTPUT_MODEL = "granite4:latest"

# ---------------------------------------------------------------------------
# Limits & paths
# ---------------------------------------------------------------------------
MAX_OUTPUT_LEN = 50_000
VERIFIER_PATH  = os.path.abspath("outputs/verifier.py")

# ---------------------------------------------------------------------------
# Verifier return-value contract
# ---------------------------------------------------------------------------
DETAILS_REQUIRED_KEYS = {"passed", "failed", "num_passed", "num_failed"}
