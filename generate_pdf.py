from fpdf import FPDF


class FinExPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "FinEx Project Documentation", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 14)
        self.set_fill_color(230, 230, 250)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(4)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5, text)
        self.ln(3)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.cell(5)
        self.cell(0, 5, f"  * {text}", new_x="LMARGIN", new_y="NEXT")

    def code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(245, 245, 245)
        for line in text.split("\n"):
            self.cell(5)
            self.cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)


pdf = FinExPDF()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=15)

# ============ PAGE 1: OVERVIEW ============
pdf.add_page()
pdf.chapter_title("1. Project Overview")
pdf.body_text(
    "FinEx is a full-stack fintech platform built for learning and showcasing modern "
    "software engineering practices. It includes a React web frontend, Flutter mobile app, "
    "FastAPI Python backend, Databricks data layer, and AI capabilities."
)

pdf.section_title("GitHub Repository")
pdf.body_text("https://github.com/IgnAite-Showcase/Finex.git")

pdf.section_title("Tech Stack")
pdf.bullet("Frontend: React + TypeScript")
pdf.bullet("Mobile: Flutter + Dart")
pdf.bullet("Backend: FastAPI (Python)")
pdf.bullet("Database: Databricks (Unity Catalog, Delta Tables)")
pdf.bullet("Authentication: JWT (python-jose) + bcrypt")
pdf.bullet("Testing: pytest (25 tests passing)")
pdf.bullet("Architecture: Clean Architecture (Router > Service > Repository)")
pdf.ln(5)

pdf.section_title("Project Folder Structure")
pdf.code_block(
    "Finex/\n"
    "|-- frontend-react/    (React web app)\n"
    "|-- mobile-flutter/    (Flutter mobile app)\n"
    "|-- backend/           (FastAPI Python backend)\n"
    "|-- ai/                (AI/ML services)\n"
    "|-- infrastructure/    (DevOps, IaC)\n"
    "|-- docs/              (Documentation)\n"
    "|-- scripts/           (Utility scripts)\n"
    "|-- README.md"
)

# ============ PAGE 2: BACKEND ARCHITECTURE ============
pdf.add_page()
pdf.chapter_title("2. Backend Architecture")

pdf.body_text(
    "The backend follows Clean Architecture principles. Each layer has a single responsibility "
    "and dependencies only flow inward."
)

pdf.section_title("Architecture Flow")
pdf.code_block(
    "React / Flutter (Client)\n"
    "       |\n"
    "       v\n"
    "Router (HTTP handling only)\n"
    "       |\n"
    "       v\n"
    "Service (Business logic, pure Python)\n"
    "       |\n"
    "       v\n"
    "Repository (Data access layer)\n"
    "       |\n"
    "       v\n"
    "Database (Databricks / In-memory)"
)

pdf.section_title("Backend Folder Structure")
pdf.code_block(
    "backend/app/\n"
    "|-- auth/           (JWT, password, security)\n"
    "|-- config/         (settings, database, logging)\n"
    "|-- core/           (exceptions, responses, handlers)\n"
    "|-- models/         (internal Python models)\n"
    "|-- repositories/   (data access layer)\n"
    "|-- services/       (business logic)\n"
    "|-- routers/        (API endpoints)\n"
    "|-- schemas/        (request/response validation)\n"
    "|-- main.py         (app entry point)"
)

pdf.section_title("Key Design Decisions")
pdf.bullet("Router: Only HTTP handling. No business logic.")
pdf.bullet("Service: Pure Python. No FastAPI imports.")
pdf.bullet("Repository: In-memory now, Databricks later. Same interface.")
pdf.bullet("All responses use APIResponse.success() or APIResponse.error()")
pdf.bullet("All errors raise FinExException subclasses")
pdf.bullet("Configuration loaded from .env via pydantic-settings")

# ============ PAGE 3: AUTHENTICATION ============
pdf.add_page()
pdf.chapter_title("3. Authentication System (JWT)")

pdf.body_text(
    "The authentication system uses JSON Web Tokens (JWT) with access and refresh tokens. "
    "Passwords are hashed using bcrypt via passlib."
)

pdf.section_title("Auth Flow")
pdf.code_block(
    "1. Register  -> Hash Password -> Store User -> Return Tokens\n"
    "2. Login     -> Verify Password -> Generate JWT -> Return Tokens\n"
    "3. /me       -> Verify JWT -> Return User Data\n"
    "4. Refresh   -> Validate Refresh Token -> New Access Token\n"
    "5. Logout    -> Client discards tokens"
)

pdf.section_title("API Endpoints")
pdf.code_block(
    "POST /api/v1/auth/register   - Register new user\n"
    "POST /api/v1/auth/login      - Login with email/password\n"
    "GET  /api/v1/auth/me         - Get current user (protected)\n"
    "POST /api/v1/auth/refresh    - Refresh access token\n"
    "POST /api/v1/auth/logout     - Logout (protected)"
)

