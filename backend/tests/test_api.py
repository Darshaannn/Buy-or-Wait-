import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


class ApiTests(unittest.TestCase):

    def test_health_endpoint(self):
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "buy-or-wait-api")
        self.assertEqual(data["version"], "1.0.0")

    def test_list_scenarios(self):
        resp = client.get("/api/scenarios")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 6)
        ids = [s["scenario_id"] for s in data]
        self.assertIn("scenario_01_safe_now", ids)
        self.assertIn("scenario_06_not_affordable", ids)

    def test_get_scenario_by_id(self):
        resp = client.get("/api/scenarios/scenario_01_safe_now")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["scenario_id"], "scenario_01_safe_now")
        self.assertIn("purchase", data["data"])

    def test_get_scenario_not_found(self):
        resp = client.get("/api/scenarios/non_existent_id")
        self.assertEqual(resp.status_code, 404)

    def test_analyze_valid_request(self):
        scenario_resp = client.get("/api/scenarios/scenario_01_safe_now")
        scenario_data = scenario_resp.json()["data"]

        resp = client.post("/api/analyze", json=scenario_data)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "safe_now")
        self.assertEqual(data["headline"], "SAFE TO BUY NOW")
        self.assertEqual(data["recommended_method"], "full_payment")
        self.assertGreater(float(data["amount_safe_today"]), 0)
        self.assertGreater(len(data["forecast"]), 80)

    def test_analyze_deterministic_reproducibility(self):
        scenario_resp = client.get("/api/scenarios/scenario_02_affordable_later")
        scenario_data = scenario_resp.json()["data"]

        res1 = client.post("/api/analyze", json=scenario_data).json()
        res2 = client.post("/api/analyze", json=scenario_data).json()

        self.assertEqual(res1["status"], res2["status"])
        self.assertEqual(res1["amount_safe_today"], res2["amount_safe_today"])
        self.assertEqual(res1["recommended_method"], res2["recommended_method"])
        self.assertEqual(res1["payment_plan"], res2["payment_plan"])
        self.assertEqual(res1["minimum_projected_balance"], res2["minimum_projected_balance"])

    def test_analyze_malformed_request(self):
        # Missing required fields like amount
        malformed = {
            "purchase": {"currency": "INR"},
            "profile": {"available_balance": "100.00"}
        }
        resp = client.post("/api/analyze", json=malformed)
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
