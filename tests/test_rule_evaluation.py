import json
from pathlib import Path

from scripts.evaluate_rules import evaluate_dataset, render_markdown


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_rule_evaluation_dataset_has_balanced_coverage():
    dataset = json.loads((ROOT_DIR / "evaluation" / "risk_cases.json").read_text(encoding="utf-8"))

    cases = dataset["text_cases"] + dataset["url_cases"]
    risky = [case for case in cases if case["expected_risky"]]
    safe = [case for case in cases if not case["expected_risky"]]

    assert len(dataset["text_cases"]) >= 15
    assert len(dataset["url_cases"]) >= 10
    assert len(risky) >= 15
    assert len(safe) >= 5
    assert len({case["id"] for case in cases}) == len(cases)


def test_rule_evaluation_has_no_regressions():
    dataset = json.loads((ROOT_DIR / "evaluation" / "risk_cases.json").read_text(encoding="utf-8"))

    summary = evaluate_dataset(dataset)

    assert summary["metrics"]["false_positive_rate_pct"] == 0
    assert summary["metrics"]["recall_pct"] == 100
    assert summary["metrics"]["assertion_pass_rate_pct"] == 100
    assert "P95 延迟" in render_markdown(summary)
