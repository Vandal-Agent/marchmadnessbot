import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def run(script_name: str):
    subprocess.run([sys.executable, str(BASE_DIR / script_name)], check=True)


def main():
    run("update_results.py")
    run("evaluate_results.py")


if __name__ == "__main__":
    main()
