import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from frontier_engine.inference import plan_ollama_inference
from frontier_engine.runtimes import OllamaEmbedder, probe_ollama, stream_ollama, warmup_ollama


class OllamaHandler(BaseHTTPRequestHandler):
    model = {"name": "qwen3", "model": "qwen3", "size": 4 * 1024**3, "digest": "fixture", "details": {"format": "gguf", "parameter_size": "4B", "quantization_level": "Q4_K_M"}}

    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._json({"models": [self.model]})
            return
        if self.path == "/api/ps":
            self._json({"models": [{**self.model, "size_vram": 3 * 1024**3, "context_length": 4096, "expires_at": "fixture"}]})
            return
        self.send_response(404); self.end_headers()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        if self.path == "/api/embed":
            self._json({"embeddings": [[0.25, 0.75]]}); return
        if self.path != "/api/generate":
            self.send_response(404); self.end_headers(); return
        if request.get("stream") is False:
            self._json({"model": "qwen3", "response": "", "done": True, "total_duration": 40, "load_duration": 30})
            return
        lines = [
            {"model": "qwen3", "response": "hello ", "done": False},
            {"model": "qwen3", "response": "world", "done": False},
            {"model": "qwen3", "response": "", "done": True, "done_reason": "stop", "total_duration": 2_000_000_000, "load_duration": 500_000_000, "prompt_eval_count": 3, "prompt_eval_duration": 100_000_000, "eval_count": 10, "eval_duration": 1_000_000_000},
        ]
        body = b"".join(json.dumps(item).encode() + b"\n" for item in lines)
        self.send_response(200); self.send_header("Content-Type", "application/x-ndjson"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def _json(self, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        return


class InferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), OllamaHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.environment = patch.dict(os.environ, {"OLLAMA_HOST": f"http://127.0.0.1:{self.server.server_port}"})
        self.which = patch("frontier_engine.runtimes.shutil.which", return_value="ollama")
        self.version = patch("frontier_engine.runtimes.subprocess.run", return_value=__import__("subprocess").CompletedProcess([], 0, "ollama 1.0\n", ""))
        self.environment.start(); self.which.start(); self.version.start()

    def tearDown(self) -> None:
        self.version.stop(); self.which.stop(); self.environment.stop()
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_probe_stream_metrics_and_warmup_use_loopback_api(self) -> None:
        probe = probe_ollama()
        self.assertTrue(probe["available"])
        self.assertEqual(probe["installed_models"][0]["size"], 4 * 1024**3)
        stream = stream_ollama("qwen3", "hello", {"num_ctx": 4096}, "10m", probe)
        self.assertEqual("".join(stream), "hello world")
        self.assertEqual(stream.metrics["tokens_per_second"], 10.0)
        warmup = warmup_ollama("qwen3", {"num_ctx": 4096}, "10m", probe)
        self.assertEqual(warmup["loaded"]["context_length"], 4096)

    def test_embeddings_use_the_verified_local_ollama_api(self) -> None:
        self.assertEqual(OllamaEmbedder("qwen3", probe_ollama()).embed("local retrieval"), [0.25, 0.75])

    def test_profile_selects_bounded_defaults_and_memory_evidence(self) -> None:
        probe = probe_ollama()
        hardware = {"logical_cores": 32, "system_memory_bytes": 32 * 1024**3, "gpu_devices": [], "gpu_memory_bytes": 0}
        plan = plan_ollama_inference(["qwen3"], runtime_probe=probe, hardware_probe=hardware)
        self.assertTrue(plan["supported"])
        self.assertEqual(plan["options"], {"num_ctx": 4096, "num_batch": 512, "num_thread": 16})
        self.assertEqual(plan["memory_source"], "system")

    def test_profile_validates_multi_model_concurrency_against_gpu_memory(self) -> None:
        probe = probe_ollama()
        second = {**OllamaHandler.model, "name": "qwen3-copy", "model": "qwen3-copy"}
        probe["models"].append("qwen3-copy")
        probe["installed_models"].append(second)
        hardware = {"logical_cores": 12, "system_memory_bytes": 64 * 1024**3, "gpu_devices": [{"name": "fixture", "memory_bytes": 24 * 1024**3}], "gpu_memory_bytes": 24 * 1024**3}
        plan = plan_ollama_inference(["qwen3", "qwen3-copy"], context_length=4096, concurrency=2, runtime_probe=probe, hardware_probe=hardware)
        self.assertTrue(plan["supported"])
        self.assertEqual(plan["memory_source"], "gpu")
        self.assertEqual(plan["concurrency"], 2)
        self.assertEqual(plan["model_estimates"][0]["context_bytes"], 2 * 4096 * 256 * 1024)

    def test_profile_refuses_missing_models_and_memory_overcommit(self) -> None:
        probe = probe_ollama()
        low_memory = {"logical_cores": 8, "system_memory_bytes": 2 * 1024**3, "gpu_devices": [], "gpu_memory_bytes": 0}
        missing = plan_ollama_inference(["missing"], runtime_probe=probe, hardware_probe=low_memory)
        self.assertIn("FR-RUNTIME-OLLAMA-MODEL-NOT-INSTALLED", missing["reasons"])
        overcommitted = plan_ollama_inference(["qwen3"], context_length=32768, runtime_probe=probe, hardware_probe=low_memory)
        self.assertIn("FR-INFERENCE-MEMORY-BUDGET", overcommitted["reasons"])
        self.assertFalse(overcommitted["supported"])

    def test_profile_falls_back_to_cpu_only_when_gpu_selection_is_automatic(self) -> None:
        probe = probe_ollama()
        hardware = {"logical_cores": 8, "system_memory_bytes": 32 * 1024**3, "gpu_devices": [{"name": "small", "memory_bytes": 2 * 1024**3}], "gpu_memory_bytes": 2 * 1024**3}
        fallback = plan_ollama_inference(["qwen3"], runtime_probe=probe, hardware_probe=hardware)
        self.assertTrue(fallback["supported"])
        self.assertTrue(fallback["automatic_cpu_fallback"])
        self.assertEqual(fallback["options"]["num_gpu"], 0)
        without_gpu = {**hardware, "gpu_devices": [], "gpu_memory_bytes": 0}
        explicit = plan_ollama_inference(["qwen3"], gpu_layers=20, runtime_probe=probe, hardware_probe=without_gpu)
        self.assertFalse(explicit["supported"])
        self.assertIn("FR-INFERENCE-GPU-NOT-DETECTED", explicit["reasons"])

    def test_nonlocal_ollama_endpoint_is_rejected(self) -> None:
        with patch.dict(os.environ, {"OLLAMA_HOST": "https://example.com"}):
            probe = probe_ollama()
        self.assertFalse(probe["available"])
        self.assertIn("NONLOCAL", probe["detail"])


if __name__ == "__main__":
    unittest.main()
