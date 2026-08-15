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
from urllib.parse import quote
import urllib.error
import urllib.request
import json
import xml.etree.ElementTree as ET
from frontier_engine.s3_signing import S3Credentials, sign_s3_request

StorageKind=Literal["s3","s3_compatible","gcs","azure_blob"]
@dataclass(frozen=True)
class StorageProfile: kind:StorageKind; endpoint:str; container:str; prefix:str; credential_handle:str
@dataclass(frozen=True)
class TransferManifest: profile:StorageProfile; object_key:str; bytes:int; sha256:str; operation:Literal["import","export","delete"]; egress_bytes:int; content:bytes=b""
class StorageApprovalRequired(PermissionError): pass

def execute_s3_signed_transfer(manifest:TransferManifest, region:str, credentials:S3Credentials, approved:bool, timeout_seconds:float=30.0)->dict[str,object]:
 if manifest.profile.kind not in {"s3","s3_compatible"}: raise ValueError("FR-S3-TRANSFER-KIND: S3-compatible profile required")
 endpoint=manifest.profile.endpoint.rstrip("/")
 if timeout_seconds <= 0: raise ValueError("FR-S3-TRANSFER-TIMEOUT: timeout must be positive")
 authorize_transfer(manifest, approved)
 if not endpoint.startswith("https://"): raise ValueError("FR-S3-TRANSFER-HTTPS: signed transfers require HTTPS")
 if not manifest.object_key.startswith(manifest.profile.prefix): raise ValueError("FR-STORAGE-SCOPE: object is outside granted prefix")
 url=f"{endpoint}/{quote(manifest.profile.container, safe='-_.~')}/{quote(manifest.object_key, safe='/~-_.')}"
 method={"import":"GET","export":"PUT","delete":"DELETE"}[manifest.operation]
 signed=sign_s3_request(method, url, region, credentials, payload=manifest.content)
 request=urllib.request.Request(url, data=manifest.content if method == "PUT" else None, method=method, headers=signed.headers)
 try:
  with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
   data=response.read() if method == "GET" else b""
 except urllib.error.HTTPError as error:
  raise ValueError(f"FR-S3-TRANSFER-HTTP:{error.code}") from error
 except (urllib.error.URLError, TimeoutError) as error:
  raise ValueError(f"FR-S3-TRANSFER-NETWORK:{error}") from error
 if method == "GET" and (len(data) != manifest.bytes or hashlib.sha256(data).hexdigest() != manifest.sha256): raise ValueError("FR-STORAGE-INTEGRITY: checksum or byte count mismatch")
 result={"state":"succeeded","operation":manifest.operation,"object_key":manifest.object_key,"bytes":len(data) if method == "GET" else manifest.bytes,"sha256":hashlib.sha256(data if method == "GET" else manifest.content).hexdigest()}
 if method == "GET": result["content"]=data
 return result

