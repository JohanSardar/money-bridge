import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "src" / "money_bridge"
ALLOWED = {
    "kernel": set(),
    "evidence": {"kernel"},
    "sources": {"kernel", "evidence"},
    "access": {"kernel", "evidence", "sources", "host", "executor"},
    "executor": {"kernel", "host"},
    "host": {"kernel"},
    "app": {"kernel", "evidence", "sources", "access", "executor", "host"},
}


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def boundary_violations() -> list[str]:
    problems = []
    for package_dir in sorted(p for p in PACKAGE.iterdir() if p.is_dir() and p.name in ALLOWED):
        owner = package_dir.name
        for path in package_dir.rglob("*.py"):
            for name in imported_modules(path):
                parts = name.split(".")
                if parts[0] != "money_bridge" or len(parts) < 2 or parts[1] == owner:
                    continue
                target = parts[1]
                where = f"{path.relative_to(REPO)} imports {name}"
                if target not in ALLOWED[owner]:
                    problems.append(f"{where}: {owner} may not import {target}")
                elif len(parts) > 2:
                    problems.append(f"{where}: import money_bridge.{target} public interface only")
    return problems


def test_no_comments() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check_no_comments.py")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout


def test_import_boundaries() -> None:
    assert boundary_violations() == []


def test_features_yaml_valid() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check_features.py")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout
