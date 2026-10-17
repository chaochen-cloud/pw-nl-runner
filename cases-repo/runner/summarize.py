import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, help="单次运行目录，如 reports/run-20261017_221030")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    report_json = run_dir / "report.json"

    with open(report_json, "r", encoding="utf-8") as f:
        run_data = json.load(f)

    md_lines = []
    md_lines.append(f"# 测试执行报告 | {run_data['run_ts']}")
    md_lines.append(f"> 运行根目录：{run_data['run_dir']}")
    md_lines.append(f"> 截图附件目录：{run_data['attachment_dir']}")
    md_lines.append("")

    total = len(run_data["cases"])
    pass_cnt = sum(1 for c in run_data["cases"] if c["status"] == "PASS")
    fail_cnt = total - pass_cnt
    md_lines.append(f"## 汇总统计：共{total}个用例，✅ PASS:{pass_cnt} | ❌ FAIL:{fail_cnt}")
    md_lines.append("")

    for case in run_data["cases"]:
        md_lines.append(f"## {case['case_id']} | {case['title']} | 【{case['status']}】")
        md_lines.append("|步骤序号|原始自然语言步骤|执行命令|执行结果|截图|")
        md_lines.append("|---|---|---|---|---|")
        for rec in case["step_records"]:
            nl = rec["nl"].replace("|", "\\|")
            cmd = rec["command"].replace("|", "\\|")
            if rec["status"] == "SKIPPED":
                res = "⏭ SKIP"
            else:
                res = "✅ PASS" if rec["exit_code"] == 0 else "❌ FAIL"
            screenshot_name = f"{case['case_id']}-step{rec['step_idx']:02d}.png"
            screenshot_link = f"![截图](attachment/{screenshot_name})"
            md_lines.append(f"|{rec['step_idx']}|{nl}|`{cmd}`|{res}|{screenshot_link}|")
        md_lines.append("")

    md_content = "\n".join(md_lines)
    md_path = run_dir / "report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ Markdown报告生成完成：{md_path}")


if __name__ == "__main__":
    main()
