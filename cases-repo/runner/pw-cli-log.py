import argparse
import json
import time
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--nl", required=True, help="原始自然语言步骤文本")
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--optional", default="false")
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    start = time.time()
    cmd = args.rest
    # 剔除--分隔符
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    duration = round(time.time() - start, 3)

    log_record = {
        "ts": time.time(),
        "case_id": args.case,
        "nl_step": args.nl,
        "cmd": cmd,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_sec": duration,
        "is_optional": args.optional.lower() == "true"
    }

    # 追加写入审计日志
    with open(args.log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_record, ensure_ascii=False) + "\n")

    exit(proc.returncode)


if __name__ == "__main__":
    main()
