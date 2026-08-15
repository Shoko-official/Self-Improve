"""Minimal stdio JSON-RPC MCP server for trusted local capability inspection."""
from __future__ import annotations
import json, sys
from typing import Any
from frontier_engine.__main__ import doctor
from frontier_engine.scientific_registry import connector_catalog, skill_catalog

_READ_ONLY = {"readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":False}
TOOLS=[
 {"name":"frontier_get_capability_report","title":"Frontier capability report","description":"Read the local Frontier engine and host capability report.","inputSchema":{"type":"object","properties":{},"additionalProperties":False},"outputSchema":{"type":"object","properties":{"status":{"type":"string"},"host":{"type":"object"}},"required":["status","host"]},"annotations":_READ_ONLY},
 {"name":"frontier_list_scientific_connectors","title":"Scientific connector registry","description":"Read local connector descriptors and their network boundaries.","inputSchema":{"type":"object","properties":{},"additionalProperties":False},"outputSchema":{"type":"object","properties":{"connectors":{"type":"array"}},"required":["connectors"]},"annotations":_READ_ONLY},
 {"name":"frontier_list_scientific_skills","title":"Scientific skill registry","description":"Read local scientific skill descriptors and their boundaries.","inputSchema":{"type":"object","properties":{},"additionalProperties":False},"outputSchema":{"type":"object","properties":{"skills":{"type":"array"}},"required":["skills"]},"annotations":_READ_ONLY},
]
def handle(request:dict[str,Any])->dict[str,Any]:
 identifier=request.get("id"); method=request.get("method")
 if method=="initialize": return _result(identifier,{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"frontier-local","version":"0.1.0"}})
 if method=="tools/list": return _result(identifier,{"tools":TOOLS})
 if method=="tools/call":
  params=request.get("params",{});
  name=params.get("name")
  if name not in {"frontier_get_capability_report","frontier_list_scientific_connectors","frontier_list_scientific_skills"}: return _error(identifier,-32602,"Unknown tool")
  if params.get("arguments",{}): return _error(identifier,-32602,"Tool accepts no arguments")
  result = doctor() if name == "frontier_get_capability_report" else {"connectors": connector_catalog()} if name == "frontier_list_scientific_connectors" else {"skills": skill_catalog()}
  return _result(identifier,{"content":[{"type":"text","text":json.dumps(result,sort_keys=True)}],"structuredContent":result,"isError":False})
 return _error(identifier,-32601,"Method not found")
def _result(identifier:object,result:dict[str,Any])->dict[str,Any]: return {"jsonrpc":"2.0","id":identifier,"result":result}
def _error(identifier:object,code:int,message:str)->dict[str,Any]: return {"jsonrpc":"2.0","id":identifier,"error":{"code":code,"message":message}}
def main()->None:
 for line in sys.stdin:
  try: print(json.dumps(handle(json.loads(line))),flush=True)
  except json.JSONDecodeError: print(json.dumps(_error(None,-32700,"Parse error")),flush=True)
if __name__=="__main__": main()
