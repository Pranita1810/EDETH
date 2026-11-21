from __future__ import annotations

import io
import json
import re
import urllib.request
import urllib.parse
import polars as pl
import psycopg2
import pyodbc

from frontend.pages.data_ingestion import page


# ════════════════════════════════════════════════════════════════════════════
#  STRICT READ-ONLY QUERY VALIDATOR (SECURITY ENFORCEMENT)
# ════════════════════════════════════════════════════════════════════════════
READONLY_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|EXEC|EXECUTE|GRANT|REVOKE|INTO|CALL|LOCK)\b",
    re.IGNORECASE,
)


def validate_readonly_query(query: str) -> tuple[bool, str]:
    """Validates that a SQL query is strictly read-only (SELECT / WITH / EXPLAIN).
    Strictly blocks INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE, etc.
    """
    clean = re.sub(r"--.*?$|/\*.*?\*/", "", query, flags=re.MULTILINE | re.DOTALL).strip()
    if not clean:
        return False, "Query is empty."

    # Must start with a read-only keyword
    if not clean.upper().startswith(("SELECT", "WITH", "EXPLAIN")):
        return False, "Query must begin with a read-only statement (SELECT or WITH)."

    # Check for forbidden mutation keywords anywhere in query tokens
    match = READONLY_FORBIDDEN_RE.search(clean)
    if match:
        cmd = match.group(0).upper()
        return False, f"Forbidden mutation command '{cmd}' detected. Only data viewing is permitted."

    return True, ""


# ════════════════════════════════════════════════════════════════════════════
#  1. FILE INPUTS (CSV & EXCEL)
# ════════════════════════════════════════════════════════════════════════════
class ExcelCsv:
    @staticmethod
    def user_input_csv():
        path = page.var_file_path
        delimiter = getattr(page, "var_csv_delimiter", ",") or ","
        try:
            user_csv_df = pl.read_csv(path, separator=delimiter)
        except Exception as e:
            print("CSV read error:", e)
            return e
        return user_csv_df

    @staticmethod
    def user_input_xl():
        path = page.var_file_path
        sheet = getattr(page, "var_excel_sheet", "") or None
        try:
            user_xl_df = pl.read_excel(path, sheet_name=sheet)
        except Exception as e:
            print("Excel read error:", e)
            return e
        return user_xl_df


# ════════════════════════════════════════════════════════════════════════════
#  2. MICROSOFT SQL SERVER CONNECTION & OPERATIONS
# ════════════════════════════════════════════════════════════════════════════
class MsSQL:
    @staticmethod
    def creds():
        SERVER = page.var_mssql_server
        PORT = page.var_mssql_port or "1433"
        DATABASE = page.var_mssql_database
        USERNAME = page.var_mssql_username
        PASSWORD = page.var_mssql_password
        DRIVER = "{ODBC Driver 18 for SQL Server}"
        return SERVER, PORT, DATABASE, USERNAME, PASSWORD, DRIVER

    @staticmethod
    def main_connection():
        SERVER, PORT, DATABASE, USERNAME, PASSWORD, DRIVER = MsSQL.creds()
        server_str = f"{SERVER},{PORT}" if PORT and PORT != "1433" else SERVER
        connection_string = (
            f"DRIVER={DRIVER};"
            f"SERVER={server_str};"
            f"DATABASE={DATABASE};"
            f"UID={USERNAME};"
            f"PWD={PASSWORD};"
            "TrustServerCertificate=yes;"
            "LoginTimeout=5;"
        )
        return pyodbc.connect(connection_string)

    @staticmethod
    def test_connections() -> tuple[bool, str]:
        """Tests MSSQL server connection. Returns (success: bool, message: str)."""
        try:
            conn = MsSQL.main_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.close()
            conn.close()
            print("SQL server connected successfully")
            return True, "SQL Server connected successfully."
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            print(f"connection failed: {e}")
            return False, err_msg

    @staticmethod
    def test_connection() -> tuple[bool, str]:
        """Alias for test_connections."""
        return MsSQL.test_connections()

    @staticmethod
    def fetch_tables() -> list[str]:
        """Fetches list of table names from MSSQL database."""
        conn = MsSQL.main_connection()
        cur = conn.cursor()
        query = (
            "SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS full_name "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME;"
        )
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [r[0] for r in rows]

    @staticmethod
    def fetch_table_data(table_name: str, limit: int = 1000) -> pl.DataFrame:
        """Fetches the first `limit` rows of a table as a Polars DataFrame."""
        query = f"SELECT TOP {limit} * FROM {table_name};"
        return MsSQL.execute_view_query(query)

    @staticmethod
    def execute_view_query(query: str) -> pl.DataFrame:
        """Executes a strictly read-only query and returns a Polars DataFrame."""
        is_ok, err = validate_readonly_query(query)
        if not is_ok:
            raise PermissionError(err)

        conn = MsSQL.main_connection()
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = [list(r) for r in cur.fetchall()] if cur.description else []
        cur.close()
        conn.close()
        return pl.DataFrame(rows, schema=columns, orient="row")


