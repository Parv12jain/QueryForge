import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [expandedTable, setExpandedTable] = useState(null);
  
  const [connectionId, setConnectionId] = useState("");
  const [queryHistory, setQueryHistory] = useState(() => {
    const savedHistory = localStorage.getItem("sqlAgentQueryHistory");

    return savedHistory
      ? JSON.parse(savedHistory)
      : [];
  });

  useEffect(() => {
    localStorage.setItem(
      "sqlAgentQueryHistory",
      JSON.stringify(queryHistory)
    );
  }, [queryHistory]);
  const [dbConnection, setDbConnection] = useState({
    type: "PostgreSQL",
    host: "localhost",
    port: "5432",
    database: "new_db",
    username: "sql_agent_user",
    password: "",
  });

  const [connectionStatus, setConnectionStatus] = useState("connected");
  const [connectionMessage, setConnectionMessage] = useState("");
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState("");


  const exampleQueries = [
    "Show all customers",
    "Who spent the most?",
    "Show orders above ₹5,000",
    "Show total spent by customer",
  ];

  /* =========================================================
     RUN QUERY
  ========================================================= */

  const runQuery = async () => {
    if (!question.trim() || loading) return;

    setLoading(true);
    setResponse(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question.trim(),
          connection_id: connectionId,
        }),
      });

      const data = await res.json();

      setResponse({
        status: res.status,
        data,
      });

      setQueryHistory((prev) => [
      {
        question: question.trim(),
        sql: data.sql,
        rows: data.results?.length ?? 0,
        retries: data.retry_count ?? 0,
        timestamp: new Date().toLocaleTimeString(),
      },
      ...prev,
    ]);
    } catch (error) {
      setResponse({
        status: 0,
        data: {
          error: "Could not connect to the SQL Agent backend.",
        },
      });
    } finally {
      setLoading(false);
    }
  };


  /* =========================================================
     RESPONSE STATE
  ========================================================= */

  const hasResponse = Boolean(response);

  const results = response?.data?.results || [];

  const resultCount = results.length;

  const hasResults = resultCount > 0;

  /* =========================================================
   RESULT INTELLIGENCE
========================================================= */

const generatedSQL =
  response?.data?.sql || "";

const normalizedSQL =
  generatedSQL.toUpperCase();

const resultType =
  normalizedSQL.includes("COUNT(")
    ? "COUNT"
    : normalizedSQL.includes("SUM(")
      ? "SUM"
      : normalizedSQL.includes("AVG(")
        ? "AVG"
        : normalizedSQL.includes("MAX(")
          ? "MAX"
          : normalizedSQL.includes("MIN(")
            ? "MIN"
            : normalizedSQL.includes("GROUP BY")
              ? "GROUPED"
              : "DATASET";


const resultTypeLabel = {
  COUNT: "COUNT ANALYSIS",
  SUM: "TOTAL ANALYSIS",
  AVG: "AVERAGE ANALYSIS",
  MAX: "MAXIMUM VALUE",
  MIN: "MINIMUM VALUE",
  GROUPED: "GROUPED ANALYSIS",
  DATASET: "DATABASE RESULT",
}[resultType];


