#!/usr/bin/env python3
"""
QA Evaluation Script for Anti-Fraud RAG System

Evaluates the anti-fraud dialogue pipeline against a QA test set.
Supports multi-mode comparison: rule-only, rule+LLM, rule+RAG, rule+RAG+LLM.

Usage:
  # Single mode
  python scripts/evaluate_qa.py --testset evaluation/qa_test.json --mode rule_llm

  # All modes comparison
  python scripts/evaluate_qa.py --testset evaluation/qa_test.json --all

  # With sample limit for quick testing
  python scripts/evaluate_qa.py --testset evaluation/qa_test.json --all -n 20
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from evaluation.metrics import MetricsCalculator
from evaluation.reporter import EvaluationReporter


def load_testset(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    raise ValueError(f"Unsupported testset format: {type(data)}")


def build_rule_only_pipeline():
    """Build a minimal rule-engine-only pipeline (no RAG, no LLM)."""
    from app.services.knowledge_base import KnowledgeBase
    from app.services.intent_recognizer import IntentRecognizer
    from app.services.risk_engine import RiskEngine

    kb = KnowledgeBase(PROJECT_DIR / "app" / "data" / "knowledge_base.json")
    intent = IntentRecognizer()
    risk = RiskEngine()
    return kb, intent, risk


def run_rule_only(testset: List[Dict[str, Any]], max_samples: int | None = None) -> List[Dict[str, Any]]:
    """Mode 1: Rule engine only — no LLM, no RAG."""
    print("\n" + "=" * 60)
    print("Mode: Rule-Only (No LLM, No RAG)")
    print("=" * 60)

    kb, intent, risk = build_rule_only_pipeline()
    results = []
    samples = testset[:max_samples] if max_samples else testset

    for item in samples:
        question = item.get("question", "")
        try:
            matched = kb.search_scams(question)
            risk_result = risk.evaluate_text(question)
            reply = _format_rule_reply(risk_result, matched)
        except Exception as e:
            print(f"  Error on: {question[:50]}... {e}")
            reply = ""

        results.append({
            "question": question,
            "prediction": reply,
            "reference": item.get("answer", ""),
            "reference_structured": {
                "risk_level": item.get("risk_level", ""),
                "fraud_type": item.get("fraud_type", ""),
                "legal_citations": item.get("legal_citations", []),
            },
            "category": item.get("category", item.get("fraud_type", "")),
        })
    return results


def run_rule_llm(testset: List[Dict[str, Any]], max_samples: int | None = None) -> List[Dict[str, Any]]:
    """Mode 2: Rule engine + LLM reply generation (no RAG)."""
    print("\n" + "=" * 60)
    print("Mode: Rule + LLM (No RAG)")
    print("=" * 60)

    from app.services.llm_client import chat_payload, first_choice_text, load_llm_config, post_chat_completion

    kb, intent, risk = build_rule_only_pipeline()
    llm_config = load_llm_config()
    results = []
    samples = testset[:max_samples] if max_samples else testset

    for item in samples:
        question = item.get("question", "")
        try:
            matched = kb.search_scams(question)
            risk_result = risk.evaluate_text(question)
            rule_reply = _format_rule_reply(risk_result, matched)

            messages = [
                {"role": "system", "content": _EVAL_SYSTEM_PROMPT},
                {"role": "user", "content": f"用户问题：{question}\n\n规则引擎分析：{rule_reply}"},
            ]
            payload = chat_payload(config=llm_config, messages=messages, temperature=0.1, max_tokens=512)
            data = post_chat_completion(llm_config, payload)
            reply = first_choice_text(data)
        except Exception as e:
            print(f"  Error on: {question[:50]}... {e}")
            reply = ""

        results.append({
            "question": question,
            "prediction": reply,
            "reference": item.get("answer", ""),
            "reference_structured": {
                "risk_level": item.get("risk_level", ""),
                "fraud_type": item.get("fraud_type", ""),
                "legal_citations": item.get("legal_citations", []),
            },
            "category": item.get("category", item.get("fraud_type", "")),
        })
    return results


def run_rule_rag(testset: List[Dict[str, Any]], max_samples: int | None = None) -> List[Dict[str, Any]]:
    """Mode 3: Rule engine + RAG retrieval (no LLM generation)."""
    print("\n" + "=" * 60)
    print("Mode: Rule + RAG (No LLM)")
    print("=" * 60)

    kb, intent, risk = build_rule_only_pipeline()
    results = []
    samples = testset[:max_samples] if max_samples else testset

    for item in samples:
        question = item.get("question", "")
        try:
            matched = kb.search_scams(question)
            risk_result = risk.evaluate_text(question)
            rule_reply = _format_rule_reply(risk_result, matched)

            # Try RAG retrieval
            rag_context = ""
            try:
                from app.services.knowledge_retriever import KnowledgeRetriever
                retriever = KnowledgeRetriever.from_env()
                if retriever:
                    rag_results = retriever.retrieve(question, top_k=3)
                    rag_context = "\n".join(
                        f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                        for r in rag_results
                    )
            except Exception:
                pass

            reply = rule_reply
            if rag_context:
                reply = f"{rule_reply}\n\n参考知识：\n{rag_context}"
        except Exception as e:
            print(f"  Error on: {question[:50]}... {e}")
            reply = ""

        results.append({
            "question": question,
            "prediction": reply,
            "reference": item.get("answer", ""),
            "reference_structured": {
                "risk_level": item.get("risk_level", ""),
                "fraud_type": item.get("fraud_type", ""),
                "legal_citations": item.get("legal_citations", []),
            },
            "category": item.get("category", item.get("fraud_type", "")),
        })
    return results


def run_rule_rag_llm(testset: List[Dict[str, Any]], max_samples: int | None = None) -> List[Dict[str, Any]]:
    """Mode 4: Rule engine + RAG + LLM (full pipeline)."""
    print("\n" + "=" * 60)
    print("Mode: Rule + RAG + LLM (Full Pipeline)")
    print("=" * 60)

    from app.services.llm_client import chat_payload, first_choice_text, load_llm_config, post_chat_completion

    kb, intent, risk = build_rule_only_pipeline()
    llm_config = load_llm_config()
    results = []
    samples = testset[:max_samples] if max_samples else testset

    for item in samples:
        question = item.get("question", "")
        try:
            matched = kb.search_scams(question)
            risk_result = risk.evaluate_text(question)
            rule_reply = _format_rule_reply(risk_result, matched)

            rag_context = ""
            try:
                from app.services.knowledge_retriever import KnowledgeRetriever
                retriever = KnowledgeRetriever.from_env()
                if retriever:
                    rag_results = retriever.retrieve(question, top_k=3)
                    rag_context = "\n".join(
                        f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                        for r in rag_results
                    )
            except Exception:
                pass

            messages = [
                {"role": "system", "content": _EVAL_SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"用户问题：{question}\n\n"
                    f"规则引擎分析：{rule_reply}\n\n"
                    f"参考知识：\n{rag_context or '无'}"
                )},
            ]
            payload = chat_payload(config=llm_config, messages=messages, temperature=0.1, max_tokens=512)
            data = post_chat_completion(llm_config, payload)
            reply = first_choice_text(data)
        except Exception as e:
            print(f"  Error on: {question[:50]}... {e}")
            reply = ""

        results.append({
            "question": question,
            "prediction": reply,
            "reference": item.get("answer", ""),
            "reference_structured": {
                "risk_level": item.get("risk_level", ""),
                "fraud_type": item.get("fraud_type", ""),
                "legal_citations": item.get("legal_citations", []),
            },
            "category": item.get("category", item.get("fraud_type", "")),
        })
    return results


_EVAL_SYSTEM_PROMPT = """你是一个反诈风险评估专家。请根据用户问题和规则引擎分析，输出评估结果。

