import uuid
from typing import Any


# Temporary in-memory connection store.
# Each connection gets a unique ID.
_connections: dict[str, dict[str, Any]] = {}


def create_connection(
    db_type: str,
    host: str,
    port: str,
    database: str,
    username: str,
    password: str,
) -> str:
    connection_id = str(uuid.uuid4())

    _connections[connection_id] = {
        "type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "password": password,
    }

    return connection_id


def get_connection(connection_id: str) -> dict[str, Any] | None:
    return _connections.get(connection_id)


def delete_connection(connection_id: str) -> bool:
    return _connections.pop(connection_id, None) is not None