pdf.section_title("Security Features")
pdf.bullet("Passwords hashed with bcrypt (never stored plain text)")
pdf.bullet("JWT access tokens expire in 30 minutes")
pdf.bullet("Refresh tokens expire in 7 days")
pdf.bullet("Protected routes require Bearer token in Authorization header")
pdf.bullet("Custom BearerTokenScheme validates token format")
pdf.bullet("AuthenticationException raised for invalid tokens")

pdf.section_title("Auth Files")
pdf.code_block(
    "auth/password.py      - hash_password(), verify_password()\n"
    "auth/jwt_handler.py   - create_access_token(), create_refresh_token(), decode_token()\n"
    "auth/dependencies.py  - get_current_user() FastAPI dependency\n"
    "auth/security.py      - BearerTokenScheme, extract_token()\n"
    "services/auth_service.py - register(), login(), refresh(), logout()"
)

# ============ PAGE 4: API STANDARD ============
pdf.add_page()
pdf.chapter_title("4. API Response Standard")

pdf.body_text(
    "Every API in FinEx returns the same JSON structure. This makes it easy for "
    "React and Flutter teams to handle responses consistently."
)

pdf.section_title("Success Response")
pdf.code_block(
    '{\n'
    '  "success": true,\n'
    '  "message": "Operation completed successfully",\n'
    '  "data": { ... }\n'
    '}'
)

pdf.section_title("Error Response")
pdf.code_block(
    '{\n'
    '  "success": false,\n'
    '  "message": "User not found",\n'
    '  "error_code": "USER_NOT_FOUND"\n'
    '}'
)

pdf.section_title("Exception Hierarchy")
pdf.code_block(
    "FinExException (base)\n"
    "|-- UserNotFoundException\n"
    "|-- AuthenticationException\n"
    "|-- PortfolioException\n"
    "|-- AIException\n"
    "|-- DatabricksException\n"
    "|-- NotFoundException\n"
    "|-- UnauthorizedException\n"
    "|-- ForbiddenException\n"
    "|-- BadRequestException"
)

# ============ PAGE 5: DATABRICKS ============
pdf.add_page()
pdf.chapter_title("5. Databricks Integration")

pdf.body_text(
    "The project uses Databricks Unity Catalog for data storage. "
    "Tables are stored as Delta tables in the finex_dev catalog."
)

pdf.section_title("Catalog & Schema")
pdf.code_block(
    "Catalog: finex_dev\n"
    "Schema:  core"
)

pdf.section_title("Tables Created")
pdf.code_block(
    "finex_dev.core.users          - user_id, email, password_hash, is_active, timestamps\n"
    "finex_dev.core.user_profiles  - profile_id, user_id, first_name, last_name, phone\n"
    "finex_dev.core.portfolios     - portfolio_id, user_id, name, description, type\n"
    "finex_dev.core.paper_accounts - account_id, user_id, account_name, balance, currency"
)

pdf.section_title("Connection Layer")
pdf.body_text(
    "backend/app/config/database.py provides get_connection(), execute_query(), "
    "and execute_write() functions that connect to the Databricks SQL Warehouse."
)

pdf.section_title("Databricks Workspace")
pdf.code_block(
    "/Users/shivrajdhote4452@gmail.com/Finex/\n"
    "|-- notebooks/\n"
    "    |-- ingestion/\n"
    "    |-- transformations/\n"
    "    |-- ai/\n"
    "    |-- analytics/"
)

# ============ PAGE 6: REQUEST VALIDATION ============
pdf.add_page()
pdf.chapter_title("6. Request Validation (Pydantic)")

pdf.body_text(
    "All incoming requests are validated using Pydantic schemas before reaching "
    "business logic. Invalid requests return 422 with detailed error messages."
)

pdf.section_title("Validation Rules")
pdf.bullet("Email: must be valid format (EmailStr)")
pdf.bullet("Password: minimum 8 characters, maximum 64")
pdf.bullet("Name: minimum 2 characters, maximum 100")
pdf.bullet("All fields are required unless marked Optional")
pdf.ln(3)

pdf.section_title("Example: Invalid Request")
pdf.code_block(
    'POST /api/v1/auth/register\n'
    '{"email": "abc", "password": "1", "name": ""}\n'
    '\n'
    'Response: 422 Unprocessable Entity\n'
    '- email: value is not a valid email\n'
    '- password: String should have at least 8 characters\n'
    '- name: String should have at least 2 characters'
)

# ============ PAGE 7: TESTING ============
pdf.add_page()
pdf.chapter_title("7. Testing (25 Tests Passing)")

