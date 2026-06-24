"""
Evaluation Reporter
生成评估报告（JSON + Markdown 表格 + 失败案例分析 + 多模型对比）

Adapted from caip2026 sub-project rag_system/evaluation/reporter.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    import numpy as np
except ImportError:
    np = None


class EvaluationReporter:
    """评估报告生成器

    输出格式：
    - JSON：结构化数据，方便后续分析
    - Markdown：人类可读的报告
    """

    def __init__(self, output_dir: Path | None = None):
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "evaluation_results"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        model_name: str,
        metrics: Dict[str, Any],
        details: List[Dict[str, Any]],
    ) -> Dict[str, Path]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{model_name}_{timestamp}"

        json_path = self.output_dir / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "model_name": model_name,
                "timestamp": timestamp,
                "summary": metrics,
                "details": details,
            }, f, ensure_ascii=False, indent=2)

        md_path = self.output_dir / f"{base_name}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._generate_markdown(model_name, metrics, details))

        print(f"\nReport saved:\n  JSON: {json_path}\n  Markdown: {md_path}")
        return {"json": json_path, "markdown": md_path}

    def _generate_markdown(
        self, model_name: str, metrics: Dict[str, Any], details: List[Dict[str, Any]]
    ) -> str:
        lines = [
            f"# 评估报告：{model_name}",
            "",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 一、总体指标",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
        ]

        bs = metrics.get("bertscore", {})
        if bs:
            lines.append(f"| BERTScore F1 | {bs.get('f1', 0):.4f} |")
            lines.append(f"| BERTScore Precision | {bs.get('precision', 0):.4f} |")
            lines.append(f"| BERTScore Recall | {bs.get('recall', 0):.4f} |")

        rg = metrics.get("rouge_l", {})
        if rg:
            lines.append(f"| ROUGE-L F1 | {rg.get('f', 0):.4f} |")

        lines.append(f"| Exact Match | {metrics.get('exact_match', 0):.4f} |")

        st = metrics.get("structured", {})
        if st:
            lines.append(f"| 风险等级准确率 | {st['risk_level']['accuracy']:.4f} |")
            lines.append(f"| 诈骗类型准确率 | {st['fraud_type']['accuracy']:.4f} |")
            lines.append(f"| 法律引用准确率 | {st['legal_citation']['accuracy']:.4f} |")

        sf = metrics.get("safety", {})
        if sf:
            lines.append(f"| 致命错误率 | {sf['fatal_error_rate']:.4f} |")
            lines.append(f"| 安全性检查 | {'PASS' if sf['pass'] else 'FAIL'} |")

        # 结构化字段详细统计
        lines.extend(["", "## 二、结构化字段详细统计", ""])
        if st:
            for field in ["risk_level", "fraud_type", "legal_citation"]:
                if field in st:
                    info = st[field]
                    lines.append(f"### {field}")
                    lines.append(f"- 准确率：{info['accuracy']:.4f}")
                    lines.append(f"- 正确数 / 总数：{info['correct']} / {info['total']}")
                    if "avg_precision" in info:
                        lines.append(f"- 平均精确率：{info['avg_precision']:.4f}")
                    lines.append("")

        # 失败案例分析
        failures = [d for d in details if d.get("is_failure")]
        if failures:
            lines.extend([
                f"## 三、失败案例分析（共 {len(failures)} 条）",
                "",
            ])
            for i, case in enumerate(failures[:20], 1):
                lines.extend([
                    f"### 案例 {i}",
                    f"- **问题**：{case.get('question', 'N/A')}",
                    f"- **标准答案**：{case.get('reference', 'N/A')[:200]}...",
                    f"- **模型回答**：{case.get('prediction', 'N/A')[:200]}...",
                    f"- **失败原因**：{case.get('failure_reason', 'N/A')}",
                    "",
                ])
            if len(failures) > 20:
                lines.append(f"*... 还有 {len(failures) - 20} 条失败案例，详见 JSON 报告 ...*")

        # 分类统计
        lines.extend(["", "## 四、按诈骗类型分类统计", "",
            "| 诈骗类型 | 样本数 | 平均BERTScore | 风险等级准确率 |",
            "|----------|--------|---------------|----------------|"])

        type_stats: Dict[str, Dict] = {}
        for d in details:
            cat = d.get("category", "未知")
            if cat not in type_stats:
                type_stats[cat] = {"count": 0, "bertscore_sum": 0.0, "risk_correct": 0}
            type_stats[cat]["count"] += 1
            type_stats[cat]["bertscore_sum"] += d.get("bertscore_f1", 0)
            if d.get("risk_level_match"):
                type_stats[cat]["risk_correct"] += 1

        for cat, stats in sorted(type_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            avg_bert = stats["bertscore_sum"] / stats["count"] if stats["count"] > 0 else 0
            risk_acc = stats["risk_correct"] / stats["count"] if stats["count"] > 0 else 0
            lines.append(f"| {cat} | {stats['count']} | {avg_bert:.4f} | {risk_acc:.4f} |")

        lines.extend(["", "---", "*报告由 Anti-Fraud RAG Evaluation System 自动生成*"])
        return "\n".join(lines)

    @staticmethod
    def generate_comparison_report(
        results: Dict[str, Dict[str, Any]],
        output_path: Path,
    ) -> Path:
        lines = [
            "# 多模型对比评估报告",
            "",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 一、总体指标对比",
            "",
            "| 模型 | BERTScore F1 | ROUGE-L | 风险等级准确率 | 诈骗类型准确率 | 法律引用准确率 | 致命错误率 |",
            "|------|-------------|---------|---------------|---------------|---------------|-----------|",
        ]

        for name, m in results.items():
            bs_f1 = m.get("bertscore", {}).get("f1", 0)
            rg_f1 = m.get("rouge_l", {}).get("f", 0)
            risk_acc = m.get("structured", {}).get("risk_level", {}).get("accuracy", 0)
            type_acc = m.get("structured", {}).get("fraud_type", {}).get("accuracy", 0)
            legal_acc = m.get("structured", {}).get("legal_citation", {}).get("accuracy", 0)
            fatal_rate = m.get("safety", {}).get("fatal_error_rate", 0)
            lines.append(
                f"| {name} | {bs_f1:.4f} | {rg_f1:.4f} | "
                f"{risk_acc:.4f} | {type_acc:.4f} | {legal_acc:.4f} | {fatal_rate:.4f} |"
            )

        # Best model per metric
        lines.extend(["", "## 二、各指标最佳模型", ""])
        model_names = list(results.keys())

        def _best(metric_path):
            best_name, best_val = None, -1.0
            for name in model_names:
                val = results[name]
                for key in metric_path:
                    val = val.get(key, {}) if isinstance(val, dict) else 0
                if isinstance(val, (int, float)) and val > best_val:
                    best_val, best_name = val, name
            return best_name, best_val

        bs_best, bs_val = _best(["bertscore", "f1"])
        rg_best, rg_val = _best(["rouge_l", "f"])
        risk_best, risk_val = _best(["structured", "risk_level", "accuracy"])
        type_best, type_val = _best(["structured", "fraud_type", "accuracy"])
        legal_best, legal_val = _best(["structured", "legal_citation", "accuracy"])

        lines.extend([
            f"- **BERTScore F1**：{bs_best} ({bs_val:.4f})",
            f"- **ROUGE-L**：{rg_best} ({rg_val:.4f})",
            f"- **风险等级准确率**：{risk_best} ({risk_val:.4f})",
            f"- **诈骗类型准确率**：{type_best} ({type_val:.4f})",
            f"- **法律引用准确率**：{legal_best} ({legal_val:.4f})",
            "",
        ])

        # RAG vs no-RAG comparison
        rag_models = [n for n in model_names if "rag" in n.lower()]
        base_models = [n for n in model_names if "rag" not in n.lower()]
        if rag_models and base_models:
            lines.append("## 三、RAG 效果分析")
            avg_rag = sum(results[n].get("bertscore", {}).get("f1", 0) for n in rag_models) / len(rag_models)
            avg_base = sum(results[n].get("bertscore", {}).get("f1", 0) for n in base_models) / len(base_models)
            lines.append(f"- 带 RAG 模型平均 BERTScore：{avg_rag:.4f}")
            lines.append(f"- 不带 RAG 模型平均 BERTScore：{avg_base:.4f}")
            diff = avg_rag - avg_base
            lines.append(f"- 差异：{diff:+.4f} ({'RAG 提升' if diff > 0 else 'RAG 下降'})")
            lines.append("")

        lines.extend([
            "---",
            "*报告由 Anti-Fraud RAG Evaluation System 自动生成*",
        ])

        content = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Comparison report saved to {output_path}")
        return output_path
