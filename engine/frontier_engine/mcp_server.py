"""Minimal stdio JSON-RPC MCP server for trusted local capability inspection."""
from __future__ import annotations
import json, sys
from typing import Any
from frontier_engine.__main__ import doctor

TOOLS=[{"name":"frontier_get_capability_report","title":"Frontier capability report","description":"Read the local Frontier engine and host capability report.","inputSchema":{"type":"object","properties":{},"additionalProperties":False},"outputSchema":{"type":"object","properties":{"status":{"type":"string"},"host":{"type":"object"}},"required":["status","host"]},"annotations":{"readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":False}}]
def handle(request:dict[str,Any])->dict[str,Any]:
 identifier=request.get("id"); method=request.get("method")
 if method=="initialize": return _result(identifier,{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"frontier-local","version":"0.1.0"}})
 if method=="tools/list": return _result(identifier,{"tools":TOOLS})
 if method=="tools/call":
  params=request.get("params",{});
  if params.get("name")!="frontier_get_capability_report": return _error(identifier,-32602,"Unknown tool")
  if params.get("arguments",{}): return _error(identifier,-32602,"Tool accepts no arguments")
  report=doctor(); return _result(identifier,{"content":[{"type":"text","text":json.dumps(report,sort_keys=True)}],"structuredContent":report,"isError":False})
 return _error(identifier,-32601,"Method not found")
def _result(identifier:object,result:dict[str,Any])->dict[str,Any]: return {"jsonrpc":"2.0","id":identifier,"result":result}
def _error(identifier:object,code:int,message:str)->dict[str,Any]: return {"jsonrpc":"2.0","id":identifier,"error":{"code":code,"message":message}}
def main()->None:
 for line in sys.stdin:
  try: print(json.dumps(handle(json.loads(line))),flush=True)
  except json.JSONDecodeError: print(json.dumps(_error(None,-32700,"Parse error")),flush=True)
if __name__=="__main__": main()
