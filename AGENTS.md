# AGENTS.md – Agentic Coding Guidelines

## 1. Build, Lint, Test

**Build**  
- `python -m pip install -e .` – install the package in editable mode.  
- `python -m build` – create source and wheel distributions.  
- `python setup.py sdist bdist_wheel` – legacy alternative for source & binary wheels.  

**Lint**  
- `ruff .` – fast linting and auto‑format check.  
- `black --check .` – enforce formatting style.  
- `mypy --strict .` – static type checking.  

**Test**  
- Run the full test suite: `pytest`  
- Run tests with coverage: `pytest --cov=.`  
- **Single test** (replace `path/to/test_mod.py` and `test_func`):  
  ```bash
  pytest path/to/test_mod.py::test_func -vv
  ```  
- Run a single test file: `pytest path/to/test_mod.py`  
- Run tests in parallel: `pytest -n auto`  

**CI Script Example**  
```bash
# Install dependencies
python -m pip install -r requirements.txt -r dev-requirements.txt

# Lint & type‑check
ruff .
black --check .
mypy --strict .

# Run tests
pytest --cov=.
```

## 2. Code Style Guidelines

### Imports
- Order: standard library → third‑party → local modules.  
- Separate groups with a blank line.  
- Use absolute imports; avoid `from module import *`.  
- Prefer explicit imports: `import os` over `import os as _`.

### Formatting
- Run `black` with line length `88`.  
- Indentation: 4 spaces, no tabs.  
- Remove trailing whitespace; ensure final newline at EOF.  

### Typing & Naming
- Add type hints to all public APIs.  
- Functions / variables: `snake_case`.  
- Classes: `PascalCase`.  
- Constants: `UPPER_SNAKE_CASE`.  
- Private symbols: leading underscore `_private_var`.  

### Error Handling
- Define custom exceptions in `exceptions.py`.  
- Raise specific exceptions; avoid bare `except:`.  
- Include contextual info (e.g., request ID) in error messages.  
- Log errors with structured logging (JSON).  

### Logging
- Use module‑level logger: `logger = logging.getLogger(__name__)`.  
- Log structured messages with key‑value pairs.  
- Propagate logs to stdout/json for CI ingestion.  

### Dependencies
- Pin exact versions in `requirements.txt`.  
- Use `pip-tools` (`requirements.in` → `requirements.txt`).  
- Keep `dev-requirements.txt` for testing/linting tools.  

### Testing
- Unit tests under `tests/unit/`.  
- Integration tests under `tests/integration/`.  
- Use `pytest` fixtures for reusable setup.  
- Mock external services with `pytest-mock`.  
- Enforce coverage threshold: `--cov-fail-under=80`.  

### Documentation
- Docstrings in Google style.  
- Update `README.md` for every public API change.  
- Generate docs with `sphinx-build -b html docs docs/_build`.  

### Git & Commit Conventions
- Message format: `<type>(<scope>): <subject>` (e.g., `feat(auth): add token refresh`).  
- Supported types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.  
- Prefix with emoji for readability: `:rocket:` for features, `:bug:` for fixes.  
- Keep commits atomic – one logical change per commit.  

### Release Process
- Bump version in `pyproject.toml` using SemVer.  
- Create a git tag: `git tag vX.Y.Z`.  
- Push tags: `git push --follow-tags`.  
- CI builds and publishes to TestPyPI/PyPI.  

### Pre‑Commit Hooks (recommended)
Add to `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks: [{id: black}]
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.5.1
    hooks: [{id: ruff}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks: [{id: mypy}]
```

### Additional Rules
- No hard‑coded secrets; use env vars or secret managers.  
- Do not commit generated files (`__pycache__`, `*.pyc`, `.pyo`).  
- Do not modify files outside the repository root without approval.  
- Ensure CI passes before merging.  

## 3. Cursor / Copilot Rules
*No Cursor rules or Copilot instructions were found in the repository.*

## 4. Quick Reference Commands
- Build: `python -m pip install -e .`  
- Lint: `ruff . && black --check .`  
- Type‑check: `mypy --strict .`  
- Test (single): `pytest path/to/test_mod.py::test_func -vv`  
- Test (all): `pytest`  
- Coverage: `pytest --cov=.`  

## 5. Frequently Used Commands
- List changed files: `git status`  
- View diff: `git diff --cached`  
- Amend last commit (use carefully): `git commit --amend`  

## 6. Agent Configuration
- Agent type: `general` for multi‑step tasks, `explore` for fast searches.  
- Memory limit: 4096 tokens per session.  
- Timeout: 120 seconds for Bash commands.  

## 7. Security Checklist
- Verify no secrets in diffs: `git diff --cached | grep -E "password|key|secret"`  
- Run `pre-commit run --all-files` before push.  
- Ensure dependencies are up‑to‑date with `pip list --outdated`.  

## 8. Example Workflow
1. `git checkout -b feature/xyz`  
2. Implement change  
3. `ruff . && black .`  
4. `pytest -k test_xyz`  
5. `git add . && git commit -m "feat(xyz): brief desc"`  
6. Open PR  

*End of AGENTS.md*