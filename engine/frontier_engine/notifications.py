"""Durable, lock-screen-safe notifications for Frontier activity."""
from __future__ import annotations
import sqlite3,uuid
from dataclasses import dataclass
from datetime import UTC,datetime
from pathlib import Path
@dataclass(frozen=True)
class Notification: id:str; source:str; severity:str; title:str; body:str; deep_link:str; acknowledged_at:str|None
class NotificationStore:
 def __init__(self,database:Path)->None:
  self.connection=sqlite3.connect(database);self.connection.row_factory=sqlite3.Row;self.connection.execute("CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,source TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,deep_link TEXT NOT NULL,acknowledged_at TEXT)");self.connection.commit()
 def close(self)->None:self.connection.close()
 def create(self,source:str,severity:str,title:str,body:str,deep_link:str)->str:
  if severity not in {"info","warning","error"}:raise ValueError("Invalid notification severity")
  if any(token in body.lower() for token in ("bearer ","api_key","password=")):raise ValueError("Notification body may not contain sensitive content")
  identifier=str(uuid.uuid4());self.connection.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,NULL)",(identifier,source,severity,title,body,deep_link));self.connection.commit();return identifier
 def pending(self)->tuple[Notification,...]:return tuple(_row(row)for row in self.connection.execute("SELECT * FROM notifications WHERE acknowledged_at IS NULL"))
 def acknowledge(self,identifier:str)->None:
  if self.connection.execute("UPDATE notifications SET acknowledged_at=? WHERE id=? AND acknowledged_at IS NULL",(datetime.now(UTC).isoformat(),identifier)).rowcount!=1:raise KeyError("Pending notification not found")
  self.connection.commit()
def _row(row:sqlite3.Row)->Notification:return Notification(row["id"],row["source"],row["severity"],row["title"],row["body"],row["deep_link"],row["acknowledged_at"])
