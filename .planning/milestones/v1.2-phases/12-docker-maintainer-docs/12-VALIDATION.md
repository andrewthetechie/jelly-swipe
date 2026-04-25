# Phase 12: Docker & maintainer docs - Validation

**Created:** 2026-04-24
**Phase:** 12-docker-maintainer-docs
**Validation approach:** Manual verification + automated test scripts (Wave 0)

## Validation Summary

This phase validates three core requirements:
1. **DOCK-01:** Dockerfile uses uv for dependency installation, container runs from jellyswipe package, exposes port 5005, supports /app/data volume
2. **DOC-01:** README.md has Development section documenting uv workflows
3. **DIST-01:** No PyPI publishing workflow or documentation exists

**Validation status:** Pending implementation (no existing test infrastructure)

## Success Criteria

### DOCK-01: Docker Integration

- [ ] Docker build completes successfully without errors
- [ ] Container starts and Gunicorn listens on port 5005
- [ ] Container can serve HTTP requests on port 5005
- [ ] `/app/data` directory exists and is writable
- [ ] SQLite database can be created in `/app/data/jellyswipe.db`
- [ ] Dependencies are installed from `uv.lock` (not pyproject.toml directly)
- [ ] Final image does not contain uv binary (multi-stage build optimization)
- [ ] Package data (templates/, static/) is present and accessible
- [ ] Gunicorn entry point `jellyswipe:app` works correctly
- [ ] Existing Docker Compose configuration from README still works

### DOC-01: Maintainer Documentation

- [ ] README.md has a "## Development" section after "## Deployment"
- [ ] Development section documents `uv sync` for first-time setup
- [ ] Development section documents `uv run python -m jellyswipe` for local dev server
- [ ] Development section documents `uv run gunicorn jellyswipe:app` for production-style testing
- [ ] Development section documents `uv add <package>` for adding dependencies
- [ ] Development section documents `uv lock --upgrade` for updating lockfile
- [ ] Development section mentions Python 3.13 requirement
- [ ] Deployment section remains unchanged (operator-facing docs intact)
- [ ] No references to `pip install -r requirements.txt` in Development section

### DIST-01: PyPI Story Avoidance

- [ ] No PyPI publishing workflow in `.github/workflows/`
- [ ] No reference to `pip install jellyswipe` in README.md
- [ ] No PyPI badges or links in README.md
- [ ] `requirements.txt` is removed (or has no remaining references)
- [ ] All install paths remain Docker or source checkout

## Validation Tests

### Test 1: Docker Build (DOCK-01)

**Purpose:** Verify Dockerfile builds successfully with uv

**Manual verification:**
```bash
# Navigate to project root
cd /Users/andrew/Documents/code/kino-swipe

# Build the image
docker build -t jellyswipe-test:latest .

# Expected output:
# - Build completes without errors
# - No "pip install" commands in build output (only uv sync)
# - Final image size should be smaller than previous single-stage build
```

**Success indicators:**
- Exit code 0
- Build log shows "uv sync --locked" executing
- Build log shows multi-stage build (AS builder)
- No uv binary in final image layers

**Failure indicators:**
- Build fails with "uv: command not found"
- Build fails with "ModuleNotFoundError: No module named 'jellyswipe'"
- Build fails with uv.lock errors
- Final image contains /uv or /uvx binaries

---

### Test 2: Container Startup (DOCK-01)

**Purpose:** Verify container starts and listens on port 5005

**Manual verification:**
```bash
# Run container with minimal environment
docker run -d \
  --name jellyswipe-test \
  -p 5005:5005 \
  -e FLASK_SECRET=test-secret-for-validation \
  -e TMDB_API_KEY=test-key-for-validation \
  -e MEDIA_PROVIDER=plex \
  jellyswipe-test:latest

# Wait for startup
sleep 5

# Check if container is running
docker ps | grep jellyswipe-test

# Check Gunicorn logs
docker logs jellyswipe-test

# Test HTTP endpoint
curl -I http://localhost:5005/

# Clean up
docker stop jellyswipe-test
docker rm jellyswipe-test
```

