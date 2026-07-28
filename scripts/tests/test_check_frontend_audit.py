import unittest

from scripts.check_frontend_audit import evaluate_audit


def report_with(*vulnerabilities: tuple[str, dict]) -> dict:
    return {
        "auditReportVersion": 2,
        "vulnerabilities": dict(vulnerabilities),
    }


class FrontendAuditTests(unittest.TestCase):
    def test_accepts_only_the_exact_documented_advisory(self) -> None:
        report = report_with(
            (
                "react-router",
                {
                    "severity": "high",
                    "via": [
                        {
                            "source": 1124282,
                            "dependency": "react-router",
                            "severity": "high",
                            "url": "https://github.com/advisories/GHSA-qwww-vcr4-c8h2",
                        }
                    ],
                },
            ),
            (
                "react-router-dom",
                {"severity": "high", "via": ["react-router"]},
            ),
        )

        unexpected, accepted = evaluate_audit(report)

        self.assertEqual(unexpected, [])
        self.assertEqual(
            accepted,
            ["react-router GHSA-qwww-vcr4-c8h2 (high)"],
        )

    def test_rejects_the_same_identifier_for_a_different_source(self) -> None:
        report = report_with(
            (
                "react-router",
                {
                    "severity": "high",
                    "via": [
                        {
                            "source": 9999999,
                            "dependency": "react-router",
                            "severity": "high",
                            "url": "https://github.com/advisories/GHSA-qwww-vcr4-c8h2",
                        }
                    ],
                },
            )
        )

        unexpected, accepted = evaluate_audit(report)

        self.assertEqual(accepted, [])
        self.assertEqual(
            unexpected,
            ["react-router GHSA-qwww-vcr4-c8h2 (high)"],
        )

    def test_rejects_a_new_high_severity_advisory_and_its_wrapper(self) -> None:
        report = report_with(
            (
                "dependency",
                {
                    "severity": "critical",
                    "via": [
                        {
                            "source": 42,
                            "dependency": "dependency",
                            "severity": "critical",
                            "url": "https://github.com/advisories/GHSA-new-finding",
                        }
                    ],
                },
            ),
            (
                "direct-package",
                {"severity": "critical", "via": ["dependency"]},
            ),
        )

        unexpected, accepted = evaluate_audit(report)

        self.assertEqual(accepted, [])
        self.assertEqual(
            unexpected,
            [
                "dependency GHSA-new-finding (critical)",
                "direct-package: critical vulnerability via dependency",
            ],
        )

    def test_ignores_findings_below_the_threshold(self) -> None:
        report = report_with(
            (
                "dependency",
                {
                    "severity": "moderate",
                    "via": [
                        {
                            "source": 43,
                            "dependency": "dependency",
                            "severity": "moderate",
                            "url": "https://github.com/advisories/GHSA-moderate",
                        }
                    ],
                },
            )
        )

        self.assertEqual(evaluate_audit(report), ([], []))

    def test_rejects_an_unrecognized_severity(self) -> None:
        report = report_with(
            (
                "dependency",
                {
                    "severity": "future-severity",
                    "via": [
                        {
                            "source": 44,
                            "dependency": "dependency",
                            "severity": "future-severity",
                            "url": "https://github.com/advisories/GHSA-unknown-severity",
                        }
                    ],
                },
            )
        )

        unexpected, accepted = evaluate_audit(report)

        self.assertEqual(accepted, [])
        self.assertEqual(
            unexpected,
            ["dependency GHSA-unknown-severity (future-severity)"],
        )

    def test_rejects_audit_errors_and_malformed_reports(self) -> None:
        self.assertTrue(evaluate_audit({"error": {"code": "EAI_AGAIN"}})[0])
        self.assertTrue(evaluate_audit({})[0])
        for report in (None, [], "not-an-object", 1):
            with self.subTest(report=report):
                self.assertEqual(
                    evaluate_audit(report),
                    (["npm audit report is not a JSON object"], []),
                )


if __name__ == "__main__":
    unittest.main()
