from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from graph import graph
from typing import Any
from connection_manager import (
    create_connection,
    get_connection,
    delete_connection,
)
import psycopg
import traceback

from db import get_user_connection
from schema_inspector import get_database_schema

app = FastAPI(
    title="SQL Agent API",
    description="Natural language PostgreSQL query API",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://queryforge-1.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    connection_id: str = Field(..., min_length=1, max_length=100)

class ConnectionRequest(BaseModel):
    type: str = "PostgreSQL"
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)

class ConnectionIdRequest(BaseModel):
    connection_id: str = Field(..., min_length=1, max_length=100)
    

class QueryResponse(BaseModel):
    success: bool
    question: str
    sql: str
    sql_valid: bool | None
    results: list[dict[str, Any]]
    retry_count: int
    answer: str
    error: str

@app.get("/")
def root():
    return {
        "message" : "SQL Agent API is running"
    }

@app.get("/health")
def health():
    return {
        "status" : "healthy"
    }

@app.post("/connection/test")
def test_connection(request: ConnectionRequest):
    if request.type != "PostgreSQL":
        raise HTTPException(
            status_code=400,
            detail="Only PostgreSQL connections are currently supported."
        )

    try:
        conn = psycopg.connect(
            host=request.host,
            port=request.port,
            dbname=request.database,
            user=request.username,
            password=request.password,
            connect_timeout=5,
        )

        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user;")
            database, user = cursor.fetchone()

        conn.close()

        connection_id = create_connection(
            db_type=request.type,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
        )

        return {
            "success": True,
            "message": "Database connection successful.",
            "database": database,
            "user": user,
            "connection_id": connection_id,
        }

    except Exception as e:
        print(
            f"DATABASE CONNECTION FAILED: "
            f"{type(e).__name__}: {e}"
        )
        raise HTTPException(
            status_code=400,
            detail="Could not connect to the database. Check the connection details."
        )

@app.post("/connection/schema")
def get_connection_schema(request: ConnectionIdRequest):
    connection = get_connection(request.connection_id)

    if connection is None:
        raise HTTPException(
            status_code=404,
            detail="Connection not found or expired."
        )

    conn = None

    try:
        conn = get_user_connection(
            host=connection["host"],
            port=connection["port"],
            dbname=connection["database"],
            user=connection["username"],
            password=connection["password"],
        )

        schema = get_database_schema(conn)

        return {
            "success": True,
            "database": connection["database"],
            "schema": schema,
        }

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read the database schema."
        )

    finally:
        if conn is not None:
            conn.close()

@app.post("/connection/disconnect")
def disconnect_connection(request: ConnectionIdRequest):
    deleted = delete_connection(request.connection_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Connection not found."
        )

    return {
        "success": True,
        "message": "Connection disconnected successfully."
    }

@app.post(
    "/query",
    response_model=QueryResponse,
    responses={
        429: {
            "description": "Gemini API quota exceeded"
        },
        500: {
            "description": "Internal server error"
        }
    }
)
def query_database(request: QueryRequest):
    connection = get_connection(request.connection_id)

    if connection is None:
        raise HTTPException(
            status_code=404,
            detail="Connection not found or expired."
        )

    try:
        result = graph.invoke({
            "user_query": request.question,
            "db_host": connection["host"],
            "db_port": connection["port"],
            "db_name": connection["database"],
            "db_user": connection["username"],
            "db_password": connection["password"],
            "retry_count": 0,
            "max_retries": 3,
        })

        return {
            "success": not bool(result.get("error")),
            "question": request.question,
            "sql": result.get("generated_sql", ""),
            "sql_valid": result.get("sql_valid"),
            "results": result.get("query_result", []),
            "retry_count": result.get("retry_count", 0),
            "answer": result.get("final_answer", ""),
            "error": result.get("error", ""),
        }

    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower() or "rate limit" in str(e).lower():
            raise HTTPException(
                status_code=429,
                detail="Gemini API quota exceeded. Please try again after the quota resets."
            )
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="The SQL agent could not complete the request."
        )   