**Success indicators:**
- Container status is "Up" in `docker ps`
- Gunicorn logs show "Listening at: http://0.0.0.0:5005"
- `curl -I` returns HTTP 200 or 302 (redirect)
- No import errors or module not found errors in logs

**Failure indicators:**
- Container exits immediately
- Gunicorn fails with "ImportError" or "ModuleNotFoundError"
- Port 5005 is not exposed or not listening
- HTTP requests timeout or return connection refused

---

### Test 3: /app/data Volume Support (DOCK-01)

**Purpose:** Verify /app/data directory exists and is writable

**Manual verification:**
```bash
# Run container with volume mount
docker run -d \
  --name jellyswipe-test \
  -p 5005:5005 \
  -e FLASK_SECRET=test-secret \
  -e TMDB_API_KEY=test-key \
  -e MEDIA_PROVIDER=plex \
  -v $(pwd)/test-data:/app/data \
  jellyswipe-test:latest

# Wait for startup and DB creation
sleep 5

# Check if database was created
ls -lh test-data/

# Verify database is a valid SQLite file
sqlite3 test-data/jellyswipe.db ".tables"

# Clean up
docker stop jellyswipe-test
docker rm jellyswipe-test
rm -rf test-data
```

**Success indicators:**
- `test-data/jellyswipe.db` file is created
- SQLite shows valid tables (e.g., sessions, matches)
- No permission errors in logs
- Database persists across container restarts

**Failure indicators:**
- "Permission denied" errors in logs
- Database file is not created
- Container cannot write to /app/data
- Database is created in wrong location

---

### Test 4: Package Data Accessibility (DOCK-01)

**Purpose:** Verify templates/ and static/ are accessible

**Manual verification:**
```bash
# Run container
docker run -d \
  --name jellyswipe-test \
  -p 5005:5005 \
  -e FLASK_SECRET=test-secret \
  -e TMDB_API_KEY=test-key \
  -e MEDIA_PROVIDER=plex \
  jellyswipe-test:latest

sleep 5

# Check if static files are accessible
curl -I http://localhost:5005/static/manifest.json

# Check if templates are rendered (fetch main page)
curl -s http://localhost:5005/ | head -20

# Clean up
docker stop jellyswipe-test
docker rm jellyswipe-test
```

**Success indicators:**
- `/static/manifest.json` returns HTTP 200
- Main page returns HTML (not 404 or 500)
- No "TemplateNotFound" errors in logs
- Static files (images, CSS, JS) load correctly

**Failure indicators:**
- 404 errors for static files
- "TemplateNotFound" errors in logs
- Main page returns error or blank response
- Static assets missing or broken

---

### Test 5: README Development Section (DOC-01)

**Purpose:** Verify README has Development section with uv commands

**Manual verification:**
```bash
# Check for Development section
grep -n "## Development" README.md

# Check for required uv commands
grep "uv sync" README.md
grep "uv run python -m jellyswipe" README.md
grep "uv run gunicorn" README.md
grep "uv add" README.md
grep "uv lock --upgrade" README.md

# Check for Python 3.13 requirement in Development section
grep -A 20 "## Development" README.md | grep "3.13"

# Check that Development section comes after Deployment section
grep -n "## Deployment" README.md
grep -n "## Development" README.md

# Verify no pip install references in Development section
sed -n '/## Development/,/## /p' README.md | grep "pip install"
# Should return nothing (or only in comments explaining deprecation)
```

**Success indicators:**
- "## Development" section exists
- All required uv commands are documented
- Python 3.13 requirement is mentioned
- Development section appears after Deployment section
- No `pip install` commands in Development section

**Failure indicators:**
- No "## Development" section
- Missing uv commands
- Pip commands referenced instead of uv
- Python 3.13 not mentioned
- Development section in wrong location

---

### Test 6: No PyPI References (DIST-01)

**Purpose:** Verify no PyPI publishing workflow or documentation exists

**Manual verification:**
```bash
# Check GitHub workflows for PyPI publishing
ls -la .github/workflows/
cat .github/workflows/docker-image.yml | grep -i pypi
cat .github/workflows/release-ghcr.yml | grep -i pypi

# Check README for PyPI references
grep -i "pypi" README.md
grep -i "pip install jellyswipe" README.md

# Check for PyPI badges
grep -i "pypi.org\|pypip.in" README.md

# Verify requirements.txt is removed or deprecation noted
ls -la requirements.txt 2>/dev/null
cat requirements.txt 2>/dev/null | head -5
```

