from langgraph.graph import StateGraph, START, END

from state import AgentState

from node import (
    check_intent_node,
    get_schema_node,
    generate_sql_node,
    validate_sql_node,
    execute_sql_node,
    fix_sql_node,
    generate_answer_node,
    validation_router,
    execution_router,
    intent_router
)


# ---------------------------------------------------------
# Create Graph
# ---------------------------------------------------------

builder = StateGraph(AgentState)


# ---------------------------------------------------------
# Add Nodes
# ---------------------------------------------------------

builder.add_node("check_intent", check_intent_node)

builder.add_node(
    "get_schema",
    get_schema_node
)

builder.add_node(
    "generate_sql",
    generate_sql_node
)

builder.add_node(
    "validate_sql",
    validate_sql_node
)

builder.add_node(
    "execute_sql",
    execute_sql_node
)

builder.add_node("generate_answer", generate_answer_node)

builder.add_node("fix_sql", fix_sql_node)

# ---------------------------------------------------------
# Add Edges
# ---------------------------------------------------------

# START → get_schema
builder.add_edge(START, "check_intent")

builder.add_conditional_edges(
    "check_intent",
    intent_router,
    {
        "continue": "get_schema",
        "reject": END
    }
)

builder.add_edge("get_schema", "generate_sql")

builder.add_edge("generate_sql", "validate_sql")

builder.add_conditional_edges(
    "validate_sql",
    validation_router,
    {
        "execute": "execute_sql",
        "reject": END
    }
)

builder.add_conditional_edges(
    "execute_sql",
    execution_router,
    {
        "success": "generate_answer",
        "fix": "fix_sql",
        "reject": END
    }
)

builder.add_edge("fix_sql", "validate_sql")

builder.add_edge("generate_answer", END)

# ---------------------------------------------------------
# Compile Graph
# ---------------------------------------------------------

graph = builder.compile()


