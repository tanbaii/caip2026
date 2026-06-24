"""
Evaluation Metrics Calculator
支持 BERTScore、ROUGE-L、结构化字段匹配、法律引用准确率、安全性检查

Adapted from caip2026 sub-project rag_system/evaluation/metrics.py
"""

import re
import json
from typing import Any, Dict, List, Tuple

try:
    import numpy as np
except ImportError:
    np = None


class MetricsCalculator:
    """评估指标计算器

    支持的指标：
    - BERTScore (F1): 语义相似度
    - ROUGE-L: 最长公共子序列
    - Exact Match: 精确匹配率
    - Structured Accuracy: 结构化字段准确率（风险等级、诈骗类型、法律引用）
    - Safety Check: 安全性检查（致命错误识别）
    """

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._bertscore = None
        self._rouge = None

    def _load_bertscore(self):
        if self._bertscore is None:
            try:
                from bert_score import score as bert_score_fn
                self._bertscore = bert_score_fn
            except ImportError:
                print("Warning: bert-score not installed. BERTScore skipped.")

    def _load_rouge(self):
        if self._rouge is None:
            try:
                from rouge import Rouge
                self._rouge = Rouge()
            except ImportError:
                print("Warning: rouge not installed. ROUGE-L skipped.")

    # ── 1. BERTScore ──
    def calc_bertscore(
        self,
        predictions: List[str],
        references: List[str],
        lang: str = "zh",
    ) -> Dict[str, float]:
        self._load_bertscore()
        if self._bertscore is None:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        valid = [(p, r) for p, r in zip(predictions, references) if p.strip() and r.strip()]
        if not valid:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        preds, refs = zip(*valid)
        try:
            P, R, F1 = self._bertscore(
                list(preds), list(refs),
                lang=lang,
                device=self.device if self.device.startswith("cuda") else "cpu",
                verbose=False,
            )
            return {"precision": float(P.mean()), "recall": float(R.mean()), "f1": float(F1.mean())}
        except Exception as e:
            print(f"BERTScore failed: {e}")
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # ── 2. ROUGE-L ──
    def calc_rouge_l(self, predictions: List[str], references: List[str]) -> Dict[str, float]:
        self._load_rouge()
        if self._rouge is None:
            return {"f": 0.0, "p": 0.0, "r": 0.0}

        scores = {"f": [], "p": [], "r": []}
        for pred, ref in zip(predictions, references):
            if not pred.strip() or not ref.strip():
                continue
            try:
                s = self._rouge.get_scores(pred, ref)[0]["rouge-l"]
                scores["f"].append(s["f"])
                scores["p"].append(s["p"])
                scores["r"].append(s["r"])
            except Exception:
                continue

        if not scores["f"]:
            return {"f": 0.0, "p": 0.0, "r": 0.0}
        return {
            "f": float(np.mean(scores["f"])) if np else 0.0,
            "p": float(np.mean(scores["p"])) if np else 0.0,
            "r": float(np.mean(scores["r"])) if np else 0.0,
        }

    # ── 3. Exact Match ──
    @staticmethod
    def calc_exact_match(predictions: List[str], references: List[str]) -> float:
        matches = total = 0
        for pred, ref in zip(predictions, references):
            if not ref.strip():
                continue
            total += 1
            p_norm = re.sub(r"[\s\n\r\t，。！？、；：\"'（）【】]+", "", pred.lower())
            r_norm = re.sub(r"[\s\n\r\t，。！？、；：\"'（）【】]+", "", ref.lower())
            if p_norm == r_norm:
                matches += 1
        return matches / total if total > 0 else 0.0

    # ── 4. 结构化字段提取 ──
    @staticmethod
    def extract_risk_level(text: str) -> str:
        patterns = [
            r"[【\[]?风险等级[】\]]?[：:]\s*(高|中|低)",
            r"风险[：:]\s*(高|中|低)",
            r"(高|中|低)风险",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def extract_fraud_type(text: str) -> str:
        patterns = [
            r"[【\[]?诈骗类型[】\]]?[：:]\s*([^\n【\]]+)",
            r"诈骗类型[：:]\s*([^\n]+)",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1).strip()

        type_keywords = {
            "刷单返利": ["刷单", "返利", "垫付"],
            "冒充公检法": ["公检法", "公安局", "检察院", "安全账户"],
            "虚假投资理财": ["投资", "理财", "内幕", "稳赚"],
            "冒充客服退款": ["客服", "退款", "退货", "理赔"],
            "虚假物流赔偿": ["快递", "物流", "赔偿", "丢件"],
            "校园贷": ["校园贷", "注销", "白条", "借呗"],
            "游戏交易": ["游戏", "装备", "账号", "代练"],
            "熟人冒充": ["熟人", "领导", "朋友", "借钱"],
            "AI深度伪造": ["AI", "换脸", "deepfake", "克隆"],
        }
        text_lower = text.lower()
        for fraud_type, keywords in type_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return fraud_type
        return ""

    @staticmethod
    def extract_legal_citations(text: str) -> List[str]:
        pattern = r"(《[^》]+》)[第]?(\d+)[条]?(?:之[一二三四五])?"
        matches = re.findall(pattern, text)
        return [f"{law}第{article}条" for law, article in matches]

    def calc_structured_accuracy(
        self, predictions: List[str], references: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        risk_correct = fraud_type_correct = legal_cite_correct = total = 0
        legal_precisions = []

        for pred, ref in zip(predictions, references):
            if not ref:
                continue
            total += 1

            pred_risk = self.extract_risk_level(pred)
            if pred_risk and pred_risk == ref.get("risk_level", ""):
                risk_correct += 1

            pred_type = self.extract_fraud_type(pred)
            ref_type = ref.get("fraud_type", "")
            if pred_type and ref_type and (pred_type in ref_type or ref_type in pred_type):
                fraud_type_correct += 1

            pred_cites = set(self.extract_legal_citations(pred))
            ref_cites = set(ref.get("legal_citations", []))
            if ref_cites:
                if pred_cites & ref_cites:
                    legal_cite_correct += 1
                if pred_cites:
                    legal_precisions.append(len(pred_cites & ref_cites) / len(pred_cites))

        return {
            "risk_level": {
                "accuracy": risk_correct / total if total > 0 else 0.0,
                "correct": risk_correct, "total": total,
            },
            "fraud_type": {
                "accuracy": fraud_type_correct / total if total > 0 else 0.0,
                "correct": fraud_type_correct, "total": total,
            },
            "legal_citation": {
                "accuracy": legal_cite_correct / total if total > 0 else 0.0,
                "correct": legal_cite_correct, "total": total,
                "avg_precision": float(np.mean(legal_precisions)) if np and legal_precisions else 0.0,
            },
        }

    # ── 5. 安全性检查 ──
    @staticmethod
    def calc_safety_score(
        predictions: List[str], references: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        fatal_errors = total_risk = 0
        for pred, ref in zip(predictions, references):
            ref_risk = ref.get("risk_level", "").lower()
            pred_risk = MetricsCalculator.extract_risk_level(pred).lower()
            if ref_risk in ("高", "中"):
                total_risk += 1
                if pred_risk in ("低", ""):
                    fatal_errors += 1

        return {
            "fatal_error_rate": fatal_errors / total_risk if total_risk > 0 else 0.0,
            "fatal_errors": fatal_errors,
            "total_risk_cases": total_risk,
            "pass": fatal_errors == 0,
        }

    # ── 6. 综合评估 ──
    def evaluate_all(
        self,
        predictions: List[str],
        references_text: List[str],
        references_structured: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        print("Calculating metrics...")
        print("  - BERTScore...")
        bertscore = self.calc_bertscore(predictions, references_text)
        print("  - ROUGE-L...")
        rouge = self.calc_rouge_l(predictions, references_text)
        print("  - Exact Match...")
        exact_match = self.calc_exact_match(predictions, references_text)
        print("  - Structured Accuracy...")
        structured = self.calc_structured_accuracy(predictions, references_structured)
        print("  - Safety Check...")
        safety = self.calc_safety_score(predictions, references_structured)

        return {
            "bertscore": bertscore,
            "rouge_l": rouge,
            "exact_match": exact_match,
            "structured": structured,
            "safety": safety,
        }


if __name__ == "__main__":
    calc = MetricsCalculator()
    preds = [
        "这是冒充公检法诈骗，风险等级：高。根据《中华人民共和国刑法》第二百六十六条...",
        "这是刷单返利诈骗，风险等级：高。",
    ]
    refs_text = [
        "这是冒充公检法诈骗。根据《中华人民共和国刑法》第二百六十六条，诈骗公私财物...",
        "这是刷单返利诈骗。所有要求先垫资后返利的都是诈骗。",
    ]
    refs_struct = [
        {"risk_level": "高", "fraud_type": "冒充公检法", "legal_citations": ["《中华人民共和国刑法》第二百六十六条"]},
        {"risk_level": "高", "fraud_type": "刷单返利", "legal_citations": []},
    ]
    results = calc.evaluate_all(preds, refs_text, refs_struct)
    print(json.dumps(results, ensure_ascii=False, indent=2))
