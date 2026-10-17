#!/usr/bin/env python3
"""
pw-cli-log.py — playwright-cli 命令日志包装器

作用：所有 playwright-cli 调用都通过本脚本执行，自动把每条命令
（时间戳 / 用例 / 会话 / 完整参数 / 退出码 / 输出摘要 / 耗时）
追加写入 JSONL 日志，实现"自然语言步骤 ↔ 实际命令"的完整审计链。

用法：
    python3 pw-cli-log.py [--case TC001] [--log-dir <dir>] -- playwright-cli <参数...>

示例：
    python3 pw-cli-log.py --case TC001 -- playwright-cli -s=tc001 open https://demo.playwright.dev/todomvc
    python3 pw-cli-log.py --case TC001 -- playwright-cli -s=tc001 fill e5 "Buy groceries"

说明：
    - "--" 之后的内容为真正要执行的命令（通常以 playwright-cli 开头）
    - 若未安装 playwright-cli，脚本报错并提示安装命令
    - 日志默认写入 ./logs/commands.jsonl，可用 --log-dir 覆盖
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="playwright-cli 命令日志包装器（自动记录每条命令到 JSONL）"
    )
    parser.add_argument("--case", default="UNKNOWN", help="用例 ID，如 TC001")
    parser.add_argument("--log-dir", default="logs", help="日志目录（默认 ./logs）")
    parser.add_argument(
        "--max-tail",
        type=int,
        default=500,
        help="stdout/stderr 摘要截取的最大字符数（默认 500）",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="-- 之后的实际命令，如: -- playwright-cli -s=tc001 open <url>",
    )
    return parser.parse_args()


def extract_session(argv: list[str]) -> str:
    """从参数中提取 -s=<name> 会话名，找不到返回空串。"""
    for arg in argv:
        if arg.startswith("-s="):
            return arg[3:]
        if arg.startswith("--session="):
            return arg[len("--session="):]
    return ""


def append_log(log_path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    raw = list(args.command)

    # argparse 的 REMAINDER 会把 "--" 分隔符本身也收进来，去掉它
    while raw and raw[0] == "--":
        raw.pop(0)

    if not raw:
        print("错误：-- 之后未提供要执行的命令。", file=sys.stderr)
        print("示例: python3 pw-cli-log.py --case TC001 -- playwright-cli -s=tc001 open <url>", file=sys.stderr)
        return 2

    argv = raw
    cli = shutil.which("playwright-cli")
    if not cli:
        print(
            "错误：未找到 playwright-cli。请先安装：\n"
            "    npm install -g @playwright/cli@latest",
            file=sys.stderr,
        )
        return 127

    start = time.perf_counter()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "case": args.case,
            "session": extract_session(argv),
            "argv": argv,
            "exit_code": -1,
            "timed_out": True,
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }
        append_log(os.path.join(args.log_dir, "commands.jsonl"), record)
        print("错误：命令执行超时（600s）", file=sys.stderr)
        return 124
    except FileNotFoundError:
        print(f"错误：命令不存在: {argv[0]}", file=sys.stderr)
        return 127

    duration_ms = int((time.perf_counter() - start) * 1000)
    tail = args.max_tail

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "session": extract_session(argv),
        "argv": argv,
        "exit_code": proc.returncode,
        "timed_out": False,
        "duration_ms": duration_ms,
        "stdout_tail": proc.stdout[-tail:],
        "stderr_tail": proc.stderr[-tail:],
    }
    append_log(os.path.join(args.log_dir, "commands.jsonl"), record)

    # 原样透传输出，保证 agent 能看到快照/结果
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
