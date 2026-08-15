"""Raw-sample benchmark records and transparent comparisons."""
from __future__ import annotations
import statistics
from dataclasses import dataclass
@dataclass(frozen=True)
class Sample: variant:str; cold:bool; latency_ms:float; throughput:float; peak_memory_mb:float
def summarize(samples:tuple[Sample,...],environment:dict[str,str])->dict[str,object]:
 if not samples:raise ValueError("At least one raw sample is required")
 if not environment:raise ValueError("Environment fingerprint is required")
 return {"environment":environment,"raw_samples":[sample.__dict__ for sample in samples],"variants":{variant:_metrics(tuple(sample for sample in samples if sample.variant==variant))for variant in sorted({sample.variant for sample in samples})}}
def compare(report:dict[str,object],left:str,right:str)->dict[str,float]:
 variants=report["variants"]
 if left not in variants or right not in variants:raise ValueError("Both variants must exist")
 a,b=variants[left],variants[right]
 return {"latency_delta_ms":b["mean_latency_ms"]-a["mean_latency_ms"],"throughput_delta":b["mean_throughput"]-a["mean_throughput"],"memory_delta_mb":b["mean_peak_memory_mb"]-a["mean_peak_memory_mb"]}
def _metrics(samples:tuple[Sample,...])->dict[str,float]:return {"mean_latency_ms":statistics.fmean(x.latency_ms for x in samples),"mean_throughput":statistics.fmean(x.throughput for x in samples),"mean_peak_memory_mb":statistics.fmean(x.peak_memory_mb for x in samples)}