**Success indicators:**
- No PyPI-related workflows in `.github/workflows/`
- No `pip install jellyswipe` references in README
- No PyPI badges or links in README
- `requirements.txt` is removed or has deprecation comment

**Failure indicators:**
- PyPI publishing workflow found
- README suggests `pip install jellyswipe`
- PyPI badges or links present
- `requirements.txt` referenced as primary install method

---

### Test 7: Existing Docker Compose Still Works (DOCK-01)

**Purpose:** Verify existing deployment configuration from README still works

**Manual verification:**
```bash
# Extract docker-compose config from README
# (Manual: Copy the docker-compose.yml section from README)

# Create test docker-compose.yml
cat > docker-compose.test.yml << 'EOF'
services:
  jelly-swipe:
    image: jellyswipe-test:latest
    container_name: jelly-swipe-test
    ports:
      - "5005:5005"
    environment:
      - MEDIA_PROVIDER=plex
      - PLEX_URL=https://test-plex:32400
      - PLEX_TOKEN=test-token
      - FLASK_SECRET=test-secret
      - TMDB_API_KEY=test-key
    volumes:
      - ./test-data:/app/data
      - ./test-static:/app/static
    restart: unless-stopped
EOF

# Start with docker-compose
docker-compose -f docker-compose.test.yml up -d

# Wait for startup
sleep 5

# Test endpoint
curl -I http://localhost:5005/

# Clean up
docker-compose -f docker-compose.test.yml down
rm docker-compose.test.yml
rm -rf test-data test-static
```

**Success indicators:**
- docker-compose starts container successfully
- Port 5005 is accessible
- Volume mounts work (test-data and test-static directories)
- Container restarts correctly

**Failure indicators:**
- docker-compose fails to start
- Port conflicts or binding errors
- Volume mount errors
- Container exits immediately

---

## Automated Test Scripts (Wave 0)

The following test scripts can be automated once Wave 0 test infrastructure is established. These require pytest and pytest-docker or similar testing framework.

### test_docker.py (DOCK-01)

