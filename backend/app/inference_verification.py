"""Provider-neutral Verifiable Inference checks and Tinfoil attestation capture."""

from __future__ import annotations

import json
import hashlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol


VERIFIER_VERSION = "enclave-tinfoil-verifier/1"
TINFOIL_ATTESTATION_PATH = "/.well-known/tinfoil-attestation"
SENSITIVE_ATTESTATION_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}


@dataclass(frozen=True)
class InferenceVerificationResult:
    provider_identity: str
    provider_endpoint: str
    model_identifier: str
    status: str
    trigger: str
    expected_claims_fingerprint: str
    actual_claims_fingerprint: str | None
    verifier_version: str
    attestation_material: object | None
    failure_category: str | None = None
    failure_message: str | None = None
    checked_at: datetime | None = None
    expires_at: datetime | None = None


class InferenceVerifier(Protocol):
    def verify(
        self,
        *,
        provider_identity: str,
        provider_endpoint: str,
        model_identifier: str,
        expected_claims: dict[str, Any],
        trigger: str = "manual",
        api_key: str | None = None,
    ) -> InferenceVerificationResult:
        ...


class InferenceVerificationStorage(Protocol):
    def create_inference_verification_record(self, **kwargs: Any) -> dict:
        ...


Fetcher = Callable[[str, dict[str, str], float], tuple[int, object]]


def fingerprint_claims(claims: object) -> str:
    encoded = json.dumps(claims, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def redact_attestation_material(value: object) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if _is_sensitive_attestation_key(key):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_attestation_material(item)
        return redacted
    if isinstance(value, list):
        return [redact_attestation_material(item) for item in value]
    return value


class TinfoilVerifier:
    def __init__(self, *, fetcher: Fetcher | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or _default_fetcher
        self.timeout = timeout

    def verify(
        self,
        *,
        provider_identity: str,
        provider_endpoint: str,
        model_identifier: str,
        expected_claims: dict[str, Any],
        trigger: str = "manual",
        api_key: str | None = None,
    ) -> InferenceVerificationResult:
        checked_at = datetime.now(timezone.utc)
        expected_fingerprint = fingerprint_claims(expected_claims)
        attestation_url = _attestation_url(provider_endpoint)
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            status_code, raw_material = self.fetcher(attestation_url, headers, self.timeout)
        except Exception as exc:
            return _failed_result(
                provider_identity=provider_identity,
                provider_endpoint=provider_endpoint,
                model_identifier=model_identifier,
                trigger=trigger,
                expected_claims_fingerprint=expected_fingerprint,
                checked_at=checked_at,
                failure_category="attestation_unavailable",
                failure_message=str(exc),
                attestation_material=None,
            )

        sanitized_material = redact_attestation_material(raw_material)
        actual_claims = _actual_claims_from_attestation(sanitized_material)
        actual_fingerprint = fingerprint_claims(actual_claims)

        if status_code < 200 or status_code >= 300:
            return _failed_result(
                provider_identity=provider_identity,
                provider_endpoint=provider_endpoint,
                model_identifier=model_identifier,
                trigger=trigger,
                expected_claims_fingerprint=expected_fingerprint,
                actual_claims_fingerprint=actual_fingerprint,
                checked_at=checked_at,
                failure_category="attestation_unavailable",
                failure_message=f"Attestation endpoint returned HTTP {status_code}",
                attestation_material=sanitized_material,
            )

        mismatch = _first_claim_mismatch(expected_claims, actual_claims)
        if mismatch:
            return _failed_result(
                provider_identity=provider_identity,
                provider_endpoint=provider_endpoint,
                model_identifier=model_identifier,
                trigger=trigger,
                expected_claims_fingerprint=expected_fingerprint,
                actual_claims_fingerprint=actual_fingerprint,
                checked_at=checked_at,
                failure_category="claim_mismatch",
                failure_message=mismatch,
                attestation_material=sanitized_material,
            )

        return InferenceVerificationResult(
            provider_identity=provider_identity,
            provider_endpoint=provider_endpoint,
            model_identifier=model_identifier,
            status="success",
            trigger=trigger,
            expected_claims_fingerprint=expected_fingerprint,
            actual_claims_fingerprint=actual_fingerprint,
            verifier_version=VERIFIER_VERSION,
            attestation_material=sanitized_material,
            checked_at=checked_at,
        )


def verify_and_store(
    *,
    verifier: InferenceVerifier,
    storage: InferenceVerificationStorage,
    provider_identity: str,
    provider_endpoint: str,
    model_identifier: str,
    expected_claims: dict[str, Any],
    trigger: str = "manual",
    api_key: str | None = None,
) -> dict:
    result = verifier.verify(
        provider_identity=provider_identity,
        provider_endpoint=provider_endpoint,
        model_identifier=model_identifier,
        expected_claims=expected_claims,
        trigger=trigger,
        api_key=api_key,
    )
    return storage.create_inference_verification_record(
        provider_identity=result.provider_identity,
        provider_endpoint=result.provider_endpoint,
        model_identifier=result.model_identifier,
        status=result.status,
        trigger=result.trigger,
        expected_claims_fingerprint=result.expected_claims_fingerprint,
        actual_claims_fingerprint=result.actual_claims_fingerprint,
        verifier_version=result.verifier_version,
        failure_category=result.failure_category,
        failure_message=result.failure_message,
        attestation_material=result.attestation_material,
        checked_at=result.checked_at,
        expires_at=result.expires_at,
    )


def _failed_result(
    *,
    provider_identity: str,
    provider_endpoint: str,
    model_identifier: str,
    trigger: str,
    expected_claims_fingerprint: str,
    checked_at: datetime,
    failure_category: str,
    failure_message: str,
    attestation_material: object | None,
    actual_claims_fingerprint: str | None = None,
) -> InferenceVerificationResult:
    return InferenceVerificationResult(
        provider_identity=provider_identity,
        provider_endpoint=provider_endpoint,
        model_identifier=model_identifier,
        status="failed",
        trigger=trigger,
        expected_claims_fingerprint=expected_claims_fingerprint,
        actual_claims_fingerprint=actual_claims_fingerprint,
        verifier_version=VERIFIER_VERSION,
        failure_category=failure_category,
        failure_message=failure_message,
        attestation_material=attestation_material,
        checked_at=checked_at,
    )


def _attestation_url(provider_endpoint: str) -> str:
    base = provider_endpoint.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return f"{base}{TINFOIL_ATTESTATION_PATH}"


def _actual_claims_from_attestation(attestation_material: object) -> object:
    if isinstance(attestation_material, dict) and isinstance(attestation_material.get("predicate"), dict):
        return attestation_material["predicate"]
    return attestation_material


def _first_claim_mismatch(expected: dict[str, Any], actual: object) -> str | None:
    if not expected:
        return None
    if not isinstance(actual, dict):
        return "Attestation material did not expose normalized claims."
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            return f"Expected claim {key!r} did not match attestation material."
    return None


def _is_sensitive_attestation_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in SENSITIVE_ATTESTATION_KEYS or normalized.endswith("_token") or normalized.endswith("_secret")


def _default_fetcher(url: str, headers: dict[str, str], timeout: float) -> tuple[int, object]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return int(response.status), json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload: object = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"body": body}
        return int(exc.code), payload
