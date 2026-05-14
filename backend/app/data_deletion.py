"""
Shared Data Deletion result contract.

Deletion workflows span multiple storage targets. This module keeps their
operator-visible result shape consistent and retry-safe.
"""

from typing import Literal, TypedDict


DeletionTargetStatus = Literal["succeeded", "skipped", "failed"]
DeletionSummaryStatus = Literal["succeeded", "partial_failure", "failed"]


class DeletionTargetResult(TypedDict):
    target_kind: str
    target_id: str
    action: str
    status: DeletionTargetStatus
    retryable: bool
    detail: str


class DeletionCounts(TypedDict):
    succeeded: int
    skipped: int
    failed: int


class DeletionSummaryResult(TypedDict):
    status: DeletionSummaryStatus
    retryable: bool
    counts: DeletionCounts
    results: list[DeletionTargetResult]


def deletion_target_succeeded(
    *,
    target_kind: str,
    target_id: str,
    action: str,
    detail: str,
) -> DeletionTargetResult:
    return {
        "target_kind": target_kind,
        "target_id": target_id,
        "action": action,
        "status": "succeeded",
        "retryable": False,
        "detail": detail,
    }


def deletion_target_skipped(
    *,
    target_kind: str,
    target_id: str,
    action: str,
    detail: str,
) -> DeletionTargetResult:
    return {
        "target_kind": target_kind,
        "target_id": target_id,
        "action": action,
        "status": "skipped",
        "retryable": False,
        "detail": detail,
    }


def deletion_target_failed(
    *,
    target_kind: str,
    target_id: str,
    action: str,
    detail: str,
    retryable: bool,
) -> DeletionTargetResult:
    return {
        "target_kind": target_kind,
        "target_id": target_id,
        "action": action,
        "status": "failed",
        "retryable": retryable,
        "detail": detail,
    }


def summarize_deletion_results(results: list[DeletionTargetResult]) -> DeletionSummaryResult:
    counts: DeletionCounts = {
        "succeeded": 0,
        "skipped": 0,
        "failed": 0,
    }
    for result in results:
        counts[result["status"]] += 1

    if counts["failed"] == 0:
        status: DeletionSummaryStatus = "succeeded"
    elif counts["succeeded"] > 0 or counts["skipped"] > 0:
        status = "partial_failure"
    else:
        status = "failed"

    return {
        "status": status,
        "retryable": any(result["status"] == "failed" and result["retryable"] for result in results),
        "counts": counts,
        "results": results,
    }