const resultTypeDescription = {
  COUNT: "The agent calculated a record count.",
  SUM: "The agent calculated a total value.",
  AVG: "The agent calculated an average value.",
  MAX: "The agent identified the maximum value.",
  MIN: "The agent identified the minimum value.",
  GROUPED: "The agent grouped database records for analysis.",
  DATASET: "The agent returned database records.",
}[resultType];

  const columns =
    results.length > 0
      ? Object.keys(results[0])
      : [];

  const columnCount = columns.length;

  const requestError =
    response?.data?.error ||
    response?.data?.detail ||
    "";

  const hasSQL =
    Boolean(response?.data?.sql);

  const sqlValid =
    response?.data?.sql_valid;

  const querySuccessful =
    response?.status === 200 &&
    !requestError;

  const queryFailed =
    hasResponse &&
    !querySuccessful;


  /* =========================================================
     AGENT PIPELINE STATUS
  ========================================================= */

  const understandStatus = loading
    ? "working"
    : hasResponse
      ? "complete"
      : "waiting";

  const generateStatus = loading
    ? "working"
    : hasSQL
      ? "complete"
      : queryFailed
        ? "failed"
        : "waiting";

  const validateStatus = loading
    ? "working"
    : sqlValid === true
      ? "safe"
      : sqlValid === false
        ? "failed"
        : "waiting";

  const executeStatus = loading
    ? "working"
    : querySuccessful
      ? "complete"
      : hasSQL && sqlValid !== false
        ? "failed"
        : "waiting";


  const getStatusSymbol = (status) => {
    if (status === "complete") return "✓";
    if (status === "safe") return "✓";
    if (status === "failed") return "!";
    if (status === "working") return "•";

    return "—";
  };


  const getStatusLabel = (status) => {
    if (status === "complete") return "COMPLETE";
    if (status === "safe") return "SAFE";
    if (status === "failed") return "FAILED";
    if (status === "working") return "WORKING";

    return "WAITING";
  };


  /* =========================================================
     DYNAMIC SCHEMA
  ========================================================= */


  const [schema, setSchema] = useState({});

  const loadSchema = async (id = connectionId) => {
    if (!id) {
      return;
    }

    setSchemaLoading(true);
    setSchemaError("");

    try {
      const res = await fetch(
        "http://127.0.0.1:8000/connection/schema",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            connection_id: id,
          })
        }
      );

      const data = await res.json();

      if (res.ok && data.success) {
        const normalizedSchema = Object.fromEntries(
          Object.entries(data.schema || {}).map(
            ([tableName, tableInfo]) => [
              tableName,
              (tableInfo.columns || []).map((column) => ({
                name: column.name,
                type: column.type,
                primary: (tableInfo.primary_keys || []).includes(column.name),
              })),
            ]
          )
        );

        setSchema(normalizedSchema);
      } else {
        setSchemaError(
          data.detail || "Could not load database schema."
        );
      }
    } catch (error) {
      setSchemaError("Could not reach the SQL Agent backend.");
    } finally {
      setSchemaLoading(false);
    }
  };


  /* =========================================================
     UI ACTIONS
  ========================================================= */

  const disconnectDatabase = async () => {
    if (!connectionId) {
      return;
    }

    try {
      const res = await fetch(
        "http://127.0.0.1:8000/connection/disconnect",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            connection_id: connectionId,
          }),
        }
      );

      const data = await res.json();

      if (res.ok && data.success) {
        setConnectionId("");
        setSchema({});
        setResponse(null);
        setConnectionMessage("");
        setConnectionStatus("editing");
      } else {
        setConnectionMessage(
          data.detail || "Could not disconnect the database."
        );
      }
    } catch (error) {
      setConnectionMessage(
        "Could not reach the SQL Agent backend."
      );
    }
  };

  const toggleTable = (tableName) => {
    setExpandedTable(
      expandedTable === tableName
        ? null
        : tableName
    );
  };


  const selectExample = (query) => {
    setQuestion(query);
    setResponse(null);
  };


  const clearQuery = () => {
    if (loading) return;

    setQuestion("");
    setResponse(null);
  };


  /* =========================================================
     FORMAT VALUES
  ========================================================= */

  const formatCellValue = (value) => {
    if (value === null || value === undefined) {
      return "NULL";
    }

    if (typeof value === "boolean") {
      return value ? "true" : "false";
    }

    return String(value);
  };




  /* =========================================================
     MAIN UI
  ========================================================= */

  return (
    <div className="app-shell">


      {/* =====================================================
          TOP BAR
      ===================================================== */}

      <header className="topbar">

        <div className="brand">

          <div className="brand-mark">
            ⌘
          </div>

          <div>

            <div className="brand-name">
              QUERYFORGE
            </div>

            <div className="brand-subtitle">
              FORGE QUESTIONS INTO ANSWERS
            </div>

          </div>

        </div>


        <div className="connection-status">

          <span className="status-dot"></span>

          <span>
            ✦ INTELLIGENCE AT WORK
          </span>

        </div>

      </header>


      {/* =====================================================
          WORKSPACE
      ===================================================== */}

      <main className="workspace">


        {/* ===================================================
            SIDEBAR
        =================================================== */}

        <aside className="sidebar">

        <div className="database-card">

          <div className="database-icon">
          DB
          </div>

          <div className="database-info">
            <strong>
              {dbConnection.type}
            </strong>

            <span>
              {dbConnection.database}
            </span>
                <div className="database-actions">
              <button
                className="configure-button"
                type="button"
                onClick={() => setConnectionStatus("editing")}
              >
                CONFIGURE
              </button>

              {connectionId && (
                <button
                  className="disconnect-button"
                  type="button"
                  onClick={disconnectDatabase}
                >
                  DISCONNECT
                </button>
              )}
            </div>

            {connectionMessage && (
        <div
          className={`connection-feedback ${
            connectionStatus === "connected"
              ? "connection-success"
              : "connection-error"
          }`}
        >
          <span className="connection-feedback-icon">
            {connectionStatus === "connected" ? "✓" : "!"}
          </span>

          <div>
            <strong>
              {connectionStatus === "connected"
                ? "CONNECTION VERIFIED"
                : "CONNECTION FAILED"}
            </strong>

            <span>
              {connectionMessage}
            </span>
          </div>
        </div>
      )}

          </div>
        </div>

          <div className="panel-label tables-label">
            SCHEMA
          </div>

          {connectionStatus === "editing" && (
  <div className="connection-panel">

    <div className="connection-panel-header">
      <div>
        <span className="connection-panel-label">
          DATABASE CONNECTION
        </span>

        <strong>
          Configure source
        </strong>
      </div>

      <button
        className="connection-close"
        type="button"
        onClick={() => setConnectionStatus("connected")}
      >
        ×
      </button>
    </div>

    <div className="connection-form">

      <label>
        DATABASE TYPE
        <select
          value={dbConnection.type}
          onChange={(event) =>
            setDbConnection({
              ...dbConnection,
              type: event.target.value,
            })
          }
        >
          <option value="PostgreSQL">PostgreSQL</option>
        </select>
      </label>

      <label>
        HOST
        <input
          type="text"
          value={dbConnection.host}
          onChange={(event) =>
            setDbConnection({
              ...dbConnection,
              host: event.target.value,
            })
          }
        />
      </label>

      <div className="connection-row">

        <label>
          PORT
          <input
            type="text"
            value={dbConnection.port}
            onChange={(event) =>
              setDbConnection({
                ...dbConnection,
                port: event.target.value,
              })
            }
          />
        </label>

        <label>
          DATABASE
          <input
            type="text"
            value={dbConnection.database}
            onChange={(event) =>
              setDbConnection({
                ...dbConnection,
                database: event.target.value,
              })
            }
          />
        </label>

      </div>

      <label>
        USERNAME
        <input
          type="text"
          value={dbConnection.username}
          onChange={(event) =>
            setDbConnection({
              ...dbConnection,
              username: event.target.value,
            })
          }
        />
      </label>

      <label>
        PASSWORD
        <input
          type="password"
          value={dbConnection.password}
          onChange={(event) =>
            setDbConnection({
              ...dbConnection,
              password: event.target.value,
            })
          }
          placeholder="Enter database password"
        />
      </label>

      <button
  className="test-connection-button"
  type="button"
  disabled={connectionStatus === "testing"}
  onClick={async () => {
    setConnectionStatus("testing");
    setConnectionId("");
    setSchema({});
    setResponse(null);
    setConnectionMessage("");

    try {
      const res = await fetch(
        "http://127.0.0.1:8000/connection/test",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            type: dbConnection.type,
            host: dbConnection.host,
            port: dbConnection.port,
            database: dbConnection.database,
            username: dbConnection.username,
            password: dbConnection.password,
          }),
        }
      );

      const data = await res.json();

      if (res.ok && data.success) {

        setConnectionId(data.connection_id);

        setConnectionMessage(
          `PostgreSQL · ${data.database} · ${data.user}`
        );
        setConnectionStatus("connected");
        await loadSchema(data.connection_id);
      } else {
        setConnectionMessage(
          data.detail || "Check your database connection details."
        );
        setConnectionStatus("error");
      }
    } catch (error) {
      setConnectionMessage(
        "Could not reach the SQL Agent backend."
      );
      setConnectionStatus("error");
    }
  }}
