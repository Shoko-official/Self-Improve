"""Durable automation definitions with dry-run-first execution history."""
from __future__ import annotations
import sqlite3,uuid
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class AutomationRun: automation_id:str; mode:str; state:str; external_effects:bool
class AutomationStore:
 def __init__(self,database:Path)->None:
  self.connection=sqlite3.connect(database);self.connection.row_factory=sqlite3.Row;self.connection.executescript("CREATE TABLE IF NOT EXISTS automations(id TEXT PRIMARY KEY,name TEXT NOT NULL,definition TEXT NOT NULL);CREATE TABLE IF NOT EXISTS automation_runs(id TEXT PRIMARY KEY,automation_id TEXT NOT NULL,mode TEXT NOT NULL,state TEXT NOT NULL,external_effects INTEGER NOT NULL);");self.connection.commit()
 def close(self)->None:self.connection.close()
 def create(self,name:str,definition:str)->str:
  identifier=str(uuid.uuid4());self.connection.execute("INSERT INTO automations VALUES(?,?,?)",(identifier,name,definition));self.connection.commit();return identifier
 def run(self,automation_id:str,dry_run:bool=True,external_approved:bool=False)->AutomationRun:
  if self.connection.execute("SELECT 1 FROM automations WHERE id=?",(automation_id,)).fetchone() is None:raise KeyError("Automation not found")
  external="external" in self.connection.execute("SELECT definition FROM automations WHERE id=?",(automation_id,)).fetchone()[0]
  if external and not dry_run and not external_approved:raise PermissionError("FR-AUTO-APPROVAL: external effects require explicit approval")
  mode="dry_run" if dry_run else "execute";state="simulated" if dry_run else "completed";self.connection.execute("INSERT INTO automation_runs VALUES(?,?,?,?,?)",(str(uuid.uuid4()),automation_id,mode,state,int(external)));self.connection.commit();return AutomationRun(automation_id,mode,state,external)
 def history(self,automation_id:str)->tuple[AutomationRun,...]:return tuple(AutomationRun(row["automation_id"],row["mode"],row["state"],bool(row["external_effects"]))for row in self.connection.execute("SELECT * FROM automation_runs WHERE automation_id=?",(automation_id,)))
