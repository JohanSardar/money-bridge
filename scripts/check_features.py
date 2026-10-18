import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
FEATURE_KEYS = {"id", "milestone", "title", "requirement", "module", "status", "scenarios"}
SCENARIO_KEYS = {"test", "level", "status"}


def pytest_target_exists(test: str) -> bool:
    file_part, _, name = test.partition("::")
    path = REPO / file_part
    if not path.is_file() or not name:
        return False
    function = name.split("[", 1)[0]
    pattern = re.compile(rf"^\s*(async\s+)?def\s+{re.escape(function)}\s*\(", re.MULTILINE)
    return bool(pattern.search(path.read_text(encoding="utf-8")))


def labelled_target_exists(test: str) -> bool:
    location, _, label = test.partition("::")
    if location == "ci/windows":
        workflows = REPO / ".github" / "workflows"
        texts = [p.read_text(encoding="utf-8") for p in workflows.glob("*.yml")] if workflows.exists() else []
        return any(label in text for text in texts)
    path = REPO / location
    return path.is_file() and label in path.read_text(encoding="utf-8")


def scenario_problems(feature_id: str, scenario: dict, levels: list[str], statuses: list[str]) -> list[str]:
    where = f"{feature_id} / {scenario.get('test')}"
    problems = []
    missing = SCENARIO_KEYS - scenario.keys()
    if missing:
        return [f"{where}: missing {sorted(missing)}"]
    if scenario["level"] not in levels:
        problems.append(f"{where}: unknown level {scenario['level']}")
    if scenario["status"] not in statuses:
        problems.append(f"{where}: unknown status {scenario['status']}")
    if scenario["status"] == "limited" and not scenario.get("limited_reason"):
        problems.append(f"{where}: limited without limited_reason")
    if scenario["status"] == "passing":
        test = scenario["test"]
        if test.endswith(".py") or ".py::" in test:
            if not pytest_target_exists(test):
                problems.append(f"{where}: passing but test not found")
        elif test.startswith("release/"):
            if not scenario.get("evidence"):
                problems.append(f"{where}: passing release scenario needs evidence")
        elif not labelled_target_exists(test):
            problems.append(f"{where}: passing but label not found")
    return problems


def feature_problems(feature: dict, document: dict) -> list[str]:
    fid = feature.get("id", "<no id>")
    missing = FEATURE_KEYS - feature.keys()
    if missing:
        return [f"{fid}: missing {sorted(missing)}"]
    problems = []
    if feature["status"] not in document["feature_statuses"]:
        problems.append(f"{fid}: unknown status {feature['status']}")
    scenarios = feature["scenarios"]
    if not scenarios:
        problems.append(f"{fid}: no scenarios")
    for scenario in scenarios:
        problems.extend(scenario_problems(fid, scenario, document["levels"], document["scenario_statuses"]))
    states = {s.get("status") for s in scenarios}
    if feature["status"] == "done" and (not states <= {"passing", "limited"} or "passing" not in states):
        problems.append(f"{fid}: done requires every scenario passing or limited and at least one passing")
    if feature["status"] == "limited":
        if not feature.get("limited_reason"):
            problems.append(f"{fid}: limited without limited_reason")
        if not states <= {"passing", "limited"}:
            problems.append(f"{fid}: limited feature still has planned scenarios")
    return problems


def problems_in(path: Path) -> list[str]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = []
    seen: set[str] = set()
    tests: set[str] = set()
    for feature in document["features"]:
        fid = feature.get("id")
        if fid in seen:
            problems.append(f"{fid}: duplicate id")
        seen.add(fid)
        for scenario in feature.get("scenarios", []):
            test = scenario.get("test")
            if test in tests:
                problems.append(f"{fid}: scenario {test} listed twice")
            tests.add(test)
        problems.extend(feature_problems(feature, document))
    return problems


def summary(path: Path) -> str:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for feature in document["features"]:
        counts[feature["status"]] = counts.get(feature["status"], 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def main() -> int:
    path = REPO / "features.yaml"
    problems = problems_in(path)
    for problem in problems:
        print(problem)
    print(summary(path))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
