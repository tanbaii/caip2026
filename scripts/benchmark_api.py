from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class BenchResult:
    endpoint: str
    latency_ms: float
    ok: bool
    payload: dict[str, Any] | None
    status_code: int


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * p
    low = int(rank)
    high = min(low + 1, len(values) - 1)
    if low == high:
        return values[low]
    weight = rank - low
    return values[low] * (1 - weight) + values[high] * weight


async def post_json(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    endpoint: str,
    payload: dict[str, Any],
) -> BenchResult:
    async with semaphore:
        start = time.perf_counter()
        try:
            response = await client.post(endpoint, json=payload)
            latency_ms = (time.perf_counter() - start) * 1000
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else None
            return BenchResult(
                endpoint=endpoint,
                latency_ms=latency_ms,
                ok=response.status_code == 200,
                payload=body,
                status_code=response.status_code,
            )
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000
            return BenchResult(
                endpoint=endpoint,
                latency_ms=latency_ms,
                ok=False,
                payload=None,
                status_code=0,
            )


async def run_benchmark(base_url: str, rounds: int, concurrency: int) -> None:
    timeout = httpx.Timeout(10.0, connect=5.0)
    semaphore = asyncio.Semaphore(concurrency)

    chat_texts = [
        "有人让我先垫付刷单，说完成后返利。",
        "陌生人说我涉嫌洗钱，要我转到安全账户。",
        "这个理财群老师说稳赚不赔，靠谱吗？",
        "我想了解校园贷诈骗怎么防。",
    ]
    report_urls = [
        "http://xn--secure-bank-5k9f.top/login@notice",
        "http://192.168.1.7/reset",
        "https://example.com/safe",
        "http://bit.ly/fake-bonus",
    ]

    tasks: list[asyncio.Task[BenchResult]] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        for i in range(rounds):
            user = f"bench_user_{i}"
            chat_payload = {
                "user_id": user,
                "message": chat_texts[i % len(chat_texts)],
                "channel": "web",
                "emotion": "anxious" if i % 2 == 0 else "neutral",
                "user_profile": {
                    "role": "student" if i % 3 == 0 else "general",
                    "risk_tolerance": "medium",
                },
            }
            report_payload = {
                "user_id": user,
                "url": report_urls[i % len(report_urls)],
                "content": "点击领取返利，先转账再提现" if i % 2 == 0 else "普通通知信息",
                "channel": "web",
            }

            tasks.append(asyncio.create_task(post_json(client, semaphore, "/chat", chat_payload)))
            tasks.append(asyncio.create_task(post_json(client, semaphore, "/report", report_payload)))

        results = await asyncio.gather(*tasks)

    chat_results = [r for r in results if r.endpoint == "/chat"]
    report_results = [r for r in results if r.endpoint == "/report"]

    def summarize(group: list[BenchResult]) -> dict[str, Any]:
        latencies = sorted([item.latency_ms for item in group])
        ok_count = sum(1 for item in group if item.ok)
        total = len(group)
        failed = total - ok_count

        summary: dict[str, Any] = {
            "total": total,
            "ok": ok_count,
            "failed": failed,
            "avg_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "p50_ms": round(percentile(latencies, 0.50), 2),
            "p95_ms": round(percentile(latencies, 0.95), 2),
            "max_ms": round(max(latencies), 2) if latencies else 0.0,
        }
        return summary

    chat_summary = summarize(chat_results)
    report_summary = summarize(report_results)

    high_risk_hits = 0
    for item in chat_results:
        if item.payload and item.payload.get("risk_level") in {"high", "critical"}:
            high_risk_hits += 1

    suspicious_hits = 0
    for item in report_results:
        if item.payload and item.payload.get("verdict") in {"suspicious", "high_risk"}:
            suspicious_hits += 1

    chat_hit_rate = round((high_risk_hits / len(chat_results)) * 100, 2) if chat_results else 0.0
    report_hit_rate = round((suspicious_hits / len(report_results)) * 100, 2) if report_results else 0.0

    print("=== Benchmark Summary ===")
    print(f"Base URL: {base_url}")
    print(f"Rounds: {rounds}, Concurrency: {concurrency}")
    print("\n[Chat]")
    print(chat_summary)
    print(f"high_or_critical_hit_rate: {chat_hit_rate}%")
    print("\n[Report]")
    print(report_summary)
    print(f"suspicious_or_high_risk_hit_rate: {report_hit_rate}%")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark anti-fraud API endpoints.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--rounds", type=int, default=80, help="Number of chat/report request pairs")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent request limit")
    args = parser.parse_args()

    await run_benchmark(
        base_url=args.base_url,
        rounds=max(1, args.rounds),
        concurrency=max(1, args.concurrency),
    )


if __name__ == "__main__":
    asyncio.run(main())
