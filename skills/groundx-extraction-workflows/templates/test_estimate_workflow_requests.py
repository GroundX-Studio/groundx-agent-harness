"""Unit tests for request-fanout estimation.

These tests stay offline: they exercise page/chunk/request arithmetic and
workflow parsing without GroundX API calls.
"""

import unittest

import estimate_workflow_requests as estimator


class EstimateWorkflowRequestsTest(unittest.TestCase):
    def test_current_repro_blocks_chunk_level_custom_steps(self):
        workflow = {
            "customSteps": [
                {"name": "statement_a", "level": "chunk", "kind": "instruct"},
                {"name": "statement_b", "level": "chunk", "kind": "instruct"},
                {"name": "statement_c", "level": "chunk", "kind": "instruct"},
            ]
        }

        report = estimator.estimate_request_fanout(
            workflow,
            page_counts=[198],
            chunks_per_page=909 / 198,
        )

        self.assertEqual(report["risk_status"], "block")
        self.assertEqual(report["step_counts"]["chunk"], 3)
        self.assertGreater(report["max_estimated_requests"], 2000)

    def test_page_section_statement_strategy_stays_under_cap(self):
        workflow = {
            "section_strategy": "page",
            "customSteps": [
                {"name": "statement_a", "level": "section", "kind": "instruct"},
                {"name": "statement_b", "level": "section", "kind": "instruct"},
                {"name": "statement_c", "level": "section", "kind": "instruct"},
            ],
        }

        report = estimator.estimate_request_fanout(
            workflow,
            page_counts=[198],
            chunks_per_page=909 / 198,
        )

        self.assertEqual(report["risk_status"], "ok")
        self.assertEqual(report["step_counts"]["section"], 3)
        self.assertLess(report["max_estimated_requests"], 2000)
        observed = [
            scenario
            for scenario in report["scenarios"]
            if scenario["name"] == "observed_max"
        ][0]
        self.assertEqual(observed["section_requests"], 198 * 3)

    def test_section_without_page_strategy_is_unknown_high_risk(self):
        workflow = {
            "customSteps": [
                {"name": "statement_a", "level": "section", "kind": "instruct"},
            ],
        }

        report = estimator.estimate_request_fanout(workflow, page_counts=[12])

        self.assertEqual(report["risk_status"], "unknown_high_risk")
        self.assertTrue(report["unknown_section_fanout"])

    def test_low_sample_uses_large_document_scenario(self):
        workflow = {
            "customSteps": [
                {"name": "statement_a", "level": "chunk", "kind": "instruct"},
                {"name": "statement_b", "level": "chunk", "kind": "instruct"},
                {"name": "statement_c", "level": "chunk", "kind": "instruct"},
            ],
        }

        report = estimator.estimate_request_fanout(workflow, page_counts=[75])

        self.assertEqual(report["sample_confidence"], "weak")
        scenario_names = {scenario["name"] for scenario in report["scenarios"]}
        self.assertIn("plausible_large_document", scenario_names)
        self.assertEqual(report["risk_status"], "block")

    def test_generic_repeating_records_remain_allowed_when_under_threshold(self):
        workflow = {
            "customSteps": [
                {"name": "line_items", "level": "chunk", "kind": "keys"},
            ],
        }

        report = estimator.estimate_request_fanout(
            workflow,
            page_counts=[20],
            chunks_per_page=3,
        )

        self.assertEqual(report["risk_status"], "ok")
        self.assertEqual(report["step_counts"]["chunk"], 1)
        self.assertLess(report["max_estimated_requests"], 1500)


if __name__ == "__main__":
    unittest.main()
