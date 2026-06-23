# Developer Guide: Vigilant

## Setup Instructions

1. **Prerequisites**
   - Python 3.12+
   - Node.js 20+
   - SQLite (Dev) / PostgreSQL (Prod)

2. **Backend Setup**
   ```bash
   python -m venv .venv
   source .venv/bin/activate # or .venv\Scripts\activate on Windows
   pip install -e .[dev]
   alembic upgrade head
   python backend/main.py
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Development Standards
- **Style:** Python code strictly follows `ruff` standards. Frontend follows standard React hooks rules and Tailwind utility best practices.
- **Cross-Platform:** Never use `os.system()` with OS-specific binaries. Use the `OSBridgeAdapter` standard methods.
- **Process Actions:** Do not invoke OS process kills directly. Always initiate a request via `request_process_suspend()` for the Analyst Approval workflow.

## Running Tests
```bash
pytest tests/
npm --prefix frontend run build
```
