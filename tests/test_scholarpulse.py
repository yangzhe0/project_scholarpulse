import json
import argparse
import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arxiv import collect_papers  # noqa: E402
from config import load_config  # noqa: E402
from scholarpulse import valid_date  # noqa: E402
from storage import known_ids  # noqa: E402
from workflow import run  # noqa: E402


def paper(identifier: str, title: str = "Test Paper") -> dict:
    return {
        "id": identifier,
        "title": title,
        "summary": "This paper presents a tested agent method.",
        "link": f"https://arxiv.org/abs/{identifier}",
        "published": "2026-06-20",
        "authors": ["A. Author"],
        "categories": ["cs.AI"],
    }


class ScholarPulseTests(unittest.TestCase):
    def test_date_must_use_iso_calendar_format(self):
        self.assertEqual(valid_date("2026-06-21"), "2026-06-21")
        for value in ("2026-6-21", "2026-02-30", "../../tmp/report"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                valid_date(value)

    def test_two_directions_have_independent_daily_and_index_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "tls": {"verify": True},
                "ollama": {"enabled": True},
                "directions": [
                    self.direction("ScholarPulse", "科研/ScholarPulse", "科研/ScholarPulse.md"),
                    self.direction("Astronomy", "天文/Astronomy", "天文/Astronomy.md"),
                ],
            }), encoding="utf-8")
            config = load_config(str(config_path))

            with patch("workflow.collect_papers", side_effect=[[paper("2606.10001v1")], [paper("2606.10002v1", "Astronomy Paper")]]), patch(
                "workflow.summarize",
                return_value="#### 一句话结论\n\n测试结论。\n\n#### 核心内容\n\n- 测试内容。",
            ):
                self.assertEqual(run(config, "2026-06-20"), 0)

            self.assert_report(root / "科研/ScholarPulse/2026-06-20.md", root / "科研/ScholarPulse.md")
            self.assert_report(root / "天文/Astronomy/2026-06-20.md", root / "天文/Astronomy.md")

    def test_ollama_failure_uses_structured_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            direction = self.direction("ScholarPulse", "ScholarPulse", "ScholarPulse.md")
            direction["daily_dir"] = str(root / "ScholarPulse")
            direction["index_file"] = str(root / "ScholarPulse.md")
            config = {"tls": {"verify": True}, "directions": [direction]}
            with patch("workflow.collect_papers", return_value=[paper("2606.10003v1")]), patch(
                "workflow.summarize", side_effect=RuntimeError("offline")
            ):
                self.assertEqual(run(config, "2026-06-20"), 0)
            content = (root / "ScholarPulse/2026-06-20.md").read_text(encoding="utf-8")
            self.assertIn("#### 一句话结论", content)
            self.assertIn("原始摘要已保留", content)

    def test_arxiv_versions_share_one_deduplication_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            daily = root / "ScholarPulse"
            daily.mkdir()
            (daily / "2026-06-19.md").write_text(
                "https://arxiv.org/abs/2606.12345v1", encoding="utf-8"
            )
            self.assertIn("2606.12345", known_ids(daily, root / "ScholarPulse.md"))

    def test_all_arxiv_queries_failed_is_an_error(self):
        direction = self.direction("ScholarPulse", "x", "x.md")
        with patch("arxiv.query_arxiv", side_effect=OSError("TLS failed")):
            with self.assertRaisesRegex(RuntimeError, "all arXiv queries failed"):
                collect_papers(direction, set(), ssl.create_default_context())

    def test_collection_failure_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            direction = self.direction("ScholarPulse", "ScholarPulse", "ScholarPulse.md")
            direction["daily_dir"] = str(root / "ScholarPulse")
            direction["index_file"] = str(root / "ScholarPulse.md")
            with patch("workflow.collect_papers", side_effect=RuntimeError("all failed")):
                self.assertEqual(run({"tls": {}, "directions": [direction]}, "2026-06-20"), 1)
            self.assertFalse((root / "ScholarPulse/2026-06-20.md").exists())
            self.assertFalse((root / "ScholarPulse.md").exists())

    def test_existing_daily_rebuilds_missing_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            direction = self.direction("ScholarPulse", "ScholarPulse", "ScholarPulse.md")
            direction["daily_dir"] = str(root / "ScholarPulse")
            direction["index_file"] = str(root / "ScholarPulse.md")
            daily_file = root / "ScholarPulse/2026-06-20.md"
            daily_file.parent.mkdir()
            daily_file.write_text(
                "## 重点论文与技术动态\n\n"
                "### 1. Existing Paper\n\n"
                "- **来源**：[arXiv](https://arxiv.org/abs/2606.12345v1)\n\n"
                "#### 一句话结论\n\nExisting conclusion.\n",
                encoding="utf-8",
            )

            with patch("workflow.collect_papers") as collect:
                self.assertEqual(run({"tls": {}, "directions": [direction]}, "2026-06-20"), 0)

            collect.assert_not_called()
            self.assertTrue((root / "ScholarPulse.md").exists())

    def test_result_json_contains_telegram_message_for_all_directions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directions = [
                self.direction("AI Agent", "agent", "agent.md"),
                self.direction("Astronomy", "astronomy", "astronomy.md"),
            ]
            for direction in directions:
                direction["daily_dir"] = str(root / direction["daily_dir"])
                direction["index_file"] = str(root / direction["index_file"])
                direction["knowledge_dir"] = f"科研/{direction['name']}"
            config = {
                "tls": {},
                "result_dir": str(root / "results"),
                "directions": directions,
            }

            with patch(
                "workflow.collect_papers",
                side_effect=[[paper("2606.10001v1")], [paper("2606.10002v1", "Astronomy Paper")]],
            ), patch(
                "workflow.summarize",
                return_value="#### 一句话结论\n\n测试结论。\n\n#### 核心内容\n\n- 测试内容。",
            ):
                self.assertEqual(run(config, "2026-06-20"), 0)

            payload = json.loads((root / "results/2026-06-20.json").read_text(encoding="utf-8"))
            self.assertEqual([item["direction"] for item in payload["reports"]], ["AI Agent", "Astronomy"])
            self.assertIn("AI Agent：收录 1 篇", payload["message"])
            self.assertIn("Astronomy Paper", payload["message"])
            self.assertIn("知识库：科研/Astronomy/2026-06-20.md", payload["message"])

    @staticmethod
    def direction(name: str, daily_dir: str, index_file: str) -> dict:
        return {
            "name": name,
            "daily_dir": daily_dir,
            "index_file": index_file,
            "limit": 2,
            "queries": ["all:agent"],
            "tags": [name, "学术监测"],
        }

    def assert_report(self, daily_file: Path, index_file: Path) -> None:
        self.assertTrue(daily_file.exists())
        self.assertTrue(index_file.exists())
        daily_content = daily_file.read_text(encoding="utf-8")
        index_content = index_file.read_text(encoding="utf-8")
        self.assertIn("## 今日速览", daily_content)
        self.assertIn("#### 一句话结论", daily_content)
        self.assertIn("## 日报", index_content)
        self.assertIn("## 去重清单", index_content)
        self.assertIn("[[2026-06-20]]", index_content)


if __name__ == "__main__":
    unittest.main()