>
  {connectionStatus === "testing"
    ? "TESTING..."
    : "TEST CONNECTION"}

  <span>
    {connectionStatus === "testing" ? "…" : "→"}
  </span>
</button>

    </div>

  </div>
)}


          {/* DYNAMIC TABLE LIST */}

          {schemaLoading && (
            <div className="schema-loading">
              <span className="schema-loading-dot">•</span>
              LOADING DATABASE SCHEMA...
            </div>
          )}

          {!schemaLoading && schemaError && (
            <div className="schema-error">
              {schemaError}
            </div>
          )}

          {!schemaLoading &&
            !schemaError &&
            Object.keys(schema).length === 0 && (
              <div className="schema-empty">
                <div className="schema-empty-icon">◇</div>
                <strong>SCHEMA STANDBY</strong>
                <span>
                  Connect a PostgreSQL databaseto inspect tables and columns.
                </span>

                <small>READ-ONLY INSPECTION</small>
              </div>
            )}

          {!schemaLoading &&
            !schemaError &&
            Object.entries(schema).map(
              ([tableName, tableColumns]) => (
                <div key={tableName}>
                  <div
                    className={`table-item ${
                      expandedTable === tableName ? "expanded" : ""
                    }`}
                    onClick={() => toggleTable(tableName)}
                  >
                    <span className="table-arrow">
                      {expandedTable === tableName ? "▾" : "▸"}
                    </span>

                    <span className="table-icon">
                      ▦
                    </span>

                    <span className="table-name">
                      {tableName}
                    </span>

                    <span className="column-count">
                      {tableColumns.length}
                    </span>
                  </div>

                  {expandedTable === tableName && (
                    <div className="column-list">
                      {tableColumns.length > 0 ? (
                        tableColumns.map((column) => (
                          <div
                            className="schema-column"
                            key={column.name}
                          >
                            <span className="column-icon">
                              {column.primary ? "🔑" : "·"}
                            </span>

                            <span className="column-name">
                              {column.name}
                            </span>

                            <span className="column-type">
                              {column.type}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div className="schema-no-columns">
                          No columns returned
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            )}

          {/* SECURITY */}

          <div className="sidebar-footer">

            <div className="security-badge">

              <span>
                ◆
              </span>

              READ-ONLY ACCESS

            </div>

          </div>

          {/* =================================================
              QUERY HISTORY
          ================================================= */}

          <div className="sidebar-history">

            <div className="sidebar-section-header">
              <span>QUERY HISTORY</span>
              <div className="sidebar-history-controls">
                <span className="sidebar-history-count">                 
                {queryHistory.length}
                </span>

                {queryHistory.length > 0 && (
                  <button
                    type="button"
                    className="clear-history-button"
                    onClick={() => setQueryHistory([])}
                  >
                    CLEAR
                  </button>
                )}
              </div>
            </div>
          

            {queryHistory.length === 0 ? (

              <div className="sidebar-history-empty">
                No queries yet
              </div>

            ) : (

              <div className="sidebar-history-list">

                {queryHistory.slice(0, 8).map((item, index) => (

                  <button
                    type="button"
                    className="sidebar-history-item"
                    key={`${item.timestamp}-${index}`}
                    onClick={() => setQuestion(item.question)}
                  >

                    <span className="sidebar-history-number">
                      {String(index + 1).padStart(2, "0")}
                    </span>

                    <span className="sidebar-history-content">

                      <span className="sidebar-history-question">
                        {item.question}
                      </span>

                      <span className="sidebar-history-time">
                        {item.timestamp}
                      </span>

                    </span>

                  </button>

                ))}

              </div>

            )}

          </div>

        </aside>


        {/* ===================================================
            MAIN AREA
        =================================================== */}

        <section className="main-area">


          {/* =================================================
              HEADER
          ================================================= */}

          <div className="workspace-heading">

            <div>

              <span className="eyebrow">
                QUERY WORKSPACE
              </span>

              <h1>
                From intent to verified SQL.
              </h1>

              <p>
                Describe your goal in plain language. QueryForge handles generation,
                validation, and execution.
              </p>

            </div>


            <div className="agent-indicator">

              <span className="pulse"></span>

              {loading
                ? "AGENT WORKING"
                : querySuccessful
                  ? "QUERY COMPLETE"
                  : queryFailed
                    ? "AGENT ERROR"
                    : "AGENT READY"}

            </div>

          </div>


          {/* =================================================
              QUERY COMMAND CENTER
          ================================================= */}

          <div className="query-card command-center">


            <div className="query-card-header">

              <div className="query-title-group">

                <span className="query-title">
                  QUERY COMMAND
                </span>

                <span className="query-mode">
                  NATURAL LANGUAGE
                </span>

              </div>


              <div className="query-header-actions">

                <span className="shortcut">
                  CTRL + ENTER
                </span>


                {question && !loading && (

                  <button
                    className="clear-query"
                    onClick={clearQuery}
                    type="button"
                  >
                    CLEAR
                  </button>

                )}

              </div>

            </div>


            <div className="query-intro">

              <span className="query-prompt-symbol">
                ↳
              </span>

              <span>
                Tell the agent what you want to know
              </span>

            </div>


            <div className="query-editor">

              <textarea
                value={question}
                onChange={(event) =>
                  setQuestion(event.target.value)
                }
                placeholder="e.g. Show me the customers who spent more than ₹5,000..."
                onKeyDown={(event) => {

                  if (
                    event.ctrlKey &&
                    event.key === "Enter"
                  ) {
                    runQuery();
                  }

                }}
              />


              <div className="character-count">

                {question.length}{" "}

                {question.length === 1
                  ? "character"
                  : "characters"}

              </div>

            </div>


            <div className="suggestion-area">

              <span className="suggestion-label">
                TRY A QUERY
              </span>


              <div className="suggestion-list">

                {exampleQueries.map(
                  (query) => (

                    <button
                      key={query}
                      className="suggestion-chip"
                      onClick={() =>
                        selectExample(query)
                      }
                      type="button"
                    >

                      {query}

                    </button>

                  )
                )}

              </div>

            </div>


            <div className="query-actions">

              <div className="query-security">

                <span className="security-dot">
                  ●
                </span>

                READ-ONLY

                <span className="action-divider">
                  /
                </span>

                POSTGRESQL

              </div>


              <button
                className="run-button"
                onClick={runQuery}
                disabled={
                  loading ||
                  !question.trim() ||
                  !connectionId
                }
              >

                <span>

                  {loading
                    ? "RUNNING..."
                    : "RUN QUERY"}

                </span>


                <span className="run-arrow">

                  {loading
                    ? "…"
                    : "→"}

                </span>

              </button>
              {loading && (
                <div className="query-loading-status">
                  <span className="loading-dot"></span>
                  <span>AGENT IS PROCESSING YOUR QUERY...</span>
                </div>
              )}

            </div>

          </div>


          {/* =================================================
              CONTENT GRID
          ================================================= */}

          <div className="content-grid">


            {/* =================================================
                SMART RESULTS PANEL
            ================================================= */}

            <div className="result-panel">

              <div className="panel-header">

                <span>
                  RESULTS
                </span>


                <span className="muted">

                  {loading
                    ? "Processing..."
                    : !response
                      ? "Waiting for query"
                      : querySuccessful
                        ? `${resultCount} ${
                            resultCount === 1
                              ? "record"
                              : "records"
                          }`
                        : "Request failed"}

                </span>

              </div>


              {/* =================================================
                  EMPTY STATE
              ================================================= */}

              {!response && !loading && (

                <div className="empty-state">

                  <div className="empty-icon">
                    ⌁
                  </div>

                  <h2>
                    Your results will appear here
                  </h2>

                  <p>
                    Run a natural-language query to see
                    generated SQL and database results.
                  </p>

                  <div className="empty-hint">
                    TIP · TRY ONE OF THE EXAMPLE QUERIES
                  </div>

                </div>

              )}


              {/* =================================================
                  LOADING STATE
              ================================================= */}

              {loading && (

                <div className="result-loading">

                  <div className="loading-orbit">

                    <span></span>
                    <span></span>
                    <span></span>

                  </div>

                  <div className="loading-title">
                    AGENT IS WORKING
                  </div>

                  <div className="loading-text">
                    Generating, validating and executing SQL...
                  </div>

                </div>

              )}


              {/* =================================================
                  RESPONSE
              ================================================= */}

              {response && !loading && (

                <div className="response-content">


                  {/* =================================================
                      SUMMARY
                  ================================================= */}

                  <div className="answer-box">

                    <div className="response-label">
                      AGENT SUMMARY
                    </div>


                    <div className="summary-content">

                      {querySuccessful ? (

                        <>

                          <div className="summary-status">

                            <span className="summary-check">
                              ✓
                            </span>

                            <span>
                              QUERY COMPLETED
                            </span>

                          </div>


                          <p>

                            {resultCount > 0
                              ? `${resultCount} ${
                                  resultCount === 1
                                    ? "record"
                                    : "records"
                                } returned from the database.`
                              : "The query completed successfully but returned no records."}

                          </p>

                        </>

                      ) : (

                        <>

                          <div className="summary-status error-summary">

                            <span className="summary-check">
                              !
                            </span>

                            <span>
                              REQUEST FAILED
                            </span>

                          </div>


                          <p>
                            {requestError ||
                              "The SQL agent could not complete the request."}
                          </p>

                        </>

                      )}

                    </div>

                  </div>


                  {/* =================================================
                      RESULT METRICS
                  ================================================= */}

                  {/* RESULT INTELLIGENCE */}

                  {querySuccessful && (

                    <div className="result-intelligence">

                      <div className="intelligence-icon">
                        ◈
                      </div>

                      <div className="intelligence-content">

                        <div className="intelligence-top">

                          <span className="intelligence-label">
                            RESULT INTELLIGENCE
                          </span>

                          <span className="intelligence-type">
                            {resultTypeLabel}
                          </span>

                        </div>

                        <p>
                          {resultTypeDescription}
                        </p>

                      </div>

                    </div>

                  )}


                   {/* RESULT METRICS */}

                   {querySuccessful && (

                     <div className="result-metrics">

                       <div className="metric-card">
                         <span className="metric-label">ROWS RETURNED</span>
                         <strong>{resultCount}</strong>
                         <small>
                           {resultCount === 1 ? "record" : "records"} from database
                         </small>
                       </div>

                       <div className="metric-card">
                         <span className="metric-label">COLUMNS</span>
                         <strong>{columnCount}</strong>
                         <small>
                           {columnCount === 1 ? "field" : "fields"} returned
                         </small>
                       </div>

                       <div className="metric-card">
                         <span className="metric-label">SQL STATUS</span>
                         <strong className="success-text">
                           {sqlValid === true ? "SAFE" : "CHECKED"}
                         </strong>
                         <small>Read-only validation passed</small>
                       </div>

                       <div className="metric-card">
                         <span className="metric-label">RETRIES</span>
                         <strong>{response?.data?.retry_count ?? 0}</strong>
                         <small>
                           {(response?.data?.retry_count ?? 0) === 0
                             ? "No correction required"
                             : "SQL correction attempts"}
                         </small>
                       </div>

                     </div>

                   )}

                   {/* =================================================
                       GENERATED SQL
                   ================================================= */}

                  {hasSQL && (

                    <div className="sql-box">

                      <div className="response-section-header">

                        <span className="response-label">
                          GENERATED SQL
                        </span>

                        <span className="sql-status">

                          {sqlValid === true
                            ? "✓ VALIDATED"
                            : sqlValid === false
                              ? "! INVALID"
                              : "SQL"}

                        </span>

                      </div>


                      <div className="sql-code">

                        <span className="sql-line-number">
                          01
                        </span>

                        <pre>
                          {response.data.sql}
                        </pre>

                      </div>

                    </div>

                  )}


                  {/* =================================================
                      DATABASE RESULTS
                  ================================================= */}

                  {hasResults && (

                    <div className="data-table-wrapper">


                      <div className="response-section-header">

                        <span className="response-label">
                          DATABASE RESULTS
                        </span>

                        <span className="table-result-count">
                          {resultCount} ROWS
                        </span>

                      </div>


                      <div className="table-scroll">

                        <table className="data-table">

                          <thead>

                            <tr>

                              {columns.map(
                                (column, index) => (

                                  <th
                                    key={column}
                                  >

                                    <span className="column-index">
                                      {String(
                                        index + 1
                                      ).padStart(2, "0")}
                                    </span>

                                    {column}

                                  </th>

                                )
                              )}

                            </tr>

                          </thead>


                          <tbody>

                            {results.map(
                              (row, rowIndex) => (

                                <tr
                                  key={rowIndex}
                                >

                                  {columns.map(
                                    (column) => (

                                      <td
                                        key={column}
                                        className={
                                          row[column] === null
                                            ? "null-value"
                                            : ""
                                        }
                                      >

                                        {formatCellValue(
                                          row[column]
                                        )}

                                      </td>

                                    )
                                  )}

                                </tr>

                              )
                            )}

                          </tbody>

                        </table>

                      </div>


                      <div className="table-footer">

                        <span>
                          SHOWING {resultCount}{" "}
                          {resultCount === 1
                            ? "ROW"
                            : "ROWS"}
                        </span>

                        <span>
                          {columnCount}{" "}
                          {columnCount === 1
                            ? "COLUMN"
                            : "COLUMNS"}
                        </span>

                      </div>

                    </div>

                  )}


                  {/* =================================================
                      EMPTY RESULT
                  ================================================= */}

                  {querySuccessful &&
                    resultCount === 0 && (

                      <div className="no-results">

                        <div className="no-results-icon">
                          ∅
                        </div>

                        <strong>
                          No records found
                        </strong>

                        <p>
                          The database returned an empty
                          result set for this query.
                        </p>

                      </div>

                    )}


                  {/* =================================================
                      ERROR
                  ================================================= */}

                  {requestError && (

                    <div className="error-box">

                      <div className="response-section-header">

                        <span className="response-label">
                          AGENT ERROR
                        </span>

                        <span className="error-status">
                          FAILED
                        </span>

                      </div>


                      <p>
                        {requestError}
                      </p>

                    </div>

                  )}

                </div>

              )}

            </div>


            {/* =================================================
                AGENT EXECUTION CONSOLE
            ================================================= */}

            <div className="insight-panel agent-console">


              <div className="panel-header agent-console-header">

                <div className="console-title">

                  <span className="console-icon">
                    ◈
                  </span>

                  <span>
                    AGENT EXECUTION
                  </span>

                </div>


                <span className="live-label">

                  {loading
                    ? "RUNNING"
                    : "LIVE"}

                </span>

              </div>


              {/* PIPELINE */}

              <div className="pipeline">


                {/* UNDERSTAND */}

                <div
                  className={`pipeline-step ${understandStatus}`}
                >

                  <div className="pipeline-marker">

                    <span>
                      {getStatusSymbol(
                        understandStatus
                      )}
                    </span>

                  </div>


                  <div className="pipeline-content">

                    <div className="pipeline-topline">

                      <span className="pipeline-number">
                        01
                      </span>

                      <strong>
                        UNDERSTAND
                      </strong>

                      <span className="pipeline-status">
                        {getStatusLabel(
                          understandStatus
                        )}
                      </span>

                    </div>


                    <p>

                      {understandStatus === "working"
                        ? "Interpreting your request..."
                        : understandStatus === "complete"
                          ? "Request understood"
                          : "Waiting for request"}

                    </p>

                  </div>

                </div>


                {/* GENERATE */}

                <div
                  className={`pipeline-step ${generateStatus}`}
                >

                  <div className="pipeline-marker">

                    <span>
                      {getStatusSymbol(
                        generateStatus
                      )}
                    </span>

                  </div>


                  <div className="pipeline-content">

                    <div className="pipeline-topline">

                      <span className="pipeline-number">
                        02
                      </span>

                      <strong>
                        GENERATE
                      </strong>

                      <span className="pipeline-status">
                        {getStatusLabel(
                          generateStatus
                        )}
                      </span>

                    </div>


                    <p>

                      {generateStatus === "working"
                        ? "Generating PostgreSQL query..."
                        : generateStatus === "complete"
                          ? "SQL query generated"
                          : generateStatus === "failed"
                            ? "Could not generate SQL"
                            : "Waiting for SQL generation"}

                    </p>

                  </div>

                </div>


                {/* VALIDATE */}

                <div
                  className={`pipeline-step ${validateStatus}`}
                >

                  <div className="pipeline-marker">

                    <span>
                      {getStatusSymbol(
                        validateStatus
                      )}
                    </span>

                  </div>


                  <div className="pipeline-content">

                    <div className="pipeline-topline">

                      <span className="pipeline-number">
                        03
                      </span>

                      <strong>
                        VALIDATE
                      </strong>

                      <span className="pipeline-status">
                        {getStatusLabel(
                          validateStatus
                        )}
                      </span>

                    </div>


                    <p>

                      {validateStatus === "working"
                        ? "Checking SQL safety & schema..."
                        : validateStatus === "safe"
                          ? "SQL validated · SAFE"
                          : validateStatus === "failed"
                            ? "SQL validation failed"
                            : "Waiting for validation"}

                    </p>

                  </div>

                </div>


                {/* EXECUTE */}

                <div
                  className={`pipeline-step ${executeStatus}`}
                >

                  <div className="pipeline-marker">

                    <span>
                      {getStatusSymbol(
                        executeStatus
                      )}
                    </span>

                  </div>


                  <div className="pipeline-content">

                    <div className="pipeline-topline">

                      <span className="pipeline-number">
                        04
                      </span>

                      <strong>
                        EXECUTE
                      </strong>

                      <span className="pipeline-status">
                        {getStatusLabel(
                          executeStatus
                        )}
                      </span>

                    </div>


                    <p>

                      {executeStatus === "working"
                        ? "Running against database..."
                        : executeStatus === "complete"
                          ? `${resultCount} ${
                              resultCount === 1
                                ? "record"
                                : "records"
                            } returned`
                          : executeStatus === "failed"
                            ? "Execution failed"
                            : "Waiting for execution"}

                    </p>

                  </div>

                </div>

              </div>


              {/* RUN STATE */}

              <div className="run-state">

                <div className="run-state-header">

                  <span>
                    RUN STATE
                  </span>

                  <span className="run-state-indicator">

                    {querySuccessful
                      ? "●"
                      : queryFailed
                        ? "!"
                        : loading
                          ? "●"
                          : "—"}

                  </span>

                </div>


                <div className="run-state-grid">


                  <div className="run-metric">

                    <span>
                      STATUS
                    </span>

                    <strong
                      className={
                        querySuccessful
                          ? "success-text"
                          : queryFailed
                            ? "error-text"
                            : ""
                      }
                    >

                      {loading
                        ? "PROCESSING"
                        : querySuccessful
                          ? "SUCCESS"
                          : queryFailed
                            ? "FAILED"
                            : "IDLE"}

                    </strong>

                  </div>


                  <div className="run-metric">

                    <span>
                      ROWS
                    </span>

                    <strong>
                      {resultCount}
                    </strong>

                  </div>


                  <div className="run-metric">

                    <span>
                      RETRIES
                    </span>

                    <strong>
                      {response?.data?.retry_count ?? 0}
                    </strong>

                  </div>


                  <div className="run-metric">

                    <span>
                      ENGINE
                    </span>

                    <strong>
                      POSTGRESQL
                    </strong>

                  </div>

                </div>

              </div>



              {/* SECURITY FOOTER */}

              <div className="console-footer">

                <span className="console-security-dot">
                  ●
                </span>

                <span>
                  READ-ONLY EXECUTION
                </span>

                <span className="footer-divider">
                  /
                </span>

                <span>
                  SQL VALIDATION ENABLED
                </span>

              </div>

            </div>

          </div>

        </section>

      </main>

    </div>
  );
}

export default App;
