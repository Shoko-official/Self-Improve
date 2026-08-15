import unittest
from frontier_engine.benchmarks import Sample,compare,summarize
class BenchmarkTests(unittest.TestCase):
 def test_raw_samples_environment_and_comparison_are_preserved(self)->None:
  report=summarize((Sample("baseline",True,100,10,1000),Sample("optimized",True,80,12,900)),{"os":"Windows","runtime":"fixture"})
  self.assertEqual(len(report["raw_samples"]),2);self.assertEqual(compare(report,"baseline","optimized"),{"latency_delta_ms":-20.0,"throughput_delta":2.0,"memory_delta_mb":-100.0})
 def test_empty_samples_are_not_a_benchmark(self)->None:
  with self.assertRaises(ValueError):summarize((),{"runtime":"x"})