# ════════════════════════════════════════════════════════════════════════════
#  3. POSTGRESQL CONNECTION & OPERATIONS
# ════════════════════════════════════════════════════════════════════════════
class PostgreSQL:
    @staticmethod
    def creds():
        HOST = page.var_postgres_host
        DATABASE = page.var_postgres_database
        USERNAME = page.var_postgres_username
        PASSWORD = page.var_postgres_password
        PORT = page.var_postgres_port or "5432"
        return HOST, DATABASE, USERNAME, PASSWORD, PORT

    @staticmethod
    def main_connection():
        HOST, DATABASE, USERNAME, PASSWORD, PORT = PostgreSQL.creds()
        return psycopg2.connect(
            host=HOST,
            database=DATABASE,
            user=USERNAME,
            password=PASSWORD,
            port=PORT,
            connect_timeout=5,
        )

    @staticmethod
    def test_connection() -> tuple[bool, str]:
        """Tests PostgreSQL connection. Returns (success: bool, message: str)."""
        try:
            with PostgreSQL.main_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1;")
                    result = cursor.fetchone()
                    print("PostgreSQL connected:", result[0])
                    return True, "PostgreSQL connected successfully."
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            print(f"Connection failed: {e}")
            return False, err_msg

    @staticmethod
    def fetch_tables() -> list[str]:
        """Fetches list of base table names from PostgreSQL database."""
        with PostgreSQL.main_connection() as conn:
            with conn.cursor() as cursor:
                query = (
                    "SELECT table_schema || '.' || table_name AS full_name "
                    "FROM information_schema.tables "
                    "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') "
                    "ORDER BY table_schema, table_name;"
                )
                cursor.execute(query)
                rows = cursor.fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def fetch_table_data(table_name: str, limit: int = 1000) -> pl.DataFrame:
        """Fetches the first `limit` rows of a table as a Polars DataFrame."""
        query = f"SELECT * FROM {table_name} LIMIT {limit};"
        return PostgreSQL.execute_view_query(query)

    @staticmethod
    def execute_view_query(query: str) -> pl.DataFrame:
        """Executes a strictly read-only query and returns a Polars DataFrame."""
        is_ok, err = validate_readonly_query(query)
        if not is_ok:
            raise PermissionError(err)

        with PostgreSQL.main_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall() if cursor.description else []
        return pl.DataFrame(rows, schema=columns, orient="row")


# ════════════════════════════════════════════════════════════════════════════
#  4. REST API CLIENT & OPERATIONS
# ════════════════════════════════════════════════════════════════════════════
class RestAPI:
    @staticmethod
    def params():
        URL = getattr(page, "var_api_url", "")
        METHOD = getattr(page, "var_api_method", "GET") or "GET"
        HEADERS_RAW = getattr(page, "var_api_headers", "") or ""
        PAYLOAD_RAW = getattr(page, "var_api_payload", "") or ""
        return URL, METHOD, HEADERS_RAW, PAYLOAD_RAW

    @staticmethod
    def parse_headers(raw: str) -> dict:
        if not raw or not raw.strip():
            return {}
        raw = raw.strip()
        if raw.startswith("{"):
            try:
                return json.loads(raw)
            except Exception:
                pass
        headers = {}
        for line in raw.splitlines():
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        return headers

    @staticmethod
    def parse_payload(raw: str):
        if not raw or not raw.strip():
            return None
        raw = raw.strip()
        if raw.startswith(("{", "[")):
            try:
                return json.loads(raw)
            except Exception:
                pass
        return raw

    @staticmethod
    def json_to_dataframe(parsed) -> pl.DataFrame:
        """Converts arbitrary JSON data structure into a tabular Polars DataFrame."""
        if isinstance(parsed, list):
            if not parsed:
                return pl.DataFrame()
            if isinstance(parsed[0], dict):
                return pl.DataFrame(parsed)
            return pl.DataFrame({"value": parsed})
        elif isinstance(parsed, dict):
            common_keys = ["data", "items", "results", "records", "rows", "values", "products", "users", "posts"]
            for k in common_keys:
                if k in parsed and isinstance(parsed[k], list) and len(parsed[k]) > 0 and isinstance(parsed[k][0], dict):
                    return pl.DataFrame(parsed[k])
            for k, v in parsed.items():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    return pl.DataFrame(v)
            return pl.DataFrame([parsed])
        return pl.DataFrame({"value": [parsed]})

    @staticmethod
    def fetch_data() -> pl.DataFrame:
        """Fetches data from configured REST API endpoint and returns a Polars DataFrame."""
        url, method, headers_raw, payload_raw = RestAPI.params()
        if not url:
            raise ValueError("API URL cannot be empty. Please enter an endpoint URL.")

        headers = RestAPI.parse_headers(headers_raw)
        payload = RestAPI.parse_payload(payload_raw)

        if not any(k.lower() == "user-agent" for k in headers):
            headers["User-Agent"] = "EDETH-Analytics/1.0"

        req_data = None
        if method.upper() == "POST" and payload is not None:
            if isinstance(payload, (dict, list)):
                req_data = json.dumps(payload).encode("utf-8")
                if not any(k.lower() == "content-type" for k in headers):
                    headers["Content-Type"] = "application/json"
            else:
                req_data = str(payload).encode("utf-8")

        req = urllib.request.Request(url, data=req_data, headers=headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_bytes = resp.read()
            text = raw_bytes.decode("utf-8", errors="replace")

        try:
            parsed = json.loads(text)
            return RestAPI.json_to_dataframe(parsed)
        except Exception:
            try:
                return pl.read_csv(io.StringIO(text))
            except Exception:
                return pl.DataFrame({"raw_response": [text]})

