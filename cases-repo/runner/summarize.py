#!/usr/bin/env python3
"""
summarize.py — 从命令日志生成执行汇总报告

读取 logs/commands.jsonl，按用例 ID 分组，统计每步命令的退出码，
输出 Markdown 汇总报告（含命令审计明细）到 reports/run-<时间戳>.md。

用法：
    python3 summarize.py [--log-dir logs] [--report-dir reports]
"""

import argparse
import glob
import json
import os
from collections import OrderedDict
from datetime import datetime, timezone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从命令日志生成执行汇总报告")
    parser.add_argument("--log-dir", default="logs", help="日志目录（默认 ./logs）")
    parser.add_argument("--report-dir", default="reports", help="报告输出目录（默认 ./reports）")
    parser.add_argument(
        "--only-failed",
        action="store_true",
        help="只输出失败的用例（默认输出全部）",
    )
    return parser.parse_args()


def load_records(log_dir: str) -> list[dict]:
    records: list[dict] = []
    for path in sorted(glob.glob(os.path.join(log_dir, "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def group_by_case(records: list[dict]) -> "OrderedDict[str, list[dict]]":
    grouped: "OrderedDict[str, list[dict]]" = OrderedDict()
    for rec in records:
        grouped.setdefault(rec.get("case", "UNKNOWN"), []).append(rec)
    return grouped


def case_verdict(steps: list[dict]) -> str:
    if not steps:
        return "EMPTY"
    return "FAIL" if any(s.get("exit_code") != 0 for s in steps) else "PASS"


def main() -> int:
    args = parse_args()
    records = load_records(args.log_dir)
    if not records:
        print(f"日志目录 {args.log_dir} 中没有找到命令记录。")
        return 1

    grouped = group_by_case(records)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(args.report_dir, exist_ok=True)
    out_path = os.path.join(args.report_dir, f"run-{ts}.md")

    lines: list[str] = []
    lines.append(f"# Playwright 用例执行报告（{ts}）")
    lines.append("")
    lines.append(f"共执行 {len(grouped)} 个用例，{len(records)} 条命令。")
    lines.append("")

    # 汇总表
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 用例 | 结果 | 步骤数 | 失败步骤 |")
    lines.append("| --- | --- | --- | --- |")
    for case, steps in grouped.items():
        verdict = case_verdict(steps)
        failed = sum(1 for s in steps if s.get("exit_code") != 0)
        if args.only_failed and verdict != "FAIL":
            continue
        lines.append(f"| {case} | {verdict} | {len(steps)} | {failed} |")
    lines.append("")

    # 命令审计明细
    lines.append("## 命令审计日志")
    lines.append("")
    for case, steps in grouped.items():
        verdict = case_verdict(steps)
        if args.only_failed and verdict != "FAIL":
            continue
        lines.append(f"### {case} — {verdict}")
        lines.append("")
        for i, s in enumerate(steps, 1):
            status = "✅" if s.get("exit_code") == 0 else "❌"
            argv = " ".join(s.get("argv", []))
            lines.append(f"{i}. {status} `{argv}`")
            lines.append(
                f"   - 退出码 {s.get('exit_code')} · 耗时 {s.get('duration_ms')}ms"
                f" · 会话 {s.get('session') or '-'} · {s.get('ts')}"
            )
            if s.get("stderr_tail"):
                lines.append(f"   - stderr: `{s['stderr_tail'][-200:]}`")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"报告已写入: {out_path}")
    print(f"汇总: {len(grouped)} 用例, {sum(1 for _, s in grouped.items() if case_verdict(s) == 'FAIL')} 失败")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
