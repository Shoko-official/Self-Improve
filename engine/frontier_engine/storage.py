"""Scoped object-storage profiles and integrity-preserving transfer manifests."""

from __future__ import annotations
import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse
import urllib.error
import urllib.request

StorageKind=Literal["s3","s3_compatible","gcs","azure_blob"]
@dataclass(frozen=True)
class StorageProfile: kind:StorageKind; endpoint:str; container:str; prefix:str; credential_handle:str
@dataclass(frozen=True)
class TransferManifest: profile:StorageProfile; object_key:str; bytes:int; sha256:str; operation:Literal["import","export","delete"]; egress_bytes:int; content:bytes=b""
class StorageApprovalRequired(PermissionError): pass

def probe_remote_storage(profile:StorageProfile, approved:bool, timeout_seconds:float=10.0)->dict[str,object]:
 if profile.kind not in {"s3","s3_compatible","gcs","azure_blob"}: raise ValueError("FR-STORAGE-KIND: unsupported storage kind")
 if not profile.endpoint.startswith(("https://","http://")): raise ValueError("FR-STORAGE-ENDPOINT: remote probe requires an HTTP endpoint")
 if not approved: raise StorageApprovalRequired("FR-STORAGE-EGRESS-APPROVAL: remote connectivity requires explicit approval")
 if timeout_seconds <= 0: raise ValueError("FR-STORAGE-TIMEOUT: timeout must be positive")
 request=urllib.request.Request(profile.endpoint, method="HEAD")
 try:
  with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
   return {"state":"reachable","kind":profile.kind,"endpoint":profile.endpoint,"status":response.status}
 except urllib.error.HTTPError as error:
  return {"state":"reachable","kind":profile.kind,"endpoint":profile.endpoint,"status":error.code,"authentication_required":error.code in {401,403}}
 except (urllib.error.URLError, TimeoutError) as error:
  return {"state":"unreachable","kind":profile.kind,"endpoint":profile.endpoint,"code":"FR-STORAGE-PROBE-FAILED","detail":str(error)}

def build_manifest(profile:StorageProfile, object_key:str, content:bytes, operation:Literal["import","export","delete"], egress_bytes:int=0)->TransferManifest:
 if not object_key.startswith(profile.prefix): raise ValueError("FR-STORAGE-SCOPE: object is outside granted prefix")
 if operation == "delete" and content: raise ValueError("FR-STORAGE-DELETE: delete manifest cannot carry content")
 return TransferManifest(profile,object_key,len(content),hashlib.sha256(content).hexdigest(),operation,egress_bytes,content)
def authorize_transfer(manifest:TransferManifest, approved:bool)->None:
 if manifest.operation in {"export","delete"} and not approved: raise StorageApprovalRequired("FR-STORAGE-APPROVAL: write or delete requires explicit approval")

def execute_local_transfer(manifest:TransferManifest, approved:bool)->dict[str,object]:
 if not manifest.profile.endpoint.startswith("file://"): raise ValueError("FR-STORAGE-ENDPOINT: local adapter requires a file:// endpoint")
 authorize_transfer(manifest, approved)
 parsed=urlparse(manifest.profile.endpoint); path_text=unquote(parsed.path); path_text=path_text[1:] if re.match(r"^/[A-Za-z]:/", path_text) else path_text; root=Path(path_text).resolve(); target=(root / manifest.object_key).resolve()
 if not target.is_relative_to(root) or not manifest.object_key.startswith(manifest.profile.prefix): raise ValueError("FR-STORAGE-SCOPE: object is outside granted prefix")
 if manifest.operation == "export":
  target.parent.mkdir(parents=True, exist_ok=True); temporary=target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
  try:
   temporary.write_bytes(manifest.content); os.replace(temporary, target)
  finally:
   if temporary.exists(): temporary.unlink()
  data=target.read_bytes()
 elif manifest.operation == "import":
  if not target.exists(): raise FileNotFoundError("FR-STORAGE-OBJECT-NOT-FOUND")
  data=target.read_bytes()
 else:
  if not target.exists(): raise FileNotFoundError("FR-STORAGE-OBJECT-NOT-FOUND")
  target.unlink(); return {"state":"succeeded","operation":"delete","object_key":manifest.object_key}
 if len(data) != manifest.bytes or hashlib.sha256(data).hexdigest() != manifest.sha256: raise ValueError("FR-STORAGE-INTEGRITY: checksum or byte count mismatch")
 result={"state":"succeeded","operation":manifest.operation,"object_key":manifest.object_key,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
 if manifest.operation == "import": result["content"]=data
 return result
