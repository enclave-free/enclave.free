#!/usr/bin/env python3
"""Quick script to test available Sage/Tinfoil models."""

import json
import os
import sys

import requests


def main():
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("TINFOIL_API_KEY")

    if not api_key:
        print("LLM_API_KEY or TINFOIL_API_KEY not found in environment")
        print("Run: export LLM_API_KEY=your_key_here")
        sys.exit(1)

    base_url = os.environ.get("LLM_API_URL") or os.environ.get(
        "TINFOIL_API_URL", "http://localhost:8089/v1"
    )
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        print(f"Requesting: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print("\nAvailable models:\n")

            if "data" in data:
                for model in data["data"]:
                    model_id = model.get("id", "unknown")
                    print(f"  - {model_id}")
            else:
                print(json.dumps(data, indent=2))
        else:
            print(f"Error response:\n{resp.text}")
            sys.exit(resp.status_code or 1)

    except requests.exceptions.ConnectionError as exc:
        print(f"Connection failed - is the Tinfoil proxy running? {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
