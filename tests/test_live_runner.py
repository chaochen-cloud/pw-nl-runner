import contextlib
import io
import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNNER = runpy.run_path(str(ROOT / "runner/run-all.py"))
SUMMARIZER = runpy.run_path(str(ROOT / "runner/summarize.py"))


class LiveRunnerTests(unittest.TestCase):
    def test_command_session_supports_both_cli_spellings(self):
        get_session = RUNNER["get_command_session"]

        self.assertEqual(
            get_session(["playwright-cli", "-s=tc001", "snapshot"], "default"),
            "tc001",
        )
        self.assertEqual(
            get_session(["playwright-cli", "-s", "tc002", "snapshot"], "default"),
            "tc002",
        )
        self.assertEqual(
            get_session(["playwright-cli", "snapshot"], "default"),
            "default",
        )

    def test_log_wrapper_records_phase_and_command(self):
        log_wrapper = ROOT / "runner/pw-cli-log.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "commands.jsonl"
            subprocess.run(
                [
                    sys.executable,
                    str(log_wrapper),
                    "--case",
                    "TC012",
                    "--nl",
                    "Observe the page",
                    "--phase",
                    "observe",
                    "--log-file",
                    str(log_path),
                    "--",
                    sys.executable,
                    "-c",
                    "print('snapshot output')",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            record = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(record["phase"], "observe")
            self.assertEqual(record["nl_step"], "Observe the page")
            self.assertEqual(record["stdout"], "snapshot output\n")
            self.assertEqual(record["exit_code"], 0)
            self.assertIn(sys.executable, record["cmd"])

    def test_live_report_marks_in_progress_without_counting_as_failure(self):
        source_content = "---\nid: TC001\n---\n## <script>alert('x')</script>\n"
        run_data = {
            "run_ts": "test",
            "run_dir": "/tmp/run",
            "attachment_dir": "/tmp/run/attachment",
            "cases": [
                {
                    "case_id": "TC001",
                    "title": "Live case",
                    "status": "RUNNING",
                    "source_content": source_content,
                    "step_records": [
                        {
                            "step_idx": 0,
                            "phase": "observe",
                            "nl": "Open the page",
                            "command": "playwright-cli -s=tc001 snapshot",
                            "exit_code": 0,
                        }
                    ],
                }
            ],
        }

        html_report = SUMMARIZER["render_html"](run_data)

        self.assertIn("进行中<strong>1</strong>", html_report)
        self.assertIn("【RUNNING】", html_report)
        self.assertIn("页面观察", html_report)
        self.assertIn("FAIL<strong>0</strong>", html_report)
        self.assertIn("<details class=\"source-case\">", html_report)
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", html_report)
        self.assertNotIn("<script>alert('x')</script>", html_report)
        markdown_report = SUMMARIZER["render_markdown"](run_data)
        self.assertIn("<summary>原始用例内容</summary>", markdown_report)
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", markdown_report)

    def test_html_screenshot_lightbox_has_reliable_close_controls_and_preserves_scroll(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            attachment_dir = Path(temp_dir) / "attachment"
            attachment_dir.mkdir()
            (attachment_dir / "TC001-step01.png").touch()
            run_data = {
                "run_ts": "test",
                "run_dir": temp_dir,
                "attachment_dir": str(attachment_dir),
                "cases": [
                    {
                        "case_id": "TC001",
                        "title": "Screenshot case",
                        "status": "PASS",
                        "source_content": "",
                        "step_records": [
                            {
                                "step_idx": 1,
                                "phase": "execute",
                                "nl": "Open page",
                                "command": "playwright-cli open",
                                "exit_code": 0,
                            }
                        ],
                    }
                ],
            }

            html_report = SUMMARIZER["render_html"](run_data)

        self.assertIn(".lightbox.open{display:flex", html_report)
        self.assertIn('class="lightbox-close" type="button"', html_report)
        self.assertIn("event.key === 'Escape'", html_report)
        self.assertIn("event.target === activeLightbox", html_report)
        self.assertIn("screenshotScrollY = window.scrollY", html_report)
        self.assertIn("window.scrollTo(0, screenshotScrollY)", html_report)
        self.assertNotIn(".lightbox:target", html_report)
        self.assertNotIn("history.replaceState", html_report)

    def test_close_case_sessions_closes_each_distinct_browser_session(self):
        close_case_sessions = RUNNER["close_case_sessions"]
        case_result = {
            "case_id": "TC013",
            "sessions": ["tc013", "tc013-api"],
            "step_records": [],
            "status": "RUNNING",
        }
        results = [
            SimpleNamespace(returncode=0, stdout="Closed tc013", stderr=""),
            SimpleNamespace(returncode=0, stdout="Closed tc013-api", stderr=""),
        ]

        with patch("subprocess.run", side_effect=results) as commands:
            with contextlib.redirect_stdout(io.StringIO()):
                close_case_sessions(ROOT, case_result, ROOT / "logs/commands.jsonl")

        self.assertEqual(
            [record["phase"] for record in case_result["step_records"]],
            ["cleanup", "cleanup"],
        )
        close_argv = [
            call.args[0][-3:]
            for call in commands.call_args_list
        ]
        self.assertEqual(
            close_argv,
            [
                ["playwright-cli", "-s=tc013", "close"],
                ["playwright-cli", "-s=tc013-api", "close"],
            ],
        )

    def test_live_steps_append_to_one_case_and_finish(self):
        run_live_step = RUNNER["run_live_step"]
        finish_live_case = RUNNER["finish_live_case"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "reports").mkdir()
            cases_dir = root / "cases-repo" / "cases"
            cases_dir.mkdir(parents=True)
            source_content = "---\nid: TC010\n---\n## Original test case\n"
            (cases_dir / "TC010.md").write_text(source_content, encoding="utf-8")

            def successful_command(*_args, **_kwargs):
                return SimpleNamespace(returncode=0, stdout="Page snapshot", stderr="")

            args = SimpleNamespace(
                case_ids=["TC010"],
                title="Dynamic case",
                session="tc010",
                nl="Open page",
                command_json=json.dumps(
                    ["playwright-cli", "-s=tc010", "open", "https://example.com"]
                ),
                phase="execute",
                run_dir=None,
            )
            with patch("subprocess.run", side_effect=successful_command):
                with contextlib.redirect_stdout(io.StringIO()):
                    run_live_step(root, args, root / "logs/commands.jsonl")

            report_path = next((root / "reports").glob("run-*/report.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["cases"][0]["status"], "RUNNING")
            self.assertEqual(report["cases"][0]["source_content"], source_content)
            self.assertEqual(len(report["cases"][0]["step_records"]), 1)
            args.run_dir = str(report_path.parent)
            args.nl = "Add another action without observing"
            with patch("subprocess.run") as run_command:
                with self.assertRaisesRegex(ValueError, "Observe the current page"):
                    run_live_step(root, args, root / "logs/commands.jsonl")
                run_command.assert_not_called()

            args.nl = "Inspect the loaded page"
            args.command_json = json.dumps(
                ["playwright-cli", "-s=tc010", "snapshot"]
            )
            args.phase = "observe"
            with patch("subprocess.run", side_effect=successful_command):
                with contextlib.redirect_stdout(io.StringIO()):
                    run_live_step(root, args, root / "logs/commands.jsonl")

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(report["cases"][0]["step_records"]), 2)
            self.assertEqual(report["cases"][0]["step_records"][1]["phase"], "observe")

            finish_args = SimpleNamespace(case_ids=["TC010"], run_dir=str(report_path.parent))
            with patch("subprocess.run", side_effect=successful_command) as commands:
                with contextlib.redirect_stdout(io.StringIO()):
                    finish_live_case(
                        root, finish_args, root / "logs/commands.jsonl"
                    )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["cases"][0]["status"], "PASS")
            self.assertTrue(
                any(
                    command[-2:] == ["-s=tc010", "close"]
                    for command in (call.args[0] for call in commands.call_args_list)
                    if isinstance(command, list)
                )
            )

    def test_failed_live_step_marks_case_terminal(self):
        run_live_step = RUNNER["run_live_step"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "reports").mkdir()
            cases_dir = root / "cases-repo" / "cases"
            cases_dir.mkdir(parents=True)
            (cases_dir / "TC011.md").write_text(
                "---\nid: TC011\n---\nFailing case\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                case_ids=["TC011"],
                title="Failing case",
                session="tc011",
                nl="Open an unavailable page",
                command_json=json.dumps(
                    ["playwright-cli", "-s=tc011", "open", "https://example.invalid"]
                ),
                phase="execute",
                run_dir=None,
            )
            command_results = [
                SimpleNamespace(returncode=1, stdout="", stderr="Navigation failed"),
                SimpleNamespace(returncode=1, stdout="", stderr="Screenshot unavailable"),
                SimpleNamespace(returncode=0, stdout="Closed", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with patch("subprocess.run", side_effect=command_results) as commands:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_live_step(root, args, root / "logs/commands.jsonl")

            report_path = next((root / "reports").glob("run-*/report.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["cases"][0]["status"], "FAIL")
            cleanup = [
                record
                for record in report["cases"][0]["step_records"]
                if record["phase"] == "cleanup"
            ]
            self.assertEqual(len(cleanup), 1)
            self.assertEqual(cleanup[0]["exit_code"], 0)
            self.assertTrue(
                any(
                    command[-2:] == ["-s=tc011", "close"]
                    for command in (call.args[0] for call in commands.call_args_list)
                    if isinstance(command, list)
                )
            )

            args.run_dir = str(report_path.parent)
            with patch("subprocess.run") as run_command:
                with self.assertRaisesRegex(ValueError, "not an appendable live case"):
                    run_live_step(root, args, root / "logs/commands.jsonl")
                run_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
