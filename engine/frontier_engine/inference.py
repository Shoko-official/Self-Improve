"""Capability-driven local inference planning."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from typing import Any

from frontier_engine.runtimes import probe_ollama


def hardware_memory() -> dict[str, object]:
    logical_cores = os.cpu_count() or 1
    system_bytes = _system_memory_bytes()
    gpu_devices = _nvidia_memory()
    return {
        "logical_cores": logical_cores,
        "system_memory_bytes": system_bytes,
        "gpu_devices": gpu_devices,
        "gpu_memory_bytes": sum(int(device["memory_bytes"]) for device in gpu_devices),
    }


def plan_ollama_inference(models: list[str], context_length: int | None = None, cpu_threads: int | None = None, batch_size: int | None = None, gpu_layers: int | None = None, keep_alive: str = "15m", concurrency: int = 1, runtime_probe: dict[str, Any] | None = None, hardware_probe: dict[str, object] | None = None) -> dict[str, object]:
    requested_models = list(dict.fromkeys(model.strip() for model in models if model.strip()))
    if not requested_models:
        raise ValueError("At least one model is required.")
    if concurrency < 1 or concurrency > 16:
        raise ValueError("Concurrency must be between 1 and 16.")
    if context_length is not None and not 512 <= context_length <= 262144:
        raise ValueError("Context length must be between 512 and 262144.")
    if cpu_threads is not None and cpu_threads < 1:
        raise ValueError("CPU threads must be positive.")
    if batch_size is not None and not 1 <= batch_size <= 2048:
        raise ValueError("Batch size must be between 1 and 2048.")
    if gpu_layers is not None and gpu_layers < 0:
        raise ValueError("GPU layers must be zero or positive when explicitly set.")
    if not keep_alive.strip():
        raise ValueError("Keep-alive must not be empty.")

    runtime = runtime_probe or probe_ollama()
    hardware = hardware_probe or hardware_memory()
    installed = {str(item["model"]): item for item in runtime.get("installed_models", []) if isinstance(item, dict) and item.get("model")}
    missing = [model for model in requested_models if model not in installed]
    gpu_memory = int(hardware.get("gpu_memory_bytes") or 0)
    system_memory = int(hardware.get("system_memory_bytes") or 0)
    selected_context = context_length or (32768 if gpu_memory >= 24 * 1024**3 else 4096)
    selected_threads = cpu_threads or max(1, min(int(hardware.get("logical_cores") or 1), 16))
    selected_batch = batch_size or min(512, max(32, selected_context // 8))
    model_estimates = []
    for model in requested_models:
        model_size = int(installed.get(model, {}).get("size") or 0)
        context_bytes = selected_context * 256 * 1024 * concurrency
        estimated = int(model_size * 1.15) + context_bytes
        model_estimates.append({"model": model, "model_bytes": model_size, "context_bytes": context_bytes, "estimated_working_set_bytes": estimated})
    estimated_total = sum(int(item["estimated_working_set_bytes"]) for item in model_estimates)
    gpu_requested = gpu_layers is not None and gpu_layers > 0
    gpu_automatic = gpu_layers is None and gpu_memory > 0
    automatic_cpu_fallback = gpu_automatic and estimated_total > int(gpu_memory * 0.85)
    use_gpu_budget = gpu_requested or (gpu_automatic and not automatic_cpu_fallback)
    available_memory = gpu_memory if use_gpu_budget else system_memory
    memory_budget = int(available_memory * 0.85)
    reasons: list[str] = []
    if not runtime.get("available"):
        reasons.append(str(runtime.get("reason") or "FR-RUNTIME-OLLAMA-UNAVAILABLE"))
    if missing:
        reasons.append("FR-RUNTIME-OLLAMA-MODEL-NOT-INSTALLED")
    if gpu_requested and gpu_memory <= 0:
        reasons.append("FR-INFERENCE-GPU-NOT-DETECTED")
    if available_memory <= 0:
        reasons.append("FR-INFERENCE-MEMORY-UNKNOWN")
    elif estimated_total > memory_budget:
        reasons.append("FR-INFERENCE-MEMORY-BUDGET")
    options: dict[str, int] = {"num_ctx": selected_context, "num_batch": selected_batch, "num_thread": selected_threads}
    if gpu_layers is not None:
        options["num_gpu"] = gpu_layers
    elif automatic_cpu_fallback:
        options["num_gpu"] = 0
    return {
        "runtime": "ollama",
        "supported": not reasons,
        "models": requested_models,
        "missing_models": missing,
        "options": options,
        "keep_alive": keep_alive,
        "concurrency": concurrency,
        "estimated_working_set_bytes": estimated_total,
        "memory_budget_bytes": memory_budget,
        "memory_source": "gpu" if use_gpu_budget else "system",
        "automatic_cpu_fallback": automatic_cpu_fallback,
        "model_estimates": model_estimates,
        "reasons": reasons,
        "hardware": hardware,
        "runtime_probe": runtime,
        "estimate_basis": "model size plus 15 percent and a conservative per-token context allowance",
    }


def _system_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong), ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong), ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong), ("available_extended_virtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.available_physical)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_AVPHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        try:
            return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
        except (AttributeError, OSError, ValueError):
            return None


def _nvidia_memory() -> list[dict[str, object]]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return []
    try:
        result = subprocess.run([executable, "--query-gpu=name,memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        return []
    devices = []
    for line in result.stdout.splitlines():
        name, separator, memory = line.rpartition(",")
        if separator and memory.strip().isdigit():
            devices.append({"name": name.strip(), "memory_bytes": int(memory.strip()) * 1024**2})
    return devices
