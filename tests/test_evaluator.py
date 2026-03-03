from pathlib import Path

from evaluator import _parse_junit_xml


def test_parse_junit_xml_counts_passed_tests(tmp_path: Path) -> None:
    xml_path = tmp_path / "report.xml"
    xml_path.write_text(
        """<testsuite tests=\"4\" failures=\"1\" errors=\"0\" skipped=\"0\"></testsuite>""",
        encoding="utf-8",
    )

    summary = _parse_junit_xml(xml_path)

    assert summary.total == 4
    assert summary.passed == 3
    assert summary.score == 75.0
