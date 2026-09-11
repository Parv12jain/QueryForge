# db.py is the database connection layer 
# that allows our LangGraph nodes to communicate with PostgreSQL.
# LangGraph/Python
#        │
#        ▼
#    psycopg
#        │
#        ▼
# PostgreSQL Server
#        ▲
#        │
#     pgAdmin
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT"),
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}


def get_connection():
    return psycopg.connect(**DB_CONFIG)


if __name__ == "__main__":
    try:
        conn = get_connection()
        print("PostgreSQL connection successful!")

        conn.close()
        print("Connection closed.")

    except Exception as e:
        print("PostgreSQL connection failed!")
        print("Error:", e)

def get_user_connection(
    host,
    port,
    dbname,
    user,
    password
):
    return psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password
    )