"""Scoped object-storage profiles and integrity-preserving transfer manifests."""

from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Literal

StorageKind=Literal["s3","s3_compatible","gcs","azure_blob"]
@dataclass(frozen=True)
class StorageProfile: kind:StorageKind; endpoint:str; container:str; prefix:str; credential_handle:str
@dataclass(frozen=True)
class TransferManifest: profile:StorageProfile; object_key:str; bytes:int; sha256:str; operation:Literal["import","export","delete"]; egress_bytes:int
class StorageApprovalRequired(PermissionError): pass

def build_manifest(profile:StorageProfile, object_key:str, content:bytes, operation:Literal["import","export","delete"], egress_bytes:int=0)->TransferManifest:
 if not object_key.startswith(profile.prefix): raise ValueError("FR-STORAGE-SCOPE: object is outside granted prefix")
 if operation == "delete" and content: raise ValueError("FR-STORAGE-DELETE: delete manifest cannot carry content")
 return TransferManifest(profile,object_key,len(content),hashlib.sha256(content).hexdigest(),operation,egress_bytes)
def authorize_transfer(manifest:TransferManifest, approved:bool)->None:
 if manifest.operation in {"export","delete"} and not approved: raise StorageApprovalRequired("FR-STORAGE-APPROVAL: write or delete requires explicit approval")
