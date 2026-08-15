import sys, unittest
from frontier_engine.compute import ComputeApprovalRequired, ComputePlan, run_local, validate_plan

class ComputeTests(unittest.TestCase):
 def test_local_fixture_executes_and_records_output(self) -> None:
  plan=ComputePlan("local",(sys.executable,"-c","print('fixture complete')"),1,128,5,0,0)
  result=run_local(plan); self.assertEqual((result["state"],result["stdout"]),("succeeded","fixture complete\n"))
 def test_remote_plan_requires_approval_and_complete_preview(self) -> None:
  plan=ComputePlan("ssh",("python","analysis.py"),4,8192,300,1.5,99)
  with self.assertRaises(ComputeApprovalRequired): validate_plan(plan,False)
  validate_plan(plan,True)
