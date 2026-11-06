"""Run this file with the editor's Run button to open Jugar."""

from pathlib import Path
import subprocess
import sys


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    interpreter = root / ".venv" / "Scripts" / "python.exe"
    if interpreter.is_file() and Path(sys.executable).resolve() != interpreter.resolve():
        raise SystemExit(subprocess.call([str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]]))
    from src.jugar import run

    run()