def list_presigned_objects(profile:StorageProfile, presigned_url:str, approved:bool, max_bytes:int=1_000_000, timeout_seconds:float=30.0)->dict[str,object]:
 if profile.kind not in {"s3","s3_compatible","gcs","azure_blob"}: raise ValueError("FR-STORAGE-KIND: unsupported storage kind")
 parsed=urlparse(presigned_url); profile_host=urlparse(profile.endpoint).hostname
 if parsed.scheme not in {"https","http"} or not parsed.query: raise ValueError("FR-STORAGE-PRESIGNED-URL: a signed query URL is required")
 if parsed.username or parsed.password or (profile_host and parsed.hostname != profile_host): raise ValueError("FR-STORAGE-PRESIGNED-URL: URL host or embedded credentials are invalid")
 if max_bytes <= 0 or timeout_seconds <= 0: raise ValueError("FR-STORAGE-LIMIT: limits must be positive")
 if not approved: raise StorageApprovalRequired("FR-STORAGE-EGRESS-APPROVAL: listing requires explicit approval")
 try:
  with urllib.request.urlopen(urllib.request.Request(presigned_url, method="GET"), timeout=timeout_seconds) as response:
   payload=response.read(max_bytes+1)
 except urllib.error.HTTPError as error:
  raise ValueError(f"FR-STORAGE-REMOTE-HTTP:{error.code}") from error
 except (urllib.error.URLError, TimeoutError) as error:
  raise ValueError(f"FR-STORAGE-REMOTE-NETWORK:{error}") from error
 if len(payload) > max_bytes: raise ValueError("FR-STORAGE-LIST-TOO-LARGE")
 objects:list[dict[str,object]]=[]
 try:
  parsed_json=json.loads(payload)
  entries=parsed_json.get("Contents", parsed_json.get("objects", [])) if isinstance(parsed_json, dict) else []
  if isinstance(entries, list):
   for entry in entries:
    if isinstance(entry, dict) and isinstance(entry.get("Key", entry.get("key")), str):
     key=entry.get("Key", entry.get("key"));
     if key.startswith(profile.prefix): objects.append({"key":key,"size":entry.get("Size",entry.get("size")),"etag":entry.get("ETag",entry.get("etag"))})
 except (json.JSONDecodeError, AttributeError):
  try:
   root=ET.fromstring(payload)
   for item in root.iter():
    if item.tag.rsplit("}",1)[-1] == "Contents":
     values={child.tag.rsplit("}",1)[-1]:child.text for child in item}
     key=values.get("Key")
     if key and key.startswith(profile.prefix): objects.append({"key":key,"size":int(values["Size"]) if values.get("Size","").isdigit() else None,"etag":values.get("ETag")})
  except (ET.ParseError, ValueError) as error:
   raise ValueError("FR-STORAGE-LIST-FORMAT") from error
 return {"state":"succeeded","kind":profile.kind,"prefix":profile.prefix,"objects":objects,"count":len(objects)}

def execute_presigned_transfer(manifest:TransferManifest, presigned_url:str, approved:bool, timeout_seconds:float=30.0)->dict[str,object]:
 if manifest.profile.kind not in {"s3","s3_compatible","gcs","azure_blob"}: raise ValueError("FR-STORAGE-KIND: unsupported storage kind")
 parsed=urlparse(presigned_url)
 profile_host=urlparse(manifest.profile.endpoint).hostname
 if parsed.scheme not in {"https","http"} or not parsed.query: raise ValueError("FR-STORAGE-PRESIGNED-URL: a signed query URL is required")
 if parsed.username or parsed.password or (profile_host and parsed.hostname != profile_host): raise ValueError("FR-STORAGE-PRESIGNED-URL: URL host or embedded credentials are invalid")
 if timeout_seconds <= 0: raise ValueError("FR-STORAGE-TIMEOUT: timeout must be positive")
 authorize_transfer(manifest, approved)
 methods={"export":"PUT","import":"GET","delete":"DELETE"}; method=methods[manifest.operation]
 request=urllib.request.Request(presigned_url, data=manifest.content if method == "PUT" else None, method=method)
 if method == "PUT": request.add_header("Content-Type","application/octet-stream")
 try:
  with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
   data=response.read() if method == "GET" else b""
 except urllib.error.HTTPError as error:
  raise ValueError(f"FR-STORAGE-REMOTE-HTTP:{error.code}") from error
 except (urllib.error.URLError, TimeoutError) as error:
  raise ValueError(f"FR-STORAGE-REMOTE-NETWORK:{error}") from error
 if method == "GET" and (len(data) != manifest.bytes or hashlib.sha256(data).hexdigest() != manifest.sha256): raise ValueError("FR-STORAGE-INTEGRITY: checksum or byte count mismatch")
 result={"state":"succeeded","operation":manifest.operation,"object_key":manifest.object_key,"bytes":len(data) if method == "GET" else manifest.bytes,"sha256":hashlib.sha256(data if method == "GET" else manifest.content).hexdigest()}
 if method == "GET": result["content"]=data
 return result

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
