from node import validate_sql_node


base_state = {
    "schema": {
        "customers": {
            "columns": [
                {"name": "id"},
                {"name": "name"},
                {"name": "email"},
            ]
        },
        "orders": {
            "columns": [
                {"name": "id"},
                {"name": "customer_id"},
                {"name": "amount"},
                {"name": "order_date"},
            ]
        }
    }
}


tests = [
    # 1. JOIN + columns
    (
        "SELECT c.name, o.amount "
        "FROM customers c "
        "JOIN orders o ON c.id = o.customer_id"
    ),

    # 2. JOIN + aggregate
    (
        "SELECT c.name, SUM(o.amount) "
        "FROM customers c "
        "JOIN orders o ON c.id = o.customer_id "
        "GROUP BY c.name"
    ),

    # 3. GROUP BY + ORDER BY
    (
        "SELECT customer_id, SUM(amount) AS total "
        "FROM orders "
        "GROUP BY customer_id "
        "ORDER BY total DESC"
    ),

    # 4. HAVING
    (
        "SELECT customer_id, SUM(amount) AS total "
        "FROM orders "
        "GROUP BY customer_id "
        "HAVING SUM(amount) > 5000"
    ),

    # 5. Multiple aggregate functions
    (
        "SELECT "
        "COUNT(*) AS order_count, "
        "SUM(amount) AS total_amount, "
        "AVG(amount) AS average_amount, "
        "MAX(amount) AS maximum_amount, "
        "MIN(amount) AS minimum_amount "
        "FROM orders"
    ),

    # 6. JOIN + GROUP BY + HAVING + ORDER BY
    (
        "SELECT c.name, SUM(o.amount) AS total "
        "FROM customers c "
        "JOIN orders o ON c.id = o.customer_id "
        "GROUP BY c.name "
        "HAVING SUM(o.amount) > 5000 "
        "ORDER BY total DESC"
    ),

    # 7. Subquery
    (
        "SELECT name "
        "FROM customers "
        "WHERE id IN "
        "(SELECT customer_id FROM orders)"
    ),

    # 8. Invalid column inside a complex query
    (
        "SELECT c.name, SUM(o.wrong_amount) "
        "FROM customers c "
        "JOIN orders o ON c.id = o.customer_id "
        "GROUP BY c.name"
    ),

    # 9. Ambiguous column
    (
        "SELECT id "
        "FROM customers c "
        "JOIN orders o ON c.id = o.customer_id"
    ),

    # 10. Invalid table
    (
        "SELECT c.name "
        "FROM customers c "
        "JOIN payments p ON c.id = p.customer_id"
    ),
]


for number, sql in enumerate(tests, start=1):

    state = base_state.copy()
    state["generated_sql"] = sql

    result = validate_sql_node(state)

    print("\n" + "=" * 70)
    print(f"TEST {number}")
    print("=" * 70)

    print("SQL:")
    print(sql)

    print("\nVALID:")
    print(result["sql_valid"])

    print("\nERROR:")
    print(result.get("error", ""))