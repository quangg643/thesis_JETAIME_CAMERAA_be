import urllib.parse

# 1. Configuration details based on your setup (SSMS 22, local, Windows Auth)
DRIVER = "ODBC Driver 17 for SQL Server"  # Standard driver bundled with SSMS 22
SERVER = "localhost\\SQLEXPRESS"
DATABASE = "jetaimee-cameraa"

# 2. Build the connection parameters for Windows Authentication
params = urllib.parse.quote_plus(
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"Trusted_Connection=yes;"
    f"TrustServerCertificate=yes;"  # Essential for Driver 18 local connections
)

# 3. Format it for SQLAlchemy
connection_string = f"mssql+pyodbc:///?odbc_connect={params}"

print("\n=== COPY THE LINE BELOW FOR YOUR .env FILE ===\n")
print(f"{connection_string}")
print("\n=============================================\n")