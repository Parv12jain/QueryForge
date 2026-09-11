import os
import json

from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from state import AgentState
from schema_inspector import get_database_schema
from db import get_connection, get_user_connection

load_dotenv()


def extract_llm_text(response):
    """
    Extract text safely from LangChain LLM responses.

    Supports both:
    - string content
    - list-based content blocks
    """

    content = response.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for block in content:

            if isinstance(block, str):
                text_parts.append(block)

            elif isinstance(block, dict):
                text = block.get("text")

                if isinstance(text, str):
                    text_parts.append(text)

        return "".join(text_parts).strip()

    return str(content).strip()


# ---------------------------------------------------------
# LLM
# ---------------------------------------------------------

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0
)

def check_intent_node(state: AgentState):
    query = state["user_query"].upper()

    destructive_keywords = [
        "DELETE",
        "UPDATE",
        "INSERT",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE",
        "GRANT",
        "REVOKE"
    ]

    for keyword in destructive_keywords:
        if keyword in query:
            return {
                "user_intent": "destructive",
                "error": f"Destructive operation detected: {keyword}"
            }

    return {
        "user_intent": "read_only",
        "error": ""
    }

# ---------------------------------------------------------
# Schema Node
# ---------------------------------------------------------

def get_schema_node(state: AgentState):
    conn = None

    try:
        conn = get_user_connection(
            host=state["db_host"],
            port=state["db_port"],
            dbname=state["db_name"],
            user=state["db_user"],
            password=state["db_password"]
        )

        schema = get_database_schema(conn)

        return {
            "schema": schema,
            "error": ""
        }

    except Exception as e:
        return {
            "schema": {},
            "error": str(e)
        }

    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------
# SQL Generation Node
# ---------------------------------------------------------

def generate_sql_node(state: AgentState):

    user_query = state["user_query"]
    schema = state["schema"]

    schema_text = json.dumps(
        schema,
        indent=2
    )

    prompt = f"""
You are an expert PostgreSQL SQL generator.

Your job is to convert the user's natural-language question into
one correct, executable PostgreSQL SQL query.

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{user_query}

RULES:

1. Understand the user's intent before generating SQL.

2. Use ONLY tables and columns that exist in the provided database schema.

3. Use the relationships between tables when a JOIN is required.
   Prefer explicit JOIN ... ON conditions.

4. For calculations:
   - Use COUNT for counts.
   - Use SUM for totals.
   - Use AVG for averages.
   - Use MAX/MIN when finding highest or lowest values.
   - Use GROUP BY when calculating values for each group.

5. When the user asks for the "top", "highest", or "most",
   use ORDER BY with LIMIT when appropriate.

6. When the user asks for the "lowest", "least", or "bottom",
   use ORDER BY in ascending order with LIMIT when appropriate.

7. When filtering grouped/aggregated results,
   use HAVING instead of WHERE.

8. Use table aliases when they make joins or column references clearer.

9. Qualify columns such as id when multiple tables could contain
   columns with the same name.

10. Generate PostgreSQL-compatible SQL.

11. Do not invent tables, columns, relationships, or values.

12. Do not assume information that is not present in the schema.

COMPLEX QUERY GUIDANCE:

- If the question requires information from multiple tables,
  determine the correct relationship from the schema and use JOIN.

- If the question asks for a total, average, count, highest,
  lowest, or similar calculation, use the appropriate aggregate
  function.

- If the calculation is required for each customer, product,
  category, or other group, use GROUP BY.

- If the user asks for conditions on an aggregate result,
  use HAVING.

- If multiple tables contain columns with the same name,
  qualify the column with its table alias.

- If the user asks for the top N or bottom N results,
  use ORDER BY together with LIMIT.

- Do not use unnecessary joins or aggregations.

EXAMPLES OF INTENT:

User: "Show each customer and their total order amount."
Pattern: JOIN + SUM + GROUP BY.

User: "Which customer has spent the most?"
Pattern: JOIN + SUM + GROUP BY + ORDER BY + LIMIT.

User: "Show customers whose total spending is above 5000."
Pattern: JOIN + SUM + GROUP BY + HAVING.

User: "Show the top 3 customers by number of orders."
Pattern: JOIN + COUNT + GROUP BY + ORDER BY + LIMIT.

User: "What is the average order amount for each customer?"
Pattern: JOIN + AVG + GROUP BY.

AMBIGUOUS QUESTION HANDLING:

- Use the database schema to resolve ambiguity whenever possible.

- If a column exists in multiple tables, determine which table
  is intended from the wording and the tables relevant to the question.

- If multiple tables are required and their relationship is available
  in the schema, use that relationship rather than guessing.

- If the user refers to "customers", prefer the customers table
  when that table exists.

- If the user refers to "orders", prefer the orders table
  when that table exists.

- If the user uses words such as "their", "each", or "those",
  use the surrounding context and table relationships to determine
  the intended entity.

- If a question asks for a value such as "highest", "lowest",
  "most", or "least", determine the relevant numeric or measurable
  column from the schema.

- Never invent a column or table to resolve ambiguity.

- Never silently choose an unrelated table just because it contains
  a similarly named column.

- When the user's intent can be reasonably determined from the schema,
  generate the most appropriate SQL query.

- If the request is genuinely impossible to interpret from the
  question and schema, do not invent information. Generate a safe
  read-only query only when a reasonable interpretation exists.

13. Return ONLY the SQL query.
    Do not include markdown fences.
    Do not include explanations.

14. Generate ONLY read-only SELECT queries.
    WITH queries are allowed only when the final statement is SELECT.

15. Never generate:
    INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE,
    GRANT, REVOKE, or other write/destructive statements.

SQL QUERY:
"""

    response = llm.invoke(prompt)

    generated_sql = extract_llm_text(response)

    return {
        "generated_sql": generated_sql,
        "error": ""
    }



