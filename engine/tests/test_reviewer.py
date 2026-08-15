import unittest
from frontier_engine.reviewer import Claim, review_claims

class ReviewerTests(unittest.TestCase):
 def test_reviewer_flags_missing_evidence_without_claiming_a_rerun(self) -> None:
  findings=review_claims((Claim("s1", "Paper says X", "source"), Claim("c1", "Mean was 4", "computed"), Claim("i1", "X causes Y", "inference")))
  self.assertEqual([finding.code for finding in findings], ["FR-REVIEW-UNSOURCED", "FR-REVIEW-UNTRACEABLE-COMPUTATION", "FR-REVIEW-UNSUPPORTED-INFERENCE"])
  self.assertNotIn("rerun", " ".join(finding.message.lower() for finding in findings))
 def test_reviewer_accepts_evidenced_claims(self) -> None:
  self.assertEqual(review_claims((Claim("s", "source", "source", ("citation-1",)), Claim("c", "mean", "computed", execution_log_id="run-1"))), ())