格式要求（必须严格遵循）：
风险等级：[高/中/低]
诈骗类型：[具体诈骗类型名称]
分析理由：[简要说明]
建议：[具体可操作的建议]
如有法律依据，请引用相关法律名称。"""


def _format_rule_reply(risk_result: dict, matched: list) -> str:
    """Format rule engine output as plain text."""
    parts = []
    level = risk_result.get("risk_level", "低")
    score = risk_result.get("risk_score", 0)
    parts.append(f"风险等级：{level}（分数：{score}）")

    if matched:
        names = [s.get("name", "") for s in matched[:3]]
        parts.append(f"匹配诈骗类型：{'、'.join(names)}")

    rules = risk_result.get("matched_rules", [])
    if rules:
        parts.append("命中规则：" + "；".join(
            r.get("reason", str(r)) for r in rules[:5]
        ))

    return "\n".join(parts)


def compute_metrics(raw_results: List[Dict[str, Any]], calculator: MetricsCalculator) -> tuple:
    predictions = [r["prediction"] for r in raw_results]
    references_text = [r["reference"] for r in raw_results]
    references_structured = [r["reference_structured"] for r in raw_results]

    metrics = calculator.evaluate_all(predictions, references_text, references_structured)

    details = []
    for i, r in enumerate(raw_results):
        pred = r["prediction"]
        ref_struct = r["reference_structured"]
        pred_risk = MetricsCalculator.extract_risk_level(pred)
        pred_type = MetricsCalculator.extract_fraud_type(pred)

        is_failure = False
        failure_reasons = []

        if ref_struct.get("risk_level") and pred_risk != ref_struct["risk_level"]:
            is_failure = True
            failure_reasons.append(f"风险等级错误：预测'{pred_risk}' vs 标准'{ref_struct['risk_level']}'")

        if ref_struct.get("fraud_type"):
            ref_type = ref_struct["fraud_type"]
            if pred_type != ref_type and pred_type not in ref_type and ref_type not in pred_type:
                is_failure = True
                failure_reasons.append(f"诈骗类型错误：预测'{pred_type}' vs 标准'{ref_type}'")

        details.append({
            "question": r["question"],
            "prediction": pred,
            "reference": r["reference"],
            "category": r["category"],
            "is_failure": is_failure,
            "failure_reason": "; ".join(failure_reasons) if failure_reasons else "",
            "risk_level_match": pred_risk == ref_struct.get("risk_level", ""),
            "fraud_type_match": (
                pred_type == ref_struct.get("fraud_type", "")
                or ref_struct.get("fraud_type", "") in pred_type
                or pred_type in ref_struct.get("fraud_type", "")
            ),
            "bertscore_f1": 0.0,
        })

    # Per-sample BERTScore in batches
    print("\nCalculating per-sample BERTScore...")
    for i in range(0, len(predictions), 32):
        batch_preds = predictions[i:i + 32]
        batch_refs = references_text[i:i + 32]
        try:
            bs = calculator.calc_bertscore(batch_preds, batch_refs)
            for j in range(len(batch_preds)):
                if i + j < len(details):
                    details[i + j]["bertscore_f1"] = bs["f1"]
        except Exception:
            pass

    return metrics, details


MODES = {
    "rule_only": run_rule_only,
    "rule_llm": run_rule_llm,
    "rule_rag": run_rule_rag,
    "rule_rag_llm": run_rule_rag_llm,
}


def main():
    parser = argparse.ArgumentParser(description="Evaluate QA on anti-fraud system")
    parser.add_argument("--testset", "-t", type=str, required=True, help="Path to QA testset JSON")
    parser.add_argument("--mode", "-m", type=str, default="rule_rag_llm",
                        choices=list(MODES.keys()), help="Evaluation mode")
    parser.add_argument("--all", "-a", action="store_true", help="Evaluate all modes")
    parser.add_argument("--max-samples", "-n", type=int, default=None, help="Limit test samples")
    parser.add_argument("--output-dir", "-o", type=str, default="evaluation_results", help="Output directory")
    args = parser.parse_args()

    testset_path = Path(args.testset)
    if not testset_path.exists():
        print(f"Error: Testset not found: {testset_path}")
        sys.exit(1)

    testset = load_testset(testset_path)
    print(f"Loaded {len(testset)} test cases from {testset_path}")
    if args.max_samples:
        print(f"Limiting to {args.max_samples} samples")

    active_modes = list(MODES.keys()) if args.all else [args.mode]
    calculator = MetricsCalculator()
    reporter = EvaluationReporter(output_dir=Path(args.output_dir))
    all_mode_results: Dict[str, Any] = {}

    for mode in active_modes:
        raw_results = MODES[mode](testset, args.max_samples)
        print(f"\nComputing metrics for {mode}...")
        metrics, details = compute_metrics(raw_results, calculator)
        all_mode_results[mode] = metrics

        print("\n" + "=" * 60)
        print(f"Results: {mode}")
        print("=" * 60)
        print(f"  BERTScore F1:        {metrics['bertscore']['f1']:.4f}")
        print(f"  ROUGE-L F1:          {metrics['rouge_l']['f']:.4f}")
        print(f"  Exact Match:         {metrics['exact_match']:.4f}")
        print(f"  Risk Level Accuracy: {metrics['structured']['risk_level']['accuracy']:.4f}")
        print(f"  Fraud Type Accuracy: {metrics['structured']['fraud_type']['accuracy']:.4f}")
        print(f"  Legal Citation Acc:  {metrics['structured']['legal_citation']['accuracy']:.4f}")
        print(f"  Fatal Error Rate:    {metrics['safety']['fatal_error_rate']:.4f}")
        print(f"  Safety Pass:         {'YES' if metrics['safety']['pass'] else 'NO'}")

        reporter.generate_report(mode, metrics, details)

    if len(active_modes) > 1:
        print("\n" + "=" * 60)
        print("Generating comparison report...")
        comparison_path = Path(args.output_dir) / f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        EvaluationReporter.generate_comparison_report(all_mode_results, comparison_path)

    print(f"\nAll evaluations completed. Results in: {args.output_dir}")


if __name__ == "__main__":
    main()
