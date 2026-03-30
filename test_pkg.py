import reviewer
import sys

# Configure logging to stdout so we can see it
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

import os

print("Starting review test...")
try:
    result = reviewer.run_agentic_review(working_dir=os.getcwd(), diff_target="staged")
    print("\n--- RESULT ---")
    print(result)
except Exception as e:
    print(f"\nERROR: {e}")
