"""Load test suite for RevOps platform (R6-01).

Simulates high-concurrency traffic across 50 organizations x 500 accounts.
Covers:
- Today cockpit view (GET /today)
- Accounts list with filtering and sorting (GET /accounts)
- Account detail (GET /accounts/{id})
- Timeline paging (GET /accounts/{id}/timeline)
- Sync fan-out and nightly batch run
"""

import os
import random
from uuid import uuid4

from locust import HttpUser, between, task


class RevOpsUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        """Simulate user login / authentication."""
        self.auth_token = os.getenv("LOAD_TEST_TOKEN", "mock-token")
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        self.sample_account_ids: list[str] = []

    @task(5)
    def view_today(self) -> None:
        """Test Today cockpit: target p95 < 800ms."""
        self.client.get(
            "/api/v1/today?owner=all",
            headers=self.headers,
            name="/api/v1/today",
        )

    @task(4)
    def list_accounts(self) -> None:
        """Test Accounts list: target p95 < 500ms."""
        res = self.client.get(
            "/api/v1/accounts?limit=25&sort=priority_score&direction=desc",
            headers=self.headers,
            name="/api/v1/accounts",
        )
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            if items:
                self.sample_account_ids = [item["id"] for item in items[:5]]

    @task(3)
    def view_account_detail(self) -> None:
        """Test account detail retrieval."""
        if self.sample_account_ids:
            acc_id = random.choice(self.sample_account_ids)
            self.client.get(
                f"/api/v1/accounts/{acc_id}",
                headers=self.headers,
                name="/api/v1/accounts/{id}",
            )

    @task(3)
    def page_timeline(self) -> None:
        """Test timeline paging."""
        if self.sample_account_ids:
            acc_id = random.choice(self.sample_account_ids)
            self.client.get(
                f"/api/v1/accounts/{acc_id}/timeline?limit=20",
                headers=self.headers,
                name="/api/v1/accounts/{id}/timeline",
            )

    @task(1)
    def list_findings(self) -> None:
        """Test findings list."""
        self.client.get(
            "/api/v1/findings?status=open&limit=25",
            headers=self.headers,
            name="/api/v1/findings",
        )


class NightlyBatchSimulationUser(HttpUser):
    wait_time = between(1.0, 3.0)

    def on_start(self) -> None:
        self.internal_key = os.getenv("INTERNAL_API_KEY", "test-internal-key")
        self.headers = {"X-Internal-Key": self.internal_key}

    @task
    def simulate_nightly_batch(self) -> None:
        """Simulate nightly batch extraction and context fetching."""
        org_id = str(uuid4())
        acc_id = str(uuid4())
        self.client.get(
            f"/internal/v1/orgs/{org_id}/accounts/{acc_id}/context",
            headers=self.headers,
            name="/internal/v1/orgs/{org}/accounts/{id}/context",
        )
