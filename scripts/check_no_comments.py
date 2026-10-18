import io
import sys
import tokenize
from pathlib import Path

ROOTS = ("src", "tests", "scripts")


def comment_lines(path: Path) -> list[int]:
    source = path.read_text(encoding="utf-8")
    found = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if token.start[0] == 1 and token.string.startswith("#!"):
            continue
        found.append(token.start[0])
    return found


def shell_comment_lines(path: Path) -> list[int]:
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if number == 1 and line.startswith("#!"):
            continue
        if line.lstrip().startswith("#"):
            found.append(number)
    return found


def violations(repo: Path) -> list[str]:
    problems = []
    for root in ROOTS:
        base = repo / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            problems.extend(f"{path.relative_to(repo)}:{line}" for line in comment_lines(path))
        for path in sorted(base.rglob("*.sh")):
            problems.extend(f"{path.relative_to(repo)}:{line}" for line in shell_comment_lines(path))
    return problems


def main() -> int:
    problems = violations(Path(__file__).resolve().parent.parent)
    for problem in problems:
        print(f"comment not allowed: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
