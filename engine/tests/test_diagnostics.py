import unittest
from frontier_engine.diagnostics import Diagnostic,Inference,user_view,validate
class DiagnosticTests(unittest.TestCase):
 def test_evidence_and_inference_are_kept_distinct_and_secrets_redacted(self)->None:
  item=Diagnostic("FR-PROVIDER-AUTH","error","provider","Credentials were rejected",("HTTP 401 received",),(Inference("Credential may be expired",.8),),("request-7",),("Update the keychain credential",),("authorization",))
  view=user_view(item,{"authorization":"Bearer secret","endpoint":"https://api.example"})
  self.assertEqual(view["details"]["authorization"],"[redacted]");self.assertEqual(view["inferences"][0]["confidence"],.8)
 def test_diagnostic_requires_facts_and_evidence(self)->None:
  with self.assertRaises(ValueError):validate(Diagnostic("FR-X","error","x","bad",(),(),(),()))
