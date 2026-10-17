import argparse
import html
import json
from pathlib import Path


def render_html(run_data):
    cases = run_data["cases"]
    pass_count = sum(case["status"] == "PASS" for case in cases)
    fail_count = len(cases) - pass_count

    lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>测试执行报告 | {html.escape(str(run_data['run_ts']))}</title>",
        "<style>",
        ":root{color-scheme:light;--ink:#1f2937;--muted:#64748b;--line:#e2e8f0;--bg:#f8fafc;--pass:#15803d;--fail:#b91c1c;}",
        "body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}",
        "main{max-width:1440px;margin:32px auto;padding:0 24px}",
        "h1{margin-bottom:4px}h2{margin-top:32px}",
        ".meta,.muted{color:var(--muted)}",
        ".summary{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}",
        ".card{background:white;border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:100px}",
        ".card strong{display:block;font-size:22px}.pass{color:var(--pass)}.fail{color:var(--fail)}",
        ".table-wrap{overflow-x:auto;background:white;border:1px solid var(--line);border-radius:10px}",
        "table{width:100%;border-collapse:collapse;min-width:900px}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid var(--line)}",
        "th{background:#f1f5f9;white-space:nowrap}tr:last-child td{border-bottom:0}",
        "td.command{max-width:560px}code{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}",
        ".screenshot-thumb{display:inline-block;line-height:0}.screenshot-thumb img{display:block;width:140px;max-height:96px;object-fit:cover;border:1px solid var(--line);border-radius:5px;cursor:zoom-in}",
        ".lightbox{display:none}.lightbox:target{display:flex;position:fixed;inset:0;z-index:10;align-items:center;justify-content:center;padding:24px;background:rgba(15,23,42,.88);cursor:zoom-out}",
        ".lightbox img{display:block;max-width:96vw;max-height:94vh;object-fit:contain;background:white;box-shadow:0 12px 48px rgba(0,0,0,.4)}",
        "a{color:#0369a1}a:hover{color:#0c4a6e}",
        "@media(max-width:640px){main{margin:20px auto;padding:0 12px}}",
        "</style>",
        "</head>",
        "<body>",
        '<main id="report-top">',
        f"<h1>测试执行报告 | {html.escape(str(run_data['run_ts']))}</h1>",
        f"<p class=\"meta\">运行目录：{html.escape(str(run_data['run_dir']))}<br>截图目录：{html.escape(str(run_data['attachment_dir']))}</p>",
        '<div class="summary">',
        f'<div class="card">用例总数<strong>{len(cases)}</strong></div>',
        f'<div class="card pass">PASS<strong>{pass_count}</strong></div>',
        f'<div class="card fail">FAIL<strong>{fail_count}</strong></div>',
        "</div>",
    ]

    for case in cases:
        case_id = html.escape(str(case["case_id"]))
        status = html.escape(str(case["status"]))
        status_class = "pass" if case["status"] == "PASS" else "fail"
        lines.extend([
            f'<section><h2>{case_id} | {html.escape(str(case["title"]))} <span class="{status_class}">【{status}】</span></h2>',
            '<div class="table-wrap"><table>',
            "<thead><tr><th>步骤序号</th><th>原始自然语言步骤</th><th>执行命令</th><th>结果</th><th>截图</th></tr></thead><tbody>",
        ])
        lightboxes = []
        for record in case["step_records"]:
            if record.get("status") == "SKIPPED":
                result = "SKIP"
                result_class = "muted"
            elif record.get("exit_code") == 0:
                result = "PASS"
                result_class = "pass"
            else:
                result = "FAIL"
                result_class = "fail"
            screenshot_name = f"{case['case_id']}-step{record['step_idx']:02d}.png"
            screenshot_path = Path(run_data["attachment_dir"]) / screenshot_name
            if screenshot_path.is_file():
                screenshot_id = html.escape(
                    f"lightbox-{case['case_id']}-step{record['step_idx']:02d}",
                    quote=True,
                )
                screenshot_href = html.escape(
                    f"attachment/{screenshot_name}",
                    quote=True,
                )
                screenshot_cell = (
                    f'<a class="screenshot-thumb" href="#{screenshot_id}" '
                    f'aria-label="放大查看步骤 {record["step_idx"]} 截图">'
                    f'<img src="{screenshot_href}" alt="步骤 {record["step_idx"]} 截图"></a>'
                )
                lightboxes.append(
                    f'<a class="lightbox" id="{screenshot_id}" href="#report-top" '
                    f'aria-label="关闭放大截图"><img src="{screenshot_href}" '
                    f'alt="步骤 {record["step_idx"]} 截图原图"></a>'
                )
            else:
                screenshot_cell = '<span class="muted">无截图</span>'
            lines.append(
                "<tr>"
                f"<td>{record['step_idx']}</td>"
                f"<td>{html.escape(str(record['nl']))}</td>"
                f'<td class="command"><code>{html.escape(str(record["command"]))}</code></td>'
                f'<td class="{result_class}">{result}</td>'
                f"<td>{screenshot_cell}</td>"
                "</tr>"
            )
        lines.extend(["</tbody></table></div></section>"])
        lines.extend(lightboxes)

    lines.extend(["</main>", "</body>", "</html>"])
    return "\n".join(lines) + "\n"


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
            if rec.get("status") == "SKIPPED":
                res = "⏭ SKIP"
            else:
                res = "✅ PASS" if rec.get("exit_code") == 0 else "❌ FAIL"
            screenshot_name = f"{case['case_id']}-step{rec['step_idx']:02d}.png"
            screenshot_link = f"[查看截图](attachment/{screenshot_name})"
            md_lines.append(f"|{rec['step_idx']}|{nl}|`{cmd}`|{res}|{screenshot_link}|")
        md_lines.append("")

    md_content = "\n".join(md_lines)
    md_path = run_dir / "report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    html_path = run_dir / "report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(run_data))

    print(f"✅ Markdown报告生成完成：{md_path}")
    print(f"✅ HTML报告生成完成：{html_path}")


if __name__ == "__main__":
    main()
