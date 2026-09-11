from db import get_user_connection

def get_database_schema(conn):
    schema = {}

    with conn.cursor() as cur:

        # Get tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)

        tables = [row[0] for row in cur.fetchall()]

        for table in tables:

            schema[table] = {
                "columns": [],
                "primary_keys": [],
                "foreign_keys": []
            }

            # Get columns
            cur.execute("""
                SELECT
                    column_name,
                    data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position;
            """, (table,))

            for column_name, data_type in cur.fetchall():
                schema[table]["columns"].append({
                    "name": column_name,
                    "type": data_type
                })

            # Get primary keys
            cur.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                    AND tc.table_name = kcu.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = %s
                ORDER BY kcu.ordinal_position;
            """, (table,))

            schema[table]["primary_keys"] = [
                row[0] for row in cur.fetchall()
            ]

            # Get foreign keys
            cur.execute("""
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = %s;
            """, (table,))

            schema[table]["foreign_keys"] = [
                {
                    "column": row[0],
                    "references_table": row[1],
                    "references_column": row[2]
                }
                for row in cur.fetchall()
            ]

    return schema



# ---------------------------------------------------------
# Test
# ---------------------------------------------------------

if __name__ == "__main__":

    schema = get_database_schema()

    for table_name, table_info in schema.items():

        print(f"\nTABLE: {table_name}")

        print("  Columns:")

        for column in table_info["columns"]:
            print(
                f"    - {column['name']} "
                f"({column['type']})"
            )

        print("  Primary Keys:")

        for pk in table_info["primary_keys"]:
            print(f"    - {pk}")

        print("  Foreign Keys:")

        for fk in table_info["foreign_keys"]:
            print(
                f"    - {fk['column']} "
                f"→ {fk['references_table']}."
                f"{fk['references_column']}"
            )