```python
"""
Tests for Docker integration (DOCK-01)
Requires: pytest, docker
"""

import subprocess
import time
import requests
import docker
import pytest
import sqlite3
import os

@pytest.fixture(scope="module")
def docker_image():
    """Build Docker image and return image ID"""
    result = subprocess.run(
        ["docker", "build", "-t", "jellyswipe-test:latest", "."],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Docker build failed: {result.stderr}"
    assert "uv sync" in result.stdout, "uv sync not found in build output"
    return "jellyswipe-test:latest"

@pytest.fixture
def running_container(docker_image):
    """Start a container for testing"""
    client = docker.from_env()
    container = client.containers.run(
        docker_image,
        detach=True,
        ports={'5005/tcp': 5005},
        environment={
            'FLASK_SECRET': 'test-secret-for-validation',
            'TMDB_API_KEY': 'test-key-for-validation',
            'MEDIA_PROVIDER': 'plex'
        }
    )
    time.sleep(5)  # Wait for Gunicorn to start
    yield container
    container.stop()
    container.remove()

def test_docker_build_succeeds(docker_image):
    """Test that Docker build completes successfully"""
    # Build already done in fixture, just verify image exists
    client = docker.from_env()
    images = [img.tags[0] for img in client.images.list() if img.tags]
    assert "jellyswipe-test:latest" in images

def test_container_starts(running_container):
    """Test that container starts and is running"""
    running_container.reload()
    assert running_container.status == "running"

def test_port_5005_accessible():
    """Test that port 5005 is accessible"""
    try:
        response = requests.get("http://localhost:5005/", timeout=5)
        assert response.status_code in [200, 302], f"Unexpected status: {response.status_code}"
    except requests.exceptions.ConnectionError:
        pytest.fail("Port 5005 not accessible")

def test_app_data_directory_writable(running_container, tmp_path):
    """Test that /app/data directory is writable"""
    client = docker.from_env()
    data_dir = tmp_path / "test-data"
    data_dir.mkdir()

    # Run container with volume mount
    container = client.containers.run(
        "jellyswipe-test:latest",
        detach=True,
        ports={'5005/tcp': 5006},  # Different port to avoid conflict
        environment={
            'FLASK_SECRET': 'test-secret',
            'TMDB_API_KEY': 'test-key',
            'MEDIA_PROVIDER': 'plex'
        },
        volumes={str(data_dir): {'bind': '/app/data', 'mode': 'rw'}}
    )
    time.sleep(5)

    try:
        # Check if database was created
        db_path = data_dir / "jellyswipe.db"
        assert db_path.exists(), "Database file not created in /app/data"

        # Verify it's a valid SQLite database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        assert len(tables) > 0, "No tables found in database"
    finally:
        container.stop()
        container.remove()

def test_no_uv_binary_in_final_image():
    """Test that uv binary is not in final image (multi-stage optimization)"""
    result = subprocess.run(
        ["docker", "run", "--rm", "jellyswipe-test:latest", "which", "uv"],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0, "uv binary found in final image (should be in builder stage only)"

def test_gunicorn_entry_point(running_container):
    """Test that Gunicorn entry point jellyswipe:app works"""
    logs = running_container.logs().decode('utf-8')
    assert "jellyswipe:app" in logs or "Listening at" in logs, "Gunicorn entry point not working"

def test_static_files_accessible():
    """Test that static files are accessible"""
    try:
        response = requests.get("http://localhost:5005/static/manifest.json", timeout=5)
        assert response.status_code == 200, f"Static file not accessible: {response.status_code}"
        assert "application/json" in response.headers.get('Content-Type', ''), "Wrong content type for manifest.json"
    except requests.exceptions.ConnectionError:
        pytest.fail("Static files not accessible")
```

### test_readme.py (DOC-01)

```python
"""
Tests for README Development section (DOC-01)
Requires: pytest
"""

import re

def test_development_section_exists():
    """Test that README has Development section"""
    with open("README.md", "r") as f:
        content = f.read()
    assert "## Development" in content, "Development section not found in README"

def test_development_section_after_deployment():
    """Test that Development section comes after Deployment section"""
    with open("README.md", "r") as f:
        content = f.read()
    deployment_idx = content.find("## Deployment")
    development_idx = content.find("## Development")
    assert deployment_idx != -1, "Deployment section not found"
    assert development_idx != -1, "Development section not found"
    assert development_idx > deployment_idx, "Development section should come after Deployment"

def test_uv_sync_documented():
    """Test that uv sync is documented"""
    with open("README.md", "r") as f:
        content = f.read()
    assert "uv sync" in content, "uv sync not documented"

def test_uv_run_python_documented():
    """Test that uv run python -m jellyswipe is documented"""
    with open("README.md", "r") as f:
        content = f.read()
    assert "uv run python -m jellyswipe" in content, "uv run python -m jellyswipe not documented"

def test_uv_run_gunicorn_documented():
    """Test that uv run gunicorn is documented"""
    with open("README.md", "r") as f:
        content = f.read()
    assert "uv run gunicorn" in content, "uv run gunicorn not documented"

def test_uv_add_documented():
    """Test that uv add is documented"""
    with open("README.md", "r") as f:
        content = f.read()
    assert "uv add" in content, "uv add not documented"

def test_uv_lock_upgrade_documented():
    """Test that uv lock --upgrade is documented"""
    with open("README.md", "r") as f:
        content = f.read()
    assert "uv lock --upgrade" in content, "uv lock --upgrade not documented"

def test_python_3_13_mentioned():
    """Test that Python 3.13 requirement is mentioned in Development section"""
    with open("README.md", "r") as f:
        content = f.read()
    # Extract Development section
    dev_match = re.search(r'## Development.*?(?=\n## |$)', content, re.DOTALL)
    assert dev_match, "Could not extract Development section"
    dev_section = dev_match.group(0)
    assert "3.13" in dev_section, "Python 3.13 not mentioned in Development section"

def test_no_pip_install_in_development():
    """Test that no pip install commands are in Development section"""
    with open("README.md", "r") as f:
        content = f.read()
    # Extract Development section
    dev_match = re.search(r'## Development.*?(?=\n## |$)', content, re.DOTALL)
    assert dev_match, "Could not extract Development section"
    dev_section = dev_match.group(0)
    # Check for pip install (not in comments)
    pip_lines = [line for line in dev_section.split('\n') if 'pip install' in line and not line.strip().startswith('#')]
    assert len(pip_lines) == 0, f"Found pip install commands in Development section: {pip_lines}"
```

