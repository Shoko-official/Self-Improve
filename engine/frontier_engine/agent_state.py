"""Inspectable, project-scoped agent plans, todos, and memories."""
from __future__ import annotations
import sqlite3, uuid
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class Todo: id:str; text:str; state:str
class AgentStateStore:
 def __init__(self,database:Path)->None:
  self.connection=sqlite3.connect(database);self.connection.row_factory=sqlite3.Row
  self.connection.executescript("CREATE TABLE IF NOT EXISTS plans(project_id TEXT PRIMARY KEY, content TEXT NOT NULL);CREATE TABLE IF NOT EXISTS todos(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,text TEXT NOT NULL,state TEXT NOT NULL);CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,content TEXT NOT NULL);CREATE TABLE IF NOT EXISTS tool_calls(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,tool_name TEXT NOT NULL,request TEXT NOT NULL,state TEXT NOT NULL,result TEXT NOT NULL);");self.connection.commit()
 def close(self)->None:self.connection.close()
 def set_plan(self,project_id:str,content:str)->None:self.connection.execute("INSERT INTO plans VALUES(?,?) ON CONFLICT(project_id) DO UPDATE SET content=excluded.content",(project_id,content));self.connection.commit()
 def plan(self,project_id:str)->str|None:
  row=self.connection.execute("SELECT content FROM plans WHERE project_id=?",(project_id,)).fetchone();return row[0] if row else None
 def add_todo(self,project_id:str,text:str)->str:
  identifier=str(uuid.uuid4());self.connection.execute("INSERT INTO todos VALUES(?,?,?,?)",(identifier,project_id,text,"pending"));self.connection.commit();return identifier
 def transition_todo(self,todo_id:str,state:str)->None:
  if state not in {"pending","in_progress","completed"}:raise ValueError("Invalid todo state")
  if self.connection.execute("UPDATE todos SET state=? WHERE id=?",(state,todo_id)).rowcount!=1:raise KeyError("Todo not found")
  self.connection.commit()
 def todos(self,project_id:str)->tuple[Todo,...]:return tuple(Todo(row["id"],row["text"],row["state"])for row in self.connection.execute("SELECT * FROM todos WHERE project_id=?",(project_id,)))
 def remember(self,project_id:str,content:str)->str:
  identifier=str(uuid.uuid4());self.connection.execute("INSERT INTO memories VALUES(?,?,?)",(identifier,project_id,content));self.connection.commit();return identifier
 def search_memory(self,project_id:str,term:str)->tuple[str,...]:return tuple(row[0] for row in self.connection.execute("SELECT content FROM memories WHERE project_id=? AND content LIKE ?",(project_id,f"%{term}%")))
 def forget(self,memory_id:str)->None:
  if self.connection.execute("DELETE FROM memories WHERE id=?",(memory_id,)).rowcount!=1:raise KeyError("Memory not found")
  self.connection.commit()
 def record_tool_call(self,project_id:str,tool_name:str,request:str,state:str,result:str)->str:
  identifier=str(uuid.uuid4());self.connection.execute("INSERT INTO tool_calls VALUES(?,?,?,?,?,?)",(identifier,project_id,tool_name,request,state,result));self.connection.commit();return identifier
 def tool_calls(self,project_id:str)->tuple[sqlite3.Row,...]:return tuple(self.connection.execute("SELECT * FROM tool_calls WHERE project_id=? ORDER BY rowid",(project_id,)))
