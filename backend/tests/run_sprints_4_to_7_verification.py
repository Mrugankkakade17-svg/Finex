"""
Direct verification runner for Sprint 4 to 7 tests.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(r"c:\Users\VICTUS\OneDrive\Desktop\Anti-Gravity")
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.test_sprints_4_to_7 import (
    test_sprint4_paper_account_summary,
    test_sprint4_paper_order_execution,
    test_sprint4_goals_projection,
    test_sprint5_privacy_consent_and_export,
    test_sprint5_spending_trends_and_masking,
    test_sprint6_grounded_ai_assistant_and_refusal,
    test_sprint6_smart_alerts_and_notifications,
    test_sprint7_observability_and_preflight,
)

def run():
    print("Testing Sprint 4...")
    test_sprint4_paper_account_summary()
    test_sprint4_paper_order_execution()
    test_sprint4_goals_projection()
    print(" [x] Sprint 4 Paper Trading & Goals PASSED.")

    print("Testing Sprint 5...")
    test_sprint5_privacy_consent_and_export()
    test_sprint5_spending_trends_and_masking()
    print(" [x] Sprint 5 Privacy Controls & Spending Trends PASSED.")

    print("Testing Sprint 6...")
    test_sprint6_grounded_ai_assistant_and_refusal()
    test_sprint6_smart_alerts_and_notifications()
    print(" [x] Sprint 6 Grounded AI & Smart Alerts PASSED.")

    print("Testing Sprint 7...")
    test_sprint7_observability_and_preflight()
    print(" [x] Sprint 7 Hardening & Ops Preflight PASSED.")

    print("\n=======================================================")
    print("ALL TESTS FOR SPRINTS 4 THROUGH 7 PASSED WITH ZERO ERRORS!")
    print("=======================================================")

if __name__ == "__main__":
    run()

