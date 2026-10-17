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


def select_case_plans(plan_dir, case_ids):
    available_plans = {
        path.stem: path
        for path in sorted(plan_dir.glob("TC*.json"), key=lambda item: item.stem)
    }
    if not case_ids:
        return list(available_plans.values())

    missing = [case_id for case_id in case_ids if case_id not in available_plans]
    if missing:
        raise ValueError(f"No plan found for case(s): {', '.join(missing)}")
    return [available_plans[case_id] for case_id in case_ids]


def prepare_run(root, run_dir_arg):
    reports_dir = (root / "reports").resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    if run_dir_arg is None:
        run_ts = time.strftime("%Y%m%d_%H%M%S")
        run_dir = reports_dir / f"run-{run_ts}"
        run_dir.mkdir(parents=True, exist_ok=False)
        attachment_dir = run_dir / "attachment"
        attachment_dir.mkdir()
        run_summary = {
            "run_ts": run_ts,
            "run_dir": str(run_dir),
            "attachment_dir": str(attachment_dir),
            "cases": [],
        }
        return run_dir, attachment_dir, run_summary

    run_dir = Path(run_dir_arg)
    if not run_dir.is_absolute():
        run_dir = root / run_dir
    run_dir = run_dir.resolve()
    try:
        run_dir.relative_to(reports_dir)
    except ValueError as exc:
        raise ValueError("Run directory must be inside the reports directory") from exc

    report_path = run_dir / "report.json"
    attachment_dir = run_dir / "attachment"
    if not run_dir.is_dir() or not report_path.is_file() or not attachment_dir.is_dir():
        raise ValueError(f"Cannot append to incomplete run directory: {run_dir}")

    with report_path.open("r", encoding="utf-8") as report_file:
        run_summary = json.load(report_file)
    if run_summary.get("run_dir") != str(run_dir):
        raise ValueError(f"Run report does not belong to directory: {run_dir}")
    return run_dir, attachment_dir, run_summary


def get_command_session(command, default_session):
    for index, arg in enumerate(command):
        if arg.startswith("-s="):
            return arg.partition("=")[2]
        if arg == "-s" and index + 1 < len(command):
            return command[index + 1]
    return default_session


def save_run(root, run_dir, run_summary):
    with open(run_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2, ensure_ascii=False)

    summarize_cmd = [
        "python3", str(root / "cases-repo/runner/summarize.py"),
        "--run-dir", str(run_dir)
    ]
    subprocess.run(summarize_cmd, check=True)


