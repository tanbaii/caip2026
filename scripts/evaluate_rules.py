from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.risk_engine import RiskEngine  # noqa: E402


DEFAULT_DATASET = ROOT_DIR / "evaluation" / "risk_cases.json"
LEVEL_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class CaseResult:
    case_id: str
    case_type: str
    category: str
    expected_risky: bool
    predicted_risky: bool
    level: str
    score: int
    matched_rules: list[str]
    assertion_errors: list[str]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _matched_rule_names(result: dict[str, Any]) -> list[str]:
    return [
        str(item.get("rule", "unknown"))
        for item in result.get("matched_rules", [])
        if isinstance(item, dict)
    ]


def _assert_case(case: dict[str, Any], level: str, rules: list[str]) -> list[str]:
    errors: list[str] = []
    level_rank = LEVEL_RANK.get(level, -1)
    minimum = case.get("minimum_level")
    maximum = case.get("maximum_level")
    if minimum and level_rank < LEVEL_RANK[str(minimum)]:
        errors.append(f"风险等级 {level} 低于期望下限 {minimum}")
    if maximum and level_rank > LEVEL_RANK[str(maximum)]:
        errors.append(f"风险等级 {level} 高于期望上限 {maximum}")

    missing = sorted(set(case.get("expected_rules", [])) - set(rules))
    forbidden = sorted(set(case.get("forbidden_rules", [])) & set(rules))
    if missing:
        errors.append(f"缺少规则: {', '.join(missing)}")
    if forbidden:
        errors.append(f"误命中规则: {', '.join(forbidden)}")
    return errors


def evaluate_dataset(
    dataset: dict[str, Any],
    *,
    engine: RiskEngine | None = None,
    iterations: int = 1,
) -> dict[str, Any]:
    evaluator = engine or RiskEngine()
    threshold = str(dataset.get("meta", {}).get("risk_threshold", "medium"))
    threshold_rank = LEVEL_RANK[threshold]
    case_results: list[CaseResult] = []
    latencies_ms: list[float] = []

    for case_type, key in (("text", "text_cases"), ("url", "url_cases")):
        for case in dataset.get(key, []):
            first_result: dict[str, Any] | None = None
            for _ in range(max(1, iterations)):
                start = time.perf_counter()
                if case_type == "text":
                    result = evaluator.evaluate_text(
                        str(case["input"]),
                        matched_scams=[],
                        user_role=str(case.get("user_role", "general")),
                        emotion=case.get("emotion"),
                    )
                else:
                    result = evaluator.evaluate_url(str(case["input"]))
                latencies_ms.append((time.perf_counter() - start) * 1000)
                if first_result is None:
                    first_result = result

            assert first_result is not None
            level = str(first_result["level"])
            rules = _matched_rule_names(first_result)
            case_results.append(CaseResult(
                case_id=str(case["id"]),
                case_type=case_type,
                category=str(case.get("category", "未分类")),
                expected_risky=bool(case["expected_risky"]),
                predicted_risky=LEVEL_RANK.get(level, -1) >= threshold_rank,
                level=level,
                score=int(first_result["score"]),
                matched_rules=rules,
                assertion_errors=_assert_case(case, level, rules),
            ))

    tp = sum(item.expected_risky and item.predicted_risky for item in case_results)
    tn = sum(not item.expected_risky and not item.predicted_risky for item in case_results)
    fp = sum(not item.expected_risky and item.predicted_risky for item in case_results)
    fn = sum(item.expected_risky and not item.predicted_risky for item in case_results)
    total = len(case_results)

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator * 100, 2) if denominator else 0.0

    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 2) if precision + recall else 0.0
    metrics = {
        "total_cases": total,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy_pct": ratio(tp + tn, total),
        "precision_pct": precision,
        "recall_pct": recall,
        "f1_pct": f1,
        "false_positive_rate_pct": ratio(fp, fp + tn),
        "assertion_pass_rate_pct": ratio(sum(not item.assertion_errors for item in case_results), total),
        "avg_latency_ms": round(statistics.mean(latencies_ms), 3) if latencies_ms else 0.0,
        "p95_latency_ms": round(percentile(latencies_ms, 0.95), 3),
        "iterations": max(1, iterations),
    }
    return {
        "dataset_version": str(dataset.get("meta", {}).get("version", "unknown")),
        "threshold": threshold,
        "ruleset_versions": evaluator.ruleset_versions,
        "metrics": metrics,
        "cases": [item.__dict__ for item in case_results],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    lines = [
        "# 反诈规则离线评测报告",
        "",
        f"- 评测集版本：`{summary['dataset_version']}`",
        f"- 文本规则版本：`{summary['ruleset_versions']['text']}`",
        f"- URL 规则版本：`{summary['ruleset_versions']['url']}`",
        f"- 风险判定阈值：`{summary['threshold']}` 及以上",
        f"- 每条样本执行次数：`{metrics['iterations']}`",
        "",
        "## 核心指标",
        "",
        "| 样本数 | 准确率 | 精确率 | 召回率 | F1 | 误报率 | 规则断言通过率 | 平均延迟 | P95 延迟 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {metrics['total_cases']} | {metrics['accuracy_pct']}% | "
            f"{metrics['precision_pct']}% | {metrics['recall_pct']}% | {metrics['f1_pct']}% | "
            f"{metrics['false_positive_rate_pct']}% | {metrics['assertion_pass_rate_pct']}% | "
            f"{metrics['avg_latency_ms']} ms | {metrics['p95_latency_ms']} ms |"
        ),
        "",
        f"混淆矩阵：TP={metrics['tp']}，TN={metrics['tn']}，FP={metrics['fp']}，FN={metrics['fn']}。",
        "",
        "## 未通过样本",
        "",
    ]
    failed = [
        item for item in summary["cases"]
        if item["expected_risky"] != item["predicted_risky"] or item["assertion_errors"]
    ]
    if not failed:
        lines.append("当前评测集全部通过。")
    else:
        lines.extend([
            "| ID | 类型 | 分类 | 期望风险 | 实际等级 | 命中规则 | 问题 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for item in failed:
            problems = list(item["assertion_errors"])
            if item["expected_risky"] != item["predicted_risky"]:
                problems.append("风险分类不一致")
            lines.append(
                f"| {item['case_id']} | {item['case_type']} | {item['category']} | "
                f"{'是' if item['expected_risky'] else '否'} | {item['level']} | "
                f"{', '.join(item['matched_rules']) or '-'} | {'；'.join(problems)} |"
            )

    lines.extend([
        "",
        "## 复现方式",
        "",
        "```bash",
        "python scripts/evaluate_rules.py --iterations 100 --output RULE_EVALUATION.md",
        "```",
        "",
        "> 本报告是规则层离线回归结果，不等同于真实世界诈骗识别准确率。新增规则时应同步补充正例与安全反例。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate anti-fraud text and URL rules offline.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    summary = evaluate_dataset(dataset, iterations=max(1, args.iterations))
    output = json.dumps(summary, ensure_ascii=False, indent=2) if args.json else render_markdown(summary)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)

    metrics = summary["metrics"]
    has_regression = metrics["fp"] > 0 or metrics["fn"] > 0 or metrics["assertion_pass_rate_pct"] < 100
    return 1 if args.fail_on_regression and has_regression else 0


if __name__ == "__main__":
    raise SystemExit(main())