def validate_tables_against_schema(expression, schema):

    allowed_tables = set(schema.keys())

    # Get CTE names
    cte_names = {
        cte.alias_or_name
        for cte in expression.find_all(exp.CTE)
    }

    for table in expression.find_all(exp.Table):

        table_name = table.name

        # Ignore CTE names because they are not real database tables
        if table_name in cte_names:
            continue

        # Check actual database tables
        if table_name not in allowed_tables:
            return {
                "valid": False,
                "error": (
                    f"Table '{table_name}' "
                    f"does not exist in the database schema."
                )
            }

    return {
        "valid": True,
        "error": ""
    }

def validate_columns_against_schema(expression, schema):
    table_columns = {
        table_name: {
            column["name"]
            for column in table_info.get("columns", [])
        }
        for table_name, table_info in schema.items()
    }

    for select_expression in expression.find_all(exp.Select):

        query_tables = set()
        table_aliases = {}

        # -----------------------------------------------------
        # Find physical tables used by this SELECT
        # -----------------------------------------------------
        for table in select_expression.find_all(exp.Table):

            table_name = table.name

            if table_name not in table_columns:
                continue

            # Ignore tables belonging to nested SELECTs.
            parent_select = table.find_ancestor(exp.Select)

            if parent_select is not select_expression:
                continue

            query_tables.add(table_name)

            table_aliases[table_name] = table_name

            if table.alias:
                table_aliases[table.alias] = table_name

        # -----------------------------------------------------
        # Find SELECT aliases
        # -----------------------------------------------------
        select_aliases = set()

        for projection in select_expression.expressions:
            if isinstance(projection, exp.Alias):
                select_aliases.add(projection.alias)

        # -----------------------------------------------------
        # Validate columns
        # -----------------------------------------------------
        for column in select_expression.find_all(exp.Column):

            column_name = column.name
            qualifier = column.table

            # Ignore *
            if column_name == "*":
                continue

            # -------------------------------------------------
            # Ignore columns belonging to nested SELECTs.
            # They will be validated by their own SELECT scope.
            # -------------------------------------------------
            parent_select = column.find_ancestor(exp.Select)

            if parent_select is not select_expression:
                continue

            # -------------------------------------------------
            # SELECT alias
            #
            # Example:
            # ORDER BY total
            # -------------------------------------------------
            if column_name in select_aliases:
                continue

            # -------------------------------------------------
            # Qualified column
            #
            # c.name
            # o.amount
            # -------------------------------------------------
            if qualifier:

                actual_table = table_aliases.get(qualifier)

                if actual_table is None:
                    return {
                        "valid": False,
                        "error": (
                            f"Table or alias '{qualifier}' "
                            f"does not exist in the query."
                        )
                    }

                if column_name not in table_columns[actual_table]:
                    return {
                        "valid": False,
                        "error": (
                            f"Column '{qualifier}.{column_name}' "
                            f"does not exist in the database schema."
                        )
                    }

            # -------------------------------------------------
            # Unqualified column
            #
            # Example:
            # SELECT amount FROM orders
            # -------------------------------------------------
            else:

                matching_tables = [
                    table_name
                    for table_name in query_tables
                    if column_name in table_columns[table_name]
                ]

                if len(matching_tables) == 0:

                    return {
                        "valid": False,
                        "error": (
                            f"Column '{column_name}' "
                            f"does not exist in the query tables."
                        )
                    }

                if len(matching_tables) > 1:

                    return {
                        "valid": False,
                        "error": (
                            f"Ambiguous column '{column_name}'. "
                            f"It exists in multiple tables: "
                            f"{', '.join(sorted(matching_tables))}. "
                            f"Use a table name or alias."
                        )
                    }

    return {
        "valid": True,
        "error": ""
    }