def run_live_step(root, args, log_file):
    if len(args.case_ids or []) != 1:
        raise ValueError("--live-step requires exactly one --case")
    if (
        not args.title
        or not args.session
        or args.nl is None
        or args.command_json is None
    ):
        raise ValueError(
            "--live-step requires --title, --session, --nl and --command-json"
        )

    try:
        command_argv = get_command_argv(json.loads(args.command_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid --command-json: {exc}") from exc
    if Path(command_argv[0]).name != "playwright-cli":
        raise ValueError("--live-step command must invoke playwright-cli")
    command_session = get_command_session(command_argv, "")
    if not command_session:
        raise ValueError("--live-step command must specify an isolated -s session")

    run_dir, attachment_dir, run_summary = prepare_run(root, args.run_dir)
    case_id = args.case_ids[0]
    case_result = next(
        (item for item in run_summary["cases"] if item["case_id"] == case_id),
        None,
    )
    if case_result is None:
        case_result = {
            "case_id": case_id,
            "title": args.title,
            "session": args.session,
            "status": "RUNNING",
            "execution_mode": "live",
            "step_records": [],
        }
        run_summary["cases"].append(case_result)
    elif (
        case_result.get("status") != "RUNNING"
        or case_result.get("execution_mode") != "live"
        or case_result.get("title") != args.title
        or case_result.get("session") != args.session
    ):
        raise ValueError(f"Case {case_id} is not an appendable live case")

    if (
        args.phase == "execute"
        and case_result["step_records"]
        and case_result["step_records"][-1].get("phase") == "execute"
    ):
        raise ValueError(
            f"Observe the current page before generating the next action for {case_id}"
        )

    step_idx = len(case_result["step_records"])
    command_display = shlex.join(command_argv)
    cmd_wrapper = [
        "python3", str(root / "cases-repo/runner/pw-cli-log.py"),
        "--case", case_id,
        "--nl", args.nl,
        "--phase", args.phase,
        "--log-file", str(log_file),
        "--",
    ] + command_argv

    start_t = time.time()
    proc = subprocess.run(cmd_wrapper, capture_output=True, text=True)
    end_t = time.time()
    case_result["step_records"].append({
        "case_id": case_id,
        "step_idx": step_idx,
        "nl": args.nl,
        "phase": args.phase,
        "command": command_display,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration": round(end_t - start_t, 3),
        "timestamp": time.time(),
    })

    if proc.returncode != 0:
        case_result["status"] = "FAIL"

    screenshot_path = str(attachment_dir / f"{case_id}-step{step_idx:02d}.png")
    screenshot_cmd = [
        "python3", str(root / "cases-repo/runner/pw-cli-log.py"),
        "--case", case_id,
        "--nl", args.nl,
        "--phase", "screenshot",
        "--optional", "true",
        "--log-file", str(log_file),
        "--",
        "playwright-cli", f"-s={command_session}",
        "screenshot", "--filename", screenshot_path,
    ]
    subprocess.run(screenshot_cmd, capture_output=True, text=True)

    save_run(root, run_dir, run_summary)
    print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="")
    print(f"\n报告目录：{run_dir}")
    print(f"用例状态：{case_result['status']}")


def finish_live_case(root, args):
    if len(args.case_ids or []) != 1:
        raise ValueError("--finish-live requires exactly one --case")
    if not args.run_dir:
        raise ValueError("--finish-live requires --run-dir")

    run_dir, _, run_summary = prepare_run(root, args.run_dir)
    case_id = args.case_ids[0]
    case_result = next(
        (item for item in run_summary["cases"] if item["case_id"] == case_id),
        None,
    )
    if case_result is None or case_result.get("execution_mode") != "live":
        raise ValueError(f"No live case {case_id} found in {run_dir}")
    if case_result.get("status") != "RUNNING":
        raise ValueError(
            f"Live case {case_id} cannot be finished from status "
            f"{case_result.get('status')}"
        )

    case_result["status"] = "PASS"
    save_run(root, run_dir, run_summary)
    print(f"报告目录：{run_dir}")
    print(f"用例状态：{case_result['status']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="config.json path")
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="run only this case plan; may be repeated for multiple case IDs",
    )
    parser.add_argument(
        "--run-dir",
        help="append this case invocation to an existing report run directory",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--live-step",
        action="store_true",
        help="execute one observed/generated browser command and append it to a live case",
    )
    mode_group.add_argument(
        "--finish-live",
        action="store_true",
        help="mark an in-progress live case as passed",
    )
    parser.add_argument("--title", help="case title for --live-step")
    parser.add_argument("--session", help="primary browser session for --live-step")
    parser.add_argument("--nl", help="original natural-language step for --live-step")
    parser.add_argument("--phase", choices=("observe", "execute"), default="execute")
    parser.add_argument(
        "--command-json",
        help="JSON argv array for one playwright-cli command in --live-step mode",
    )
    args = parser.parse_args()

    # 工程根目录
    root = Path(__file__).parent.parent.parent
    cfg = load_config(args.config)

    plan_dir = root / cfg["plan_dir"]
    log_file = root / "logs" / "commands.jsonl"
    Path(log_file).parent.mkdir(exist_ok=True)
    if args.live_step or args.finish_live:
        try:
            if args.live_step:
                run_live_step(root, args, log_file)
            else:
                finish_live_case(root, args)
        except ValueError as exc:
            parser.error(str(exc))
        return

    try:
        case_plans = select_case_plans(plan_dir, args.case_ids)
        if args.run_dir and (not args.case_ids or len(args.case_ids) != 1):
            raise ValueError("--run-dir requires exactly one --case")
        run_dir, attachment_dir, run_summary = prepare_run(root, args.run_dir)
    except ValueError as exc:
        parser.error(str(exc))

    for plan_path in case_plans:
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        case_id = plan["case_id"]
        if case_id != plan_path.stem:
            raise ValueError(
                f"Plan filename {plan_path.name} does not match case_id {case_id}"
            )
        if args.case_ids and case_id not in args.case_ids:
            raise ValueError(
                f"Selected plan {plan_path.name} does not match requested case ID"
            )
        if any(existing["case_id"] == case_id for existing in run_summary["cases"]):
            raise ValueError(
                f"Case {case_id} is already present in report run {run_dir}"
            )
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
                "phase": "execute",
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
                "--phase", "screenshot",
                "--optional", "true",
                "--log-file", str(log_file),
                "--",
                "playwright-cli", "-s", plan["session"],
                "screenshot", "--filename", screenshot_path
            ]
            # 截图命令为可选，截图失败不中断用例执行
            subprocess.run(screenshot_cmd, capture_output=True, text=True)

        run_summary["cases"].append(case_result)

    save_run(root, run_dir, run_summary)

    print(f"\n✅ 本批用例执行完成！")
    print(f"📁 报告目录：{run_dir}")
    print(f"🖼️ 截图附件目录：{attachment_dir}")
    print(f"📄 可视化报告：{run_dir}/report.md")
    print(f"🌐 HTML报告：{run_dir}/report.html")


if __name__ == "__main__":
    main()
