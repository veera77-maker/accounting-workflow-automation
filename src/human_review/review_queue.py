"""Human review queue — receives REVIEW items and records human decisions.

This component handles the "Human review" step of the Case 3 workflow.

Design decisions:
- In-memory queue — no persistence required by spec for this prototype.
- Every REVIEW decision is recorded with reviewer, action, reason, timestamp.
- CORRECT decisions preserve the corrected values.
- The queue does NOT perform anomaly detection — it receives items from the detector.
- The queue does NOT generate P&L or call an LLM.
- Invalid actions are rejected with clear error messages.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from models.anomaly import AnomalyResult, AnomalyVerdict
from models.human_review import (
    HumanReviewDecision,
    HumanReviewItem,
    ReviewDecision,
)
from models.expense import ExpenseRecord


class ReviewQueueError(Exception):
    """Raised when a review queue operation fails."""
    pass


class HumanReviewQueue:
    """In-memory queue for human review of anomalous expenses.

    Items enter the queue when the anomaly detector produces a REVIEW verdict.
    A human reviewer then decides: APPROVE, REJECT, or CORRECT.
    """

    def __init__(self):
        self._queue: list[HumanReviewItem] = []
        self._decisions: list[HumanReviewDecision] = []
        self._reviewed_ids: set[str] = set()

    @property
    def pending_count(self) -> int:
        """Number of items awaiting review."""
        return len(self._queue)

    @property
    def decided_count(self) -> int:
        """Number of items that have been reviewed."""
        return len(self._decisions)

    @property
    def pending_items(self) -> list[HumanReviewItem]:
        """List of items awaiting review (copy)."""
        return list(self._queue)

    @property
    def decisions(self) -> list[HumanReviewDecision]:
        """List of all decisions made (copy)."""
        return list(self._decisions)

    def add_to_queue(
        self,
        expense: ExpenseRecord,
        anomaly_result: AnomalyResult,
    ) -> HumanReviewItem:
        """Add an expense with REVIEW verdict to the human review queue.

        Args:
            expense: The expense record being flagged.
            anomaly_result: The anomaly detection result with REVIEW verdict.

        Returns:
            The created HumanReviewItem.

        Raises:
            ReviewQueueError: If the anomaly verdict is not REVIEW,
                or if the expense is already in the queue.
        """
        if anomaly_result.verdict != AnomalyVerdict.REVIEW:
            raise ReviewQueueError(
                f"Cannot add expense {expense.expense_id} to review queue: "
                f"anomaly verdict is '{anomaly_result.verdict.value}', not 'review'"
            )

        if expense.expense_id in self._reviewed_ids:
            raise ReviewQueueError(
                f"Expense {expense.expense_id} is already in the review queue or has been reviewed"
            )

        review_id = f"REV-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        item = HumanReviewItem(
            review_id=review_id,
            expense_id=expense.expense_id,
            anomaly_reasons=[r.value for r in anomaly_result.reasons],
            evidence=anomaly_result.features,
            queued_at=now,
        )

        self._queue.append(item)
        self._reviewed_ids.add(expense.expense_id)

        return item

    def add_item_directly(
        self,
        item: HumanReviewItem,
    ) -> None:
        """Add a HumanReviewItem directly to the queue.

        Used for testing or when the item is pre-constructed.
        """
        if item.expense_id in self._reviewed_ids:
            raise ReviewQueueError(
                f"Expense {item.expense_id} is already in the review queue or has been reviewed"
            )
        self._queue.append(item)
        self._reviewed_ids.add(item.expense_id)

    def approve(
        self,
        review_id: str,
        reviewer: str,
        reason: str,
    ) -> HumanReviewDecision:
        """Approve an expense in the review queue.

        Args:
            review_id: The review ID to approve.
            reviewer: Name/ID of the human reviewer.
            reason: Human-readable reason for approval.

        Returns:
            The recorded HumanReviewDecision.

        Raises:
            ReviewQueueError: If review_id not found in queue.
        """
        item = self._find_and_remove(review_id)

        decision = HumanReviewDecision(
            review_id=review_id,
            expense_id=item.expense_id,
            reviewer=reviewer,
            decision=ReviewDecision.APPROVE,
            reason=reason,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )

        self._decisions.append(decision)
        return decision

    def reject(
        self,
        review_id: str,
        reviewer: str,
        reason: str,
    ) -> HumanReviewDecision:
        """Reject an expense in the review queue.

        Args:
            review_id: The review ID to reject.
            reviewer: Name/ID of the human reviewer.
            reason: Human-readable reason for rejection.

        Returns:
            The recorded HumanReviewDecision.

        Raises:
            ReviewQueueError: If review_id not found in queue.
        """
        item = self._find_and_remove(review_id)

        decision = HumanReviewDecision(
            review_id=review_id,
            expense_id=item.expense_id,
            reviewer=reviewer,
            decision=ReviewDecision.REJECT,
            reason=reason,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )

        self._decisions.append(decision)
        return decision

    def correct(
        self,
        review_id: str,
        reviewer: str,
        reason: str,
        corrected_amount: float | None = None,
        corrected_category: str | None = None,
        corrected_vendor: str | None = None,
    ) -> HumanReviewDecision:
        """Correct an expense in the review queue.

        Args:
            review_id: The review ID to correct.
            reviewer: Name/ID of the human reviewer.
            reason: Human-readable reason for correction.
            corrected_amount: New amount (if correcting amount).
            corrected_category: New category (if correcting category).
            corrected_vendor: New vendor (if correcting vendor).

        Returns:
            The recorded HumanReviewDecision.

        Raises:
            ReviewQueueError: If review_id not found in queue.
        """
        item = self._find_and_remove(review_id)

        decision = HumanReviewDecision(
            review_id=review_id,
            expense_id=item.expense_id,
            reviewer=reviewer,
            decision=ReviewDecision.CORRECT,
            reason=reason,
            corrected_amount=corrected_amount,
            corrected_category=corrected_category,
            corrected_vendor=corrected_vendor,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )

        self._decisions.append(decision)
        return decision

    def get_decision(self, review_id: str) -> HumanReviewDecision | None:
        """Look up a decision by review_id."""
        for d in self._decisions:
            if d.review_id == review_id:
                return d
        return None

    def get_decision_by_expense(self, expense_id: str) -> HumanReviewDecision | None:
        """Look up a decision by expense_id."""
        for d in self._decisions:
            if d.expense_id == expense_id:
                return d
        return None

    def _find_and_remove(self, review_id: str) -> HumanReviewItem:
        """Find and remove an item from the queue by review_id.

        Raises ReviewQueueError if not found.
        """
        for i, item in enumerate(self._queue):
            if item.review_id == review_id:
                return self._queue.pop(i)
        raise ReviewQueueError(
            f"Review ID '{review_id}' not found in queue"
        )

    def to_dict(self) -> dict:
        """Serialize queue state for audit/logging."""
        return {
            "pending_count": self.pending_count,
            "decided_count": self.decided_count,
            "pending_items": [item.model_dump(mode="json") for item in self._queue],
            "decisions": [d.model_dump(mode="json") for d in self._decisions],
        }
