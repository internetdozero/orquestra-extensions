"""Local SQLite idea vault and inter-agent blackboard for MCP."""

from .store import Database, default_db_path, get_database

__version__ = "0.1.0"
__all__ = ["Database", "default_db_path", "get_database", "__version__"]