### test_distribution.py (DIST-01)

```python
"""
Tests for PyPI story avoidance (DIST-01)
Requires: pytest
"""

import os
import glob

def test_no_pypi_workflow():
    """Test that no PyPI publishing workflow exists"""
    workflow_dir = ".github/workflows"
    assert os.path.exists(workflow_dir), "Workflows directory not found"

    workflow_files = glob.glob(os.path.join(workflow_dir, "*.yml")) + glob.glob(os.path.join(workflow_dir, "*.yaml"))
    for workflow_file in workflow_files:
        with open(workflow_file, "r") as f:
            content = f.read()
        assert "pypi" not in content.lower(), f"PyPI reference found in {workflow_file}"

def test_no_pip_install_jellyswipe_in_readme():
    """Test that README does not suggest pip install jellyswipe"""
    with open("README.md", "r") as f:
        content = f.read()
    assert "pip install jellyswipe" not in content.lower(), "README suggests pip install jellyswipe"

def test_no_pypi_badges():
    """Test that no PyPI badges or links are in README"""
    with open("README.md", "r") as f:
        content = f.read()
    # Check for common PyPI badge patterns
    pypi_patterns = [
        r'pypi\.org',
        r'pypip\.in',
        r'badge\.fury\.io.*py',
        r'img\.shields\.io.*pypi',
    ]
    for pattern in pypi_patterns:
        assert not re.search(pattern, content, re.IGNORECASE), f"PyPI badge/link found matching pattern: {pattern}"

def test_requirements_txt_removed_or_deprecated():
    """Test that requirements.txt is removed or has deprecation comment"""
    requirements_path = "requirements.txt"
    if os.path.exists(requirements_path):
        with open(requirements_path, "r") as f:
            content = f.read()
        assert "deprecated" in content.lower() or "uv" in content.lower(), \
            "requirements.txt exists but lacks deprecation comment or uv reference"

def test_docker_install_paths_only():
    """Test that only Docker or source checkout install paths are documented"""
    with open("README.md", "r") as f:
        content = f.read()
    # Check Deployment section
    deploy_match = re.search(r'## Deployment.*?(?=\n## |$)', content, re.DOTALL)
    assert deploy_match, "Could not extract Deployment section"
    deploy_section = deploy_match.group(0)

    # Should mention Docker
    assert "docker" in deploy_section.lower(), "Docker not mentioned in Deployment section"

    # Should not mention pip install from PyPI
    assert "pip install" not in deploy_section or "from PyPI" not in deploy_section, \
        "Deployment section suggests pip install from PyPI"
```

## Validation Checklist

Use this checklist to manually verify all success criteria before phase completion.

### Pre-Validation Setup
- [ ] Docker daemon is running
- [ ] Current branch is clean (no uncommitted changes)
- [ ] No running containers on port 5005 (to avoid conflicts)

### DOCK-01: Docker Integration
- [ ] Docker build completes: `docker build -t jellyswipe-test:latest .`
- [ ] Container starts: `docker run -d -p 5005:5005 -e FLASK_SECRET=test -e TMDB_API_KEY=test -e MEDIA_PROVIDER=plex jellyswipe-test:latest`
- [ ] Port 5005 accessible: `curl -I http://localhost:5005/`
- [ ] /app/data writable: Test with volume mount and verify DB creation
- [ ] Static files accessible: `curl -I http://localhost:5005/static/manifest.json`
- [ ] No uv binary in final image: `docker run --rm jellyswipe-test:latest which uv` (should fail)
- [ ] Gunicorn entry point works: Check logs for "Listening at: http://0.0.0.0:5005"
- [ ] Docker Compose works: Test with docker-compose config from README
- [ ] Image size reasonable: Compare to previous build (should be smaller or similar)
- [ ] Build uses uv.lock: Check build log for "uv sync --locked"