pdf.body_text("All tests use pytest and FastAPI TestClient.")

pdf.section_title("Test Categories")
pdf.bullet("Repository Tests: Create, Find, Duplicate, Delete user")
pdf.bullet("Password Tests: Hash, Verify")
pdf.bullet("JWT Tests: Create token, Decode, Expired, Invalid, Refresh")
pdf.bullet("Auth Tests: Register, Duplicate email, Login, Wrong password, Invalid email")
pdf.bullet("Auth Tests: Protected route, No token, Refresh token, Logout")
pdf.bullet("E2E Flow Test: Full register-login-me-refresh-logout flow")
pdf.bullet("Health Test: Health endpoint returns correct format")
pdf.bullet("Demo Test: Exception handler returns clean error JSON")
pdf.ln(3)

pdf.section_title("Run Tests")
pdf.code_block(
    "cd backend\n"
    ".\\venv\\Scripts\\Activate.ps1\n"
    "pytest tests/"
)

# ============ PAGE 8: SETUP GUIDE ============
pdf.add_page()
pdf.chapter_title("8. Setup Guide")

pdf.section_title("Prerequisites")
pdf.bullet("Python 3.9+")
pdf.bullet("Git")
pdf.bullet("Databricks account (optional for local dev)")
pdf.ln(3)

pdf.section_title("Steps")
pdf.code_block(
    "1. Clone the repo\n"
    "   git clone https://github.com/IgnAite-Showcase/Finex.git\n"
    "\n"
    "2. Navigate to backend\n"
    "   cd Finex/backend\n"
    "\n"
    "3. Create virtual environment\n"
    "   python -m venv venv\n"
    "\n"
    "4. Activate it\n"
    "   .\\venv\\Scripts\\Activate.ps1\n"
    "\n"
    "5. Install dependencies\n"
    "   pip install -r requirements.txt\n"
    "\n"
    "6. Copy .env.example to .env and fill values\n"
    "   copy .env.example .env\n"
    "\n"
    "7. Run the server\n"
    "   uvicorn app.main:app --reload\n"
    "\n"
    "8. Open Swagger docs\n"
    "   http://127.0.0.1:8000/docs\n"
    "\n"
    "9. Run tests\n"
    "   pytest tests/"
)

# ============ PAGE 9: PACKAGES ============
pdf.add_page()
pdf.chapter_title("9. Required Packages")

pdf.code_block(
    "fastapi==0.116.1\n"
    "uvicorn[standard]==0.35.0\n"
    "python-dotenv==1.1.1\n"
    "pydantic==2.11.7\n"
    "pydantic-settings==2.10.1\n"
    "pytest==8.4.1\n"
    "httpx==0.28.1\n"
    "email-validator==2.3.0\n"
    "bcrypt==4.2.1\n"
    "python-jose[cryptography]==3.5.0\n"
    "passlib[bcrypt]==1.7.4\n"
    "databricks-sql-connector==4.3.0"
)

pdf.section_title("Package Purposes")
pdf.bullet("fastapi - Web framework")
pdf.bullet("uvicorn - ASGI server")
pdf.bullet("pydantic/pydantic-settings - Validation & config")
pdf.bullet("python-jose - JWT token handling")
pdf.bullet("passlib + bcrypt - Password hashing")
pdf.bullet("email-validator - Email format validation")
pdf.bullet("databricks-sql-connector - Databricks connection")
pdf.bullet("pytest + httpx - Testing")

# ============ PAGE 10: CODING STANDARDS ============
pdf.add_page()
pdf.chapter_title("10. Coding Standards")

pdf.bullet("SOLID Principles")
pdf.bullet("Clean Architecture (Router > Service > Repository)")
pdf.bullet("Type Hints on all functions")
pdf.bullet("Docstrings on all classes and public functions")
pdf.bullet("Dependency Injection via FastAPI Depends()")
pdf.bullet("No hardcoded secrets (all in .env)")
pdf.bullet("Configuration from .env via pydantic-settings")
pdf.bullet("Logging using project logger (not print)")
pdf.bullet("Standard APIResponse format for all endpoints")
pdf.bullet("Standard FinExException handling for all errors")
pdf.bullet("Swagger documentation with examples on every endpoint")
pdf.ln(5)

pdf.section_title("Next Steps")
pdf.bullet("Connect auth to Databricks (replace in-memory repository)")
pdf.bullet("Build Portfolio module")
pdf.bullet("Build Paper Trading module")
pdf.bullet("Build AI Chat module")
pdf.bullet("Build React frontend with login/register")
pdf.bullet("Build Flutter mobile app")

# Save
pdf.output(r"C:\Users\Shivraj Dhote\Desktop\Finex\FinEx_Project_Documentation.pdf")
print("PDF saved successfully!")
