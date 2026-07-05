from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "dist" / "browser-wheels"


def _strip_dependencies(pyproject_text: str) -> str:
    dependency_block = re.compile(
        r"dependencies\s*=\s*\[(?:.|\n)*?\]\n",
        flags=re.MULTILINE,
    )
    stripped = dependency_block.sub("dependencies = []\n", pyproject_text, count=1)
    if stripped == pyproject_text:
        raise SystemExit("Failed to strip dependencies from pyproject.toml for browser wheel build")
    return stripped


def _build_browser_wheel(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    for existing in out_dir.glob("codeflow_py-*.whl"):
        existing.unlink()

    with tempfile.TemporaryDirectory(prefix="codeflow_py_browser_build_") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(REPO_ROOT / "src", temp_root / "src")
        shutil.copyfile(REPO_ROOT / "README.md", temp_root / "README.md")
        pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        (temp_root / "pyproject.toml").write_text(
            _strip_dependencies(pyproject_text),
            encoding="utf-8",
        )

        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
            cwd=temp_root,
            check=True,
        )

    wheels = sorted(out_dir.glob("codeflow_py-*.whl"))
    if not wheels:
        raise SystemExit("Failed to build browser wheel for codeflow-py")
    return wheels[-1]


def main() -> None:
    parser = ArgumentParser(description="Build a browser-safe wheel for codeflow-py.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Directory to place the built wheel (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    wheel_path = _build_browser_wheel(args.out_dir)
    print(f"built browser wheel: {wheel_path}")


if __name__ == "__main__":
    main()