### DOC-01: Maintainer Documentation
- [ ] README has "## Development" section
- [ ] Development section after "## Deployment"
- [ ] Documents `uv sync`
- [ ] Documents `uv run python -m jellyswipe`
- [ ] Documents `uv run gunicorn jellyswipe:app`
- [ ] Documents `uv add <package>`
- [ ] Documents `uv lock --upgrade`
- [ ] Mentions Python 3.13 requirement
- [ ] No `pip install` commands in Development section
- [ ] Deployment section unchanged

### DIST-01: PyPI Story Avoidance
- [ ] No PyPI workflow in `.github/workflows/`
- [ ] No `pip install jellyswipe` in README
- [ ] No PyPI badges or links in README
- [ ] `requirements.txt` removed or has deprecation comment
- [ ] All install paths are Docker or source checkout

### Post-Validation Cleanup
- [ ] Stop test containers: `docker stop $(docker ps -q --filter ancestor=jellyswipe-test)`
- [ ] Remove test containers: `docker rm $(docker ps -aq --filter ancestor=jellyswipe-test)`
- [ ] Remove test image: `docker rmi jellyswipe-test:latest`
- [ ] Clean up test data directories

## Validation Report Template

After completing validation, fill out this report:

```
## Phase 12 Validation Report

**Date:** [YYYY-MM-DD]
**Validator:** [Name]

### DOCK-01: Docker Integration
- Docker build: [PASS/FAIL] - Notes: [...]
- Container startup: [PASS/FAIL] - Notes: [...]
- Port 5005 accessible: [PASS/FAIL] - Notes: [...]
- /app/data writable: [PASS/FAIL] - Notes: [...]
- Static files accessible: [PASS/FAIL] - Notes: [...]
- No uv binary in final image: [PASS/FAIL] - Notes: [...]
- Gunicorn entry point: [PASS/FAIL] - Notes: [...]
- Docker Compose works: [PASS/FAIL] - Notes: [...]

### DOC-01: Maintainer Documentation
- Development section exists: [PASS/FAIL] - Notes: [...]
- uv commands documented: [PASS/FAIL] - Notes: [...]
- Python 3.13 mentioned: [PASS/FAIL] - Notes: [...]
- No pip install in Development: [PASS/FAIL] - Notes: [...]

### DIST-01: PyPI Story Avoidance
- No PyPI workflow: [PASS/FAIL] - Notes: [...]
- No pip install jellyswipe: [PASS/FAIL] - Notes: [...]
- No PyPI badges: [PASS/FAIL] - Notes: [...]
- requirements.txt handled: [PASS/FAIL] - Notes: [...]

### Overall Result
- Phase 12: [PASS/FAIL]
- Blocking issues: [List if any]
- Non-blocking issues: [List if any]
- Recommendations: [Any suggestions for future phases]
```

## Known Limitations

1. **No automated test infrastructure:** Current validation is manual. Wave 0 tasks should establish pytest with docker testing capabilities.
2. **Depends on external services:** Some tests mock Plex/Jellyfin/TMDB connections, but full integration tests would require real services.
3. **Port conflicts:** Validation assumes port 5005 is available. Conflicts require manual port changes.
4. **Image size comparison:** "Reasonable image size" is subjective. Establish baseline metrics for future comparisons.

## Next Steps for Automation

To move from manual to automated validation:

1. **Wave 0 Tasks:**
   - Install pytest and pytest-docker (or similar)
   - Create `tests/` directory structure
   - Set up `tests/conftest.py` with Docker fixtures
   - Implement `test_docker.py`, `test_readme.py`, `test_distribution.py`

2. **CI Integration:**
   - Add GitHub Action to run tests on push
   - Configure test environment variables
   - Set up Docker-in-Docker for CI testing

3. **Continuous Validation:**
   - Run tests on every PR
   - Block merges if tests fail
   - Track test coverage over time

---

**Validation document created:** 2026-04-24
**Valid until:** Phase 12 completion
