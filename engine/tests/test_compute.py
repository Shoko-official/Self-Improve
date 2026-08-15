import sys, unittest
from unittest.mock import patch
from frontier_engine.compute import ComputeApprovalRequired, ComputePlan, run_local, run_remote, validate_plan

class ComputeTests(unittest.TestCase):
 def test_local_fixture_executes_and_records_output(self) -> None:
  plan=ComputePlan("local",(sys.executable,"-c","print('fixture complete')"),1,128,5,0,0)
  result=run_local(plan); self.assertEqual((result["state"],result["stdout"]),("succeeded","fixture complete\n"))
 def test_remote_plan_requires_approval_and_complete_preview(self) -> None:
  plan=ComputePlan("ssh",("python","analysis.py"),4,8192,300,1.5,99)
  with self.assertRaises(ComputeApprovalRequired): validate_plan(plan,False)
  validate_plan(plan,True)

 def test_approved_ssh_executor_uses_argument_vector_without_shell(self) -> None:
  plan=ComputePlan("ssh",("python","analysis.py"),4,8192,300,1.5,99,"gpu.example","/srv/frontier")
  completed=type("Result",(),{"returncode":0,"stdout":"done\n","stderr":""})()
  with patch("frontier_engine.compute.subprocess.run",return_value=completed) as run:
   result=run_remote(plan,True)
  self.assertEqual(result["state"],"succeeded")
  self.assertEqual(run.call_args.args[0],["ssh","gpu.example","--","python","analysis.py"])
  self.assertNotIn("shell",run.call_args.kwargs)

 def test_slurm_executor_preserves_resources_and_cloud_stays_unconfigured(self) -> None:
  plan=ComputePlan("slurm",("python","analysis.py"),4,8192,300,0,0,"cluster","/srv/frontier")
  completed=type("Result",(),{"returncode":0,"stdout":"12345;cluster\n","stderr":""})()
  with patch("frontier_engine.compute.subprocess.run",return_value=completed) as run:
   result=run_remote(plan,True)
  self.assertEqual(result["scheduler_job_id"],"12345;cluster")
  command=run.call_args.args[0]
  self.assertIn("--cpus-per-task",command); self.assertIn("--mem",command); self.assertIn("--chdir",command)
  cloud=ComputePlan("cloud",("python","analysis.py"),1,128,5,0,0,"provider")
  self.assertEqual(run_remote(cloud,True)["diagnostic"]["code"],"FR-REMOTE-CLOUD-NOT-CONFIGURED")