def validate_functions(expression):
    """
    Validate SQL functions used in the query.

    Allows common read-only PostgreSQL functions.
    Rejects functions that could perform unsafe operations.
    """

    allowed_functions = {
        # Aggregate functions
        "COUNT",
        "SUM",
        "AVG",
        "MIN",
        "MAX",

        # Common numeric functions
        "ABS",
        "ROUND",
        "CEIL",
        "CEILING",
        "FLOOR",

        # Common string functions
        "LOWER",
        "UPPER",
        "LENGTH",
        "TRIM",
        "LTRIM",
        "RTRIM",
        "CONCAT",
        "SUBSTRING",

        # Date/time functions
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "NOW",

        # PostgreSQL conditional functions
        "COALESCE",
        "NULLIF",
    }

    for function in expression.find_all(exp.Func):
        function_name = function.sql_name().upper()

        if function_name not in allowed_functions:
            return {
                "valid": False,
                "error": (
                    f"SQL function '{function_name}' "
                    f"is not allowed by the SQL validator."
                )
            }

    return {
        "valid": True,
        "error": ""
    }
# ---------------------------------------------------------
# SQL Validation Node
# ---------------------------------------------------------

import sqlglot
from sqlglot import exp

# ---------------------------------------------------------
# SQL Validation Node
# ---------------------------------------------------------

def validate_sql_node(state: AgentState):

    sql = state["generated_sql"].strip()

    # -----------------------------------------------------
    # 1. SQL cannot be empty
    # -----------------------------------------------------

    if not sql:
        return {
            "sql_valid": False,
            "error": "Generated SQL is empty."
        }

    # -----------------------------------------------------
    # 2. Parse SQL using SQLGlot
    # -----------------------------------------------------

    try:
        statements = sqlglot.parse(
            sql,
            read="postgres"
        )

    except Exception as e:
        return {
            "sql_valid": False,
            "error": f"Invalid SQL syntax: {str(e)}"
        }

    # -----------------------------------------------------
    # 3. Only one SQL statement is allowed
    # -----------------------------------------------------

    if len(statements) != 1:
        return {
            "sql_valid": False,
            "error": "Multiple SQL statements are not allowed."
        }

    expression = statements[0]

    # -----------------------------------------------------
    # 4. Only SELECT / WITH queries are allowed
    # -----------------------------------------------------

    if not isinstance(expression, (exp.Select, exp.Union)):
        return {
            "sql_valid": False,
            "error": "Only SELECT queries are allowed."
        }

    # -----------------------------------------------------
    # 5. Validate tables against database schema
    # -----------------------------------------------------

    schema = state.get("schema", {})

    table_validation = validate_tables_against_schema(
        expression,
        schema
    )

    if not table_validation["valid"]:
        return {
            "sql_valid": False,
            "error": table_validation["error"]
        }

    # -----------------------------------------------------
    # 6. Validate columns against database schema
    # -----------------------------------------------------

    column_validation = validate_columns_against_schema(
        expression,
        schema
    )

    if not column_validation["valid"]:
        return {
            "sql_valid": False,
            "error": column_validation["error"]
        }
    function_validation = validate_functions(expression)

    if not function_validation["valid"]:
         return {
              "sql_valid": False,
              "error": function_validation["error"]
    }

    # -----------------------------------------------------
    # 7. Check for data-modifying operations
    # -----------------------------------------------------

    forbidden_expressions = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Alter,
        exp.Create,
        exp.Grant,
        exp.Command,
    )

    dangerous_nodes = expression.find_all(
        forbidden_expressions
    )

    for node in dangerous_nodes:

        return {
            "sql_valid": False,
            "error": (
                f"Forbidden SQL operation detected: "
                f"{node.key.upper()}"
            )
        }

    # -----------------------------------------------------
    # 8. Query passed validation
    # -----------------------------------------------------

    return {
        "sql_valid": True,
        "error": ""
    }

# ---------------------------------------------------------
# SQL Execution Node
# ---------------------------------------------------------

from db import get_connection


def execute_sql_node(state: AgentState):
    if state.get("sql_valid") is not True:
        return {
            "query_result": [],
            "error": "SQL execution blocked because the query did not pass validation."
        }
    sql = state["generated_sql"]
    conn = None

    try:
        conn = get_user_connection(
            host=state["db_host"],
            port=state["db_port"],
            dbname=state["db_name"],
            user=state["db_user"],
            password=state["db_password"]
        )

        with conn.cursor() as cur:
            cur.execute(sql)

            column_names = [
                description.name
                for description in cur.description
            ]

            rows = cur.fetchall()

        results = [
            dict(zip(column_names, row))
            for row in rows
        ]

        return {
            "query_result": results,
            "error": ""
        }

    except Exception as e:
        return {
            "query_result": [],
            "error": str(e)
        }

    finally:
        if conn:
            conn.close()

