"""
One-shot FYP demo seed: users + DEMO001 + room/cameras/exam.

Usage (from backend folder, venv active):
    python seed_all_demo.py
"""

from seed_demo_cameras import seed as seed_cameras
from seed_demo_users import seed as seed_users


def main() -> None:
    print("=== Users + DEMO001 ===")
    seed_users()
    print()
    print("=== Rooms / cameras / exam ===")
    seed_cameras()
    print()
    print("Demo seed complete.")
    print("Login: invigilator@demo.com (password documented in README)")


if __name__ == "__main__":
    main()
