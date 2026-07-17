#!/usr/bin/env python3
"""Verify the public frontend contracts in the rendered Compose topology."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_COMPOSE_FILES = (
    "docker-compose.infra.yml",
    "docker-compose.app.yml",
)
DEVELOPMENT_OVERRIDE = "docker-compose.frontend-dev.yml"


def render_compose(*files: str) -> dict[str, object]:
    command = ["docker", "compose"]
    for compose_file in files:
        command.extend(("-f", compose_file))
    command.extend(("config", "--format", "json"))

    environment = os.environ.copy()
    environment.setdefault("LLM_API_KEY", "compose-contract-test")
    environment.setdefault("INTERNAL_AGENT_TOKEN", "compose-contract-test")
    environment.setdefault(
        "SECRET_KEY", "compose-contract-test-secret-key-00000000"
    )
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def frontend_service(config: dict[str, object]) -> dict[str, object]:
    services = config["services"]
    assert isinstance(services, dict)
    frontend = services["frontend"]
    assert isinstance(frontend, dict)
    return frontend


class FrontendComposeContractTests(unittest.TestCase):
    def test_default_topology_is_the_production_frontend(self) -> None:
        frontend = frontend_service(render_compose(*BASE_COMPOSE_FILES))

        self.assertEqual(frontend["build"]["target"], "production")
        self.assertEqual(
            frontend["ports"],
            [
                {
                    "mode": "ingress",
                    "host_ip": "127.0.0.1",
                    "target": 80,
                    "published": "5173",
                    "protocol": "tcp",
                }
            ],
        )
        self.assertNotIn("volumes", frontend)
        self.assertIn("http://127.0.0.1/", " ".join(frontend["healthcheck"]["test"]))

    def test_development_override_restores_vite_workflow(self) -> None:
        frontend = frontend_service(
            render_compose(*BASE_COMPOSE_FILES, DEVELOPMENT_OVERRIDE)
        )

        self.assertEqual(frontend["build"]["target"], "development")
        self.assertEqual(frontend["command"][:3], ["npm", "run", "dev"])
        self.assertEqual(
            frontend["ports"],
            [
                {
                    "mode": "ingress",
                    "host_ip": "127.0.0.1",
                    "target": 5173,
                    "published": "5173",
                    "protocol": "tcp",
                }
            ],
        )
        volumes = frontend["volumes"]
        self.assertTrue(
            any(
                volume.get("type") == "bind"
                and Path(volume["source"]) == REPO_ROOT / "frontend"
                and volume.get("target") == "/app"
                for volume in volumes
            )
        )
        self.assertTrue(
            any(volume.get("target") == "/app/node_modules" for volume in volumes)
        )
        self.assertIn(
            "http://127.0.0.1:5173/", " ".join(frontend["healthcheck"]["test"])
        )


if __name__ == "__main__":
    unittest.main()
