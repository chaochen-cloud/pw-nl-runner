import argparse
import json
import shlex
import time
import subprocess
from pathlib import Path


def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_command_argv(command):
    if isinstance(command, list) and all(isinstance(arg, str) for arg in command):
        if not command:
            raise ValueError("Plan step command must not be empty")
        return command
    if isinstance(command, str):
        argv = shlex.split(command)
        if not argv:
            raise ValueError("Plan step command must not be empty")
        return argv
    raise ValueError("Plan step command must be a string or an array of strings")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="config.json path")
    args = parser.parse_args()

    # 工程根目录
    root = Path(__file__).parent.parent.parent
    cfg = load_config(args.config)

    # 每次执行新建独立时间戳运行目录
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_dir = root / "reports" / f"run-{ts}"
    attachment_dir = run_dir / "attachment"
    run_dir.mkdir(parents=True, exist_ok=False)
    attachment_dir.mkdir(parents=True, exist_ok=False)

    log_file = root / "logs" / "commands.jsonl"
    Path(log_file).parent.mkdir(exist_ok=True)

    plan_dir = root / cfg["plan_dir"]
    case_plans = sorted(list(plan_dir.glob("TC*.json")), key=lambda x: x.stem)

    run_summary = {
        "run_ts": ts,
        "run_dir": str(run_dir),
        "attachment_dir": str(attachment_dir),
        "cases": []
    }

    for plan_path in case_plans:
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        case_id = plan["case_id"]
        case_title = plan["title"]
        steps = plan["steps"]

        case_result = {
            "case_id": case_id,
            "title": case_title,
            "status": "PASS",
            "step_records": []
        }
        case_failed = False

        for step_idx, step in enumerate(steps):
            nl_text = step["nl"]
            command_argv = get_command_argv(step["command"])
            command_display = shlex.join(command_argv)

            if case_failed:
                record = {
                    "case_id": case_id,
                    "step_idx": step_idx,
                    "nl": nl_text,
                    "command": command_display,
                    "status": "SKIPPED",
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "",
                    "timestamp": time.time()
                }
                case_result["step_records"].append(record)
                continue

            # 调用日志包装器执行playwright命令
            cmd_wrapper = [
                "python3", str(root / "cases-repo/runner/pw-cli-log.py"),
                "--case", case_id,
                "--nl", nl_text,
                "--log-file", str(log_file),
                "--"
            ] + command_argv

            start_t = time.time()
            proc = subprocess.run(cmd_wrapper, capture_output=True, text=True)
            end_t = time.time()

            exit_code = proc.returncode
            record = {
                "case_id": case_id,
                "step_idx": step_idx,
                "nl": nl_text,
                "command": command_display,
                "exit_code": exit_code,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "duration": round(end_t - start_t, 3),
                "timestamp": time.time()
            }
            case_result["step_records"].append(record)

            # 标记用例失败
            if exit_code != 0:
                case_failed = True
                case_result["status"] = "FAIL"

            # 【强制截图】每一步执行完毕，无论成败，截图存入本次run的attachment
            screenshot_name = f"{case_id}-step{step_idx:02d}.png"
            screenshot_path = str(attachment_dir / screenshot_name)
            screenshot_cmd = [
                "python3", str(root / "cases-repo/runner/pw-cli-log.py"),
                "--case", case_id,
                "--nl", f"截图留证：{nl_text}",
                "--optional", "true",
                "--log-file", str(log_file),
                "--",
                "playwright-cli", "-s", plan["session"],
                "screenshot", "--filename", screenshot_path
            ]
            # 截图命令为可选，截图失败不中断用例执行
            subprocess.run(screenshot_cmd, capture_output=True, text=True)

        run_summary["cases"].append(case_result)

    # 写入机器可读报告到本次run目录
    with open(run_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2, ensure_ascii=False)

    # ✅ 自动调用summarize生成report.md，无需手动执行
    summarize_cmd = [
        "python3", str(root / "cases-repo/runner/summarize.py"),
        "--run-dir", str(run_dir)
    ]
    subprocess.run(summarize_cmd, check=True)

    print(f"\n✅ 全部用例执行完成！")
    print(f"📁 报告目录：{run_dir}")
    print(f"🖼️ 截图附件目录：{attachment_dir}")
    print(f"📄 可视化报告：{run_dir}/report.md")
    print(f"🌐 HTML报告：{run_dir}/report.html")


if __name__ == "__main__":
    main()