# ---------------------------------------------------------
# SQL Validation Router
# ---------------------------------------------------------

def validation_router(state: AgentState):

    if state.get("sql_valid") is True:
        return "execute"

    return "reject"


def intent_router(state: AgentState):
    if state.get("user_intent") == "read_only":
        return "continue"

    return "reject"


def fix_sql_node(state: AgentState):
    user_query = state["user_query"]
    schema = state.get("schema", {})
    generated_sql = state.get("generated_sql", "")
    error = state.get("error", "")
    retry_count = state.get("retry_count", 0)

    prompt = f"""
You are a PostgreSQL SQL correction agent.

The user asked:
{user_query}

The previously generated SQL was:
{generated_sql}

The SQL validator rejected it with this error:
{error}

Database schema:
{schema}

Your task is to correct the SQL.

Rules:
1. Return ONLY SQL.
2. The SQL must be read-only.
3. Use only SELECT or WITH ... SELECT.
4. Use only tables that exist in the provided schema.
5. Use only columns that exist in those tables.
6. Correct ambiguous columns by using table names or aliases.
7. Correct invalid table aliases.
8. Use only safe/read-only SQL functions.
9. Do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE,
   GRANT, REVOKE, or any other write/destructive operation.
10. Do not explain the correction.
11. Do not use markdown code fences.
12. Carefully diagnose the validation error before modifying the SQL.

13. Preserve the original user's intent.
    Do not change the requested result just to make the SQL valid.

14. Make the smallest necessary correction to the previous SQL.

15. If a table or column does not exist, replace it only with a
    valid table or column supported by the provided schema.

16. If a JOIN is required, use only relationships that exist in
    the provided schema. Never invent relationships.

17. Preserve valid JOIN, GROUP BY, HAVING, ORDER BY, aggregate,
    and filtering logic whenever possible.

18. Do not remove valid parts of the query unnecessarily.

19. The corrected SQL must be compatible with PostgreSQL.
Generate the corrected PostgreSQL query now.
"""

    try:
        response = llm.invoke(prompt)

        if isinstance(response.content, str):
            corrected_sql = extract_llm_text(response)
        else:
            corrected_sql = ""
            for block in response.content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        corrected_sql += block.get("text", "")
                elif isinstance(block, str):
                    corrected_sql += block

            corrected_sql = extract_llm_text(response)


        # Remove markdown fences if the model still returns them.
        if corrected_sql.startswith("```"):
            corrected_sql = corrected_sql.replace("```sql", "")
            corrected_sql = corrected_sql.replace("```", "")
            corrected_sql = corrected_sql.strip()

        return {
            "generated_sql": corrected_sql,
            "retry_count": retry_count + 1,
            "error": ""
        }

    except Exception as e:
        return {
            "generated_sql": generated_sql,
            "retry_count": retry_count + 1,
            "error": f"SQL correction failed: {str(e)}"
        }

def execution_router(state: AgentState):
    if state.get("error"):
        if state.get("retry_count", 0) < state.get("max_retries", 3):
            return "fix"

        return "reject"

    return "success"


def generate_answer_node(state: AgentState):
    error = state.get("error")

    if error:
        return {
            "final_answer": f"I couldn't complete the query. Error: {error}"
        }

    user_query = state.get("user_query", "")
    results = state.get("query_result", [])

    prompt = f"""
You are a helpful PostgreSQL database assistant.

USER QUESTION:
{user_query}

DATABASE RESULT:
{results}

Answer the user's question using ONLY the database result.

RULES:

1. Answer in clear, natural language.

2. Directly answer what the user asked.

3. Keep the answer concise and easy to understand.

4. Do not generate or show SQL.

5. Do not mention internal agent processes, nodes,
   validation, retries, schema inspection, or LLMs.

6. Base every factual statement only on the database result.

7. If there are no results, clearly say that no matching
   records were found.

8. If the result contains multiple rows, summarize the
   important information clearly instead of unnecessarily
   repeating the entire raw result.

9. If the user asks for a total, count, average, highest,
   lowest, or similar value, clearly state the calculated
   value from the result.

10. Do not invent explanations, values, names, or facts
    that are not present in the database result.

11. If the result is already sufficient to answer the
    question, do not ask a follow-up question.

12. Use simple wording suitable for a normal database user.

FINAL ANSWER:
"""

    response = llm.invoke(prompt)

    return {
        "final_answer": extract_llm_text(response)
    }