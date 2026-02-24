# app/ai/github_scanner.py
# ============================================================
# GITHUB SCANNER
#
# Scans a user's public GitHub profile and extracts technical
# skills from their repositories automatically.
#
# HOW IT WORKS
# ────────────
# 1. Parse the GitHub username from any URL format the user gives
#    e.g. "github.com/santhosh", "https://github.com/santhosh",
#         or just "santhosh"
#
# 2. Call the GitHub public API to list all repos
#    Endpoint: GET https://api.github.com/users/{username}/repos
#    No API key needed for public repos (60 requests/hour free)
#
# 3. For each repo, fetch the file tree to find:
#    - requirements.txt  (Python dependencies)
#    - package.json      (Node.js dependencies)
#    - *.ipynb           (Jupyter notebooks → Data Science signal)
#    - Dockerfile        (CI/CD signal)
#    - go.mod, Cargo.toml, pom.xml etc. (language signals)
#
# 4. For important files, fetch the actual file content and
#    scan for import statements and library names
#
# 5. Map everything found → canonical skill names using
#    GITHUB_SKILL_MAP below
#
# RATE LIMITING
# ─────────────
# GitHub allows 60 unauthenticated requests/hour per IP.
# We batch smartly: fetch repo list (1 request), then fetch
# only the most relevant files per repo (2-3 requests each).
# For a typical user with 10-20 repos, total = ~30-50 requests.
# If the user provides a GitHub token via env var, limit is 5000/hour.
#
# PRIVACY
# ───────
# We only access PUBLIC repositories. Private repos are never
# visible to the GitHub public API without a personal access token.
# ============================================================

import os
import re
import json
import logging
import urllib.request
import urllib.error
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Optional GitHub token (dramatically raises rate limit) ────
# Set in environment: export GITHUB_TOKEN="ghp_..."
# Without it: 60 requests/hour (enough for most users)
# With it:  5000 requests/hour
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# ── How many repos to scan per user ──────────────────────────
# Scanning all repos of a prolific developer would hit rate limits.
# We take the 15 most recently updated repos — these reflect
# current skills best.
MAX_REPOS = 15

# ── How many files to fetch per repo ─────────────────────────
# Each file fetch = 1 API request. Keep this small.
MAX_FILES_PER_REPO = 3


# ════════════════════════════════════════════════════════════
# SKILL MAP
# Maps library/framework/file names → canonical graph skill names
# ════════════════════════════════════════════════════════════

# Python library imports → skill
PYTHON_IMPORT_MAP: dict[str, str] = {
    # ML / AI
    "torch":              "PyTorch",
    "pytorch":            "PyTorch",
    "tensorflow":         "Deep Learning",
    "keras":              "Deep Learning",
    "sklearn":            "Machine Learning",
    "scikit_learn":       "Machine Learning",
    "scikit-learn":       "Machine Learning",
    "xgboost":            "Machine Learning",
    "lightgbm":           "Machine Learning",
    "catboost":           "Machine Learning",
    "transformers":       "NLP",
    "huggingface":        "NLP",
    "spacy":              "NLP",
    "nltk":               "NLP",
    "gensim":             "NLP",
    "cv2":                "Computer Vision",
    "opencv":             "Computer Vision",
    "PIL":                "Computer Vision",
    "pillow":             "Computer Vision",
    "gymnasium":          "Reinforcement Learning",
    "gym":                "Reinforcement Learning",
    "stable_baselines":   "Reinforcement Learning",

    # Data Science
    "numpy":              "Linear Algebra",
    "scipy":              "Statistics",
    "pandas":             "Data Science",
    "matplotlib":         "Data Science",
    "seaborn":            "Data Science",
    "plotly":             "Data Science",
    "bokeh":              "Data Science",
    "statsmodels":        "Statistics",
    "pingouin":           "Hypothesis Testing",

    # Backend
    "fastapi":            "Backend Development",
    "flask":              "Backend Development",
    "django":             "Backend Development",
    "aiohttp":            "Backend Development",
    "starlette":          "Backend Development",
    "uvicorn":            "Backend Development",
    "sqlalchemy":         "Databases",
    "psycopg2":           "Databases",
    "pymongo":            "Databases",
    "redis":              "Databases",
    "pymysql":            "Databases",
    "requests":           "File I/O and APIs",
    "httpx":              "File I/O and APIs",
    "aiohttp":            "File I/O and APIs",

    # System / DevOps
    "subprocess":         "Linux / CLI",
    "paramiko":           "Linux / CLI",
    "fabric":             "Linux / CLI",
    "celery":             "Distributed Systems",
    "kafka":              "Distributed Systems",
    "pika":               "Distributed Systems",  # RabbitMQ

    # Data Structures & Algorithms
    "collections":        "Data Structures",
    "heapq":              "Data Structures",
    "bisect":             "Algorithms",
    "functools":          "Algorithms",

    # Math
    "sympy":              "Calculus",
    "autograd":           "Calculus",
}

# requirements.txt / package.json package names → skill
PACKAGE_NAME_MAP: dict[str, str] = {
    # Python packages (requirements.txt)
    "torch":              "PyTorch",
    "torchvision":        "PyTorch",
    "torchaudio":         "PyTorch",
    "tensorflow":         "Deep Learning",
    "keras":              "Deep Learning",
    "scikit-learn":       "Machine Learning",
    "xgboost":            "Machine Learning",
    "lightgbm":           "Machine Learning",
    "transformers":       "NLP",
    "spacy":              "NLP",
    "nltk":               "NLP",
    "opencv-python":      "Computer Vision",
    "Pillow":             "Computer Vision",
    "gymnasium":          "Reinforcement Learning",
    "stable-baselines3":  "Reinforcement Learning",
    "numpy":              "Linear Algebra",
    "scipy":              "Statistics",
    "pandas":             "Data Science",
    "matplotlib":         "Data Science",
    "seaborn":            "Data Science",
    "plotly":             "Data Science",
    "statsmodels":        "Statistics",
    "fastapi":            "Backend Development",
    "flask":              "Backend Development",
    "django":             "Backend Development",
    "sqlalchemy":         "Databases",
    "psycopg2-binary":    "Databases",
    "pymongo":            "Databases",
    "redis":              "Databases",
    "celery":             "Distributed Systems",
    "kafka-python":       "Distributed Systems",
    "pytest":             "CI/CD",
    "black":              "Collaborative Development",
    "mypy":               "Collaborative Development",
    "pre-commit":         "Collaborative Development",
    "sympy":              "Calculus",
    "networkx":           "Algorithms",

    # Node.js packages (package.json)
    "express":            "Backend Development",
    "fastify":            "Backend Development",
    "next":               "Backend Development",
    "react":              "Backend Development",
    "axios":              "File I/O and APIs",
    "mongoose":           "Databases",
    "sequelize":          "Databases",
    "prisma":             "Databases",
    "jest":               "CI/CD",
    "mocha":              "CI/CD",
    "eslint":             "Collaborative Development",
    "tensorflow":         "Deep Learning",
    "brain.js":           "Machine Learning",
}

# File names / extensions → skill signals
FILE_SIGNAL_MAP: dict[str, str] = {
    "dockerfile":           "CI/CD",
    "docker-compose.yml":   "CI/CD",
    "docker-compose.yaml":  "CI/CD",
    ".github/workflows":    "CI/CD",
    "jenkinsfile":          "CI/CD",
    ".travis.yml":          "CI/CD",
    "kubernetes":           "Distributed Systems",
    "k8s":                  "Distributed Systems",
    "makefile":             "Linux / CLI",
    "*.ipynb":              "Data Science",      # Jupyter notebook
    "*.sql":                "Databases",
    "schema.sql":           "Databases",
    "migration":            "Databases",
    "*.sh":                 "Linux / CLI",
    "*.bash":               "Linux / CLI",
    "setup.py":             "Python",
    "pyproject.toml":       "Python",
    "go.mod":               "Backend Development",
    "cargo.toml":           "System Design",     # Rust → systems
    "pom.xml":              "Backend Development", # Java/Maven
    "build.gradle":         "Backend Development",
}

# Programming language detected from repo's main language → skill
LANGUAGE_MAP: dict[str, str] = {
    "Python":     "Python",
    "Jupyter Notebook": "Data Science",
    "R":          "Statistics",
    "SQL":        "Databases",
    "Shell":      "Linux / CLI",
    "Dockerfile": "CI/CD",
    "Go":         "Backend Development",
    "Rust":       "System Design",
    "Java":       "Object Oriented Programming",
    "C++":        "Algorithms",
    "C":          "Operating Systems",
    "TypeScript": "Backend Development",
    "JavaScript": "Backend Development",
}


# ════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════

def scan_github_profile(github_input: str) -> dict:
    """
    Scan a GitHub profile and return detected skills.

    Accepts any of these input formats:
        "santhosh"
        "github.com/santhosh"
        "https://github.com/santhosh"
        "https://github.com/santhosh/"

    Returns:
        dict with keys:
            username       — cleaned GitHub username
            skills         — list of canonical skill names
            repos_scanned  — number of repos analyzed
            signals        — detailed breakdown of what was found where
            error          — None on success, error message on failure

    The `signals` list is important for transparency — it shows
    exactly which repo/file triggered each skill detection.
    This makes the results explainable and auditable.
    """
    # ── Step 1: Parse username ────────────────────────────────
    username = _parse_username(github_input)
    if not username:
        return _error_result("Could not parse a GitHub username from the input.")

    logger.info(f"Scanning GitHub profile: {username}")

    # ── Step 2: Fetch repo list ───────────────────────────────
    try:
        repos = _fetch_repos(username)
    except GithubScanError as e:
        return _error_result(str(e))

    if not repos:
        return _error_result(f"No public repositories found for '{username}'.")

    # ── Step 3: Scan each repo ────────────────────────────────
    all_signals: list[dict] = []

    # Detect skills from repo metadata (language, topic tags, name)
    for repo in repos:
        signals = _scan_repo_metadata(repo)
        all_signals.extend(signals)

    # Detect skills from file contents (requirements.txt, imports, etc.)
    for repo in repos[:MAX_REPOS]:
        try:
            signals = _scan_repo_files(username, repo)
            all_signals.extend(signals)
        except GithubScanError as e:
            logger.warning(f"Could not scan {repo['name']}: {e}")
            continue

    # ── Step 4: Deduplicate and return ────────────────────────
    from app.ai.skill_extractor import KNOWN_SKILLS
    valid_skills = set(KNOWN_SKILLS)

    # Collect unique skills, preserving signal info
    seen_skills: set[str] = set()
    unique_signals: list[dict] = []
    for signal in all_signals:
        skill = signal["skill"]
        if skill in valid_skills and skill not in seen_skills:
            seen_skills.add(skill)
            unique_signals.append(signal)

    skills = sorted(seen_skills)

    return {
        "username":      username,
        "skills":        skills,
        "repos_scanned": len(repos),
        "signals":       unique_signals,
        "error":         None,
    }


# ════════════════════════════════════════════════════════════
# PARSING
# ════════════════════════════════════════════════════════════

def _parse_username(raw: str) -> str | None:
    """
    Extract a clean GitHub username from any input format.

    Examples:
        "santhosh"                        → "santhosh"
        "github.com/santhosh"             → "santhosh"
        "https://github.com/santhosh"     → "santhosh"
        "https://github.com/santhosh/"    → "santhosh"
        "github.com/santhosh/some-repo"   → "santhosh"
    """
    raw = raw.strip().strip("/")

    # If it's a URL, parse it
    if "github.com" in raw:
        # Ensure it has a scheme for urlparse
        if not raw.startswith("http"):
            raw = "https://" + raw
        parsed = urlparse(raw)
        # path is like "/santhosh" or "/santhosh/repo"
        parts = parsed.path.strip("/").split("/")
        if parts and parts[0]:
            return parts[0]
        return None

    # Otherwise treat the whole string as the username
    # Validate: GitHub usernames are alphanumeric + hyphens, max 39 chars
    if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,37}[a-zA-Z0-9])?$', raw):
        return raw

    return None


# ════════════════════════════════════════════════════════════
# GITHUB API CALLS
# ════════════════════════════════════════════════════════════

def _github_get(url: str) -> dict | list:
    """
    Make a GET request to the GitHub API.

    Uses urllib (Python stdlib) — no external HTTP library needed.
    Adds Authorization header if GITHUB_TOKEN is set.

    Raises:
        GithubScanError on any HTTP error or network failure.
    """
    headers = {
        "User-Agent":  "CareerArchitect/1.0",
        "Accept":      "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise GithubScanError(f"GitHub user or resource not found (404): {url}")
        if e.code == 403:
            raise GithubScanError(
                "GitHub API rate limit reached. Wait 1 hour or set GITHUB_TOKEN env variable."
            )
        raise GithubScanError(f"GitHub API error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise GithubScanError(f"Network error reaching GitHub: {e.reason}")
    except Exception as e:
        raise GithubScanError(f"Unexpected error: {str(e)}")


def _fetch_repos(username: str) -> list[dict]:
    """
    Fetch the user's most recently updated public repositories.

    Returns list of repo dicts from GitHub API, sorted by push date.
    Limited to MAX_REPOS to stay within rate limits.
    """
    url = (
        f"https://api.github.com/users/{username}/repos"
        f"?sort=pushed&direction=desc&per_page={MAX_REPOS}&type=owner"
    )
    data = _github_get(url)
    if not isinstance(data, list):
        raise GithubScanError("Unexpected response format from GitHub repos API.")
    return data


def _fetch_file_content(username: str, repo_name: str, file_path: str) -> str:
    """
    Fetch the raw text content of a specific file in a repo.

    Uses the GitHub Contents API which returns base64-encoded content.
    Decodes and returns as plain text string.
    """
    import base64
    url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{file_path}"
    data = _github_get(url)

    if isinstance(data, dict) and data.get("encoding") == "base64":
        raw = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return raw

    return ""


def _fetch_repo_tree(username: str, repo_name: str, default_branch: str) -> list[str]:
    """
    Fetch a flat list of all file paths in a repo.

    Uses the Git Trees API with recursive=1 to get the full tree
    in a single request (much more efficient than traversing folders).
    """
    url = (
        f"https://api.github.com/repos/{username}/{repo_name}"
        f"/git/trees/{default_branch}?recursive=1"
    )
    data = _github_get(url)
    if isinstance(data, dict) and "tree" in data:
        return [item["path"] for item in data["tree"] if item["type"] == "blob"]
    return []


# ════════════════════════════════════════════════════════════
# SCANNING LOGIC
# ════════════════════════════════════════════════════════════

def _scan_repo_metadata(repo: dict) -> list[dict]:
    """
    Extract skill signals from repo metadata without fetching file content.

    Looks at:
    - repo.language   (primary programming language GitHub detected)
    - repo.topics     (tags the owner added, e.g. "machine-learning")
    - repo.name       (sometimes descriptive: "pytorch-cnn-classifier")
    - repo.description

    This costs 0 extra API requests since metadata comes with the repo list.
    """
    signals = []
    repo_name = repo.get("name", "")
    description = (repo.get("description") or "").lower()
    language = repo.get("language") or ""
    topics = repo.get("topics") or []

    # Language signal
    if language in LANGUAGE_MAP:
        signals.append({
            "skill":  LANGUAGE_MAP[language],
            "source": f"repo/{repo_name}",
            "detail": f"Primary language: {language}",
        })

    # Topic tags signal
    TOPIC_SKILL_MAP = {
        "machine-learning":      "Machine Learning",
        "deep-learning":         "Deep Learning",
        "neural-network":        "Deep Learning",
        "pytorch":               "PyTorch",
        "tensorflow":            "Deep Learning",
        "nlp":                   "NLP",
        "natural-language-processing": "NLP",
        "computer-vision":       "Computer Vision",
        "reinforcement-learning":"Reinforcement Learning",
        "data-science":          "Data Science",
        "data-analysis":         "Data Science",
        "linear-algebra":        "Linear Algebra",
        "statistics":            "Statistics",
        "algorithms":            "Algorithms",
        "data-structures":       "Data Structures",
        "backend":               "Backend Development",
        "rest-api":              "Backend Development",
        "fastapi":               "Backend Development",
        "flask":                 "Backend Development",
        "django":                "Backend Development",
        "docker":                "CI/CD",
        "kubernetes":            "Distributed Systems",
        "git":                   "Git",
        "linux":                 "Linux / CLI",
        "database":              "Databases",
        "sql":                   "Databases",
        "system-design":         "System Design",
        "distributed-systems":   "Distributed Systems",
    }

    for topic in topics:
        if topic in TOPIC_SKILL_MAP:
            signals.append({
                "skill":  TOPIC_SKILL_MAP[topic],
                "source": f"repo/{repo_name}",
                "detail": f"Topic tag: #{topic}",
            })

    # Description + name keyword scan
    combined = f"{repo_name} {description}".lower()
    DESCRIPTION_KEYWORDS = {
        "pytorch":     "PyTorch",
        "tensorflow":  "Deep Learning",
        "transformer": "NLP",
        "bert":        "NLP",
        "gpt":         "NLP",
        "cnn":         "Computer Vision",
        "lstm":        "Deep Learning",
        "reinforcement": "Reinforcement Learning",
        "classifier":  "Machine Learning",
        "neural":      "Deep Learning",
        "pandas":      "Data Science",
        "jupyter":     "Data Science",
        "fastapi":     "Backend Development",
        "flask":       "Backend Development",
        "docker":      "CI/CD",
        "kubernetes":  "Distributed Systems",
        "sql":         "Databases",
        "linux":       "Linux / CLI",
        "bash":        "Linux / CLI",
        "algorithm":   "Algorithms",
        "data structure": "Data Structures",
        "leetcode":    "Algorithms",
        "competitive": "Algorithms",
        "research":    "Research Methods",
    }
    for kw, skill in DESCRIPTION_KEYWORDS.items():
        if kw in combined:
            signals.append({
                "skill":  skill,
                "source": f"repo/{repo_name}",
                "detail": f"Found '{kw}' in repo name/description",
            })

    return signals


def _scan_repo_files(username: str, repo: dict) -> list[dict]:
    """
    Scan files inside a repo for skill signals.

    Strategy (in order of signal quality):
    1. requirements.txt → highest quality (exact package names)
    2. package.json     → Node.js dependencies
    3. Python source files (*.py) → import statement scan
    4. File tree        → detect presence of Dockerfiles, notebooks, etc.

    We cap at MAX_FILES_PER_REPO fetches to stay within rate limits.
    """
    signals = []
    repo_name = repo.get("name", "")
    default_branch = repo.get("default_branch", "main")
    files_fetched = 0

    # ── Try requirements.txt ──────────────────────────────────
    if files_fetched < MAX_FILES_PER_REPO:
        try:
            content = _fetch_file_content(username, repo_name, "requirements.txt")
            if content:
                signals.extend(_parse_requirements_txt(content, repo_name))
                files_fetched += 1
        except GithubScanError:
            pass  # File doesn't exist in this repo

    # ── Try package.json ──────────────────────────────────────
    if files_fetched < MAX_FILES_PER_REPO:
        try:
            content = _fetch_file_content(username, repo_name, "package.json")
            if content:
                signals.extend(_parse_package_json(content, repo_name))
                files_fetched += 1
        except GithubScanError:
            pass

    # ── Scan file tree for structural signals ─────────────────
    if files_fetched < MAX_FILES_PER_REPO:
        try:
            file_paths = _fetch_repo_tree(username, repo_name, default_branch)
            signals.extend(_scan_file_tree(file_paths, repo_name))
            files_fetched += 1
        except GithubScanError:
            pass

    return signals


def _parse_requirements_txt(content: str, repo_name: str) -> list[dict]:
    """
    Parse a requirements.txt file and map packages to skills.

    Handles common formats:
        torch==2.0.0
        torch>=1.9
        torch
        # comment lines (skipped)
        -r other-requirements.txt (skipped)
    """
    signals = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip version specifiers: torch==2.0 → torch
        package = re.split(r"[>=<!;\[]", line)[0].strip().lower()
        # Check both the raw name and a normalized version
        for key, skill in PACKAGE_NAME_MAP.items():
            if package == key.lower() or package.startswith(key.lower()):
                signals.append({
                    "skill":  skill,
                    "source": f"repo/{repo_name}/requirements.txt",
                    "detail": f"Package: {line.strip()}",
                })
                break
    return signals


def _parse_package_json(content: str, repo_name: str) -> list[dict]:
    """
    Parse a package.json file and map Node.js packages to skills.
    Looks in both 'dependencies' and 'devDependencies'.
    """
    signals = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return signals

    all_deps = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("devDependencies", {}))

    for package in all_deps:
        pkg_lower = package.lower()
        for key, skill in PACKAGE_NAME_MAP.items():
            if pkg_lower == key.lower():
                signals.append({
                    "skill":  skill,
                    "source": f"repo/{repo_name}/package.json",
                    "detail": f"Package: {package}",
                })
                break
    return signals


def _scan_file_tree(file_paths: list[str], repo_name: str) -> list[dict]:
    """
    Scan a list of file paths for structural skill signals.

    Examples:
    - Presence of Dockerfile → CI/CD
    - Presence of *.ipynb   → Data Science (Jupyter notebook user)
    - Presence of *.sql     → Databases
    - Presence of *.sh      → Linux / CLI
    - .github/workflows/    → CI/CD (GitHub Actions)
    """
    signals = []
    paths_lower = [p.lower() for p in file_paths]

    FILE_SIGNALS = [
        ("dockerfile",          "CI/CD",              "Dockerfile found"),
        ("docker-compose",      "CI/CD",              "docker-compose.yml found"),
        (".github/workflows",   "CI/CD",              "GitHub Actions workflow found"),
        (".travis.yml",         "CI/CD",              ".travis.yml found"),
        ("jenkinsfile",         "CI/CD",              "Jenkinsfile found"),
        (".ipynb",              "Data Science",       "Jupyter notebook found"),
        (".sql",                "Databases",          "SQL file found"),
        ("schema",              "Databases",          "Database schema file found"),
        ("migration",           "Databases",          "Database migration found"),
        (".sh",                 "Linux / CLI",        "Shell script found"),
        ("kubernetes",          "Distributed Systems","Kubernetes config found"),
        ("/k8s/",               "Distributed Systems","k8s directory found"),
        ("helm",                "Distributed Systems","Helm chart found"),
        ("terraform",           "Distributed Systems","Terraform config found"),
        ("makefile",            "Linux / CLI",        "Makefile found"),
        ("research",            "Research Methods",   "Research directory/file found"),
        ("paper",               "Research Methods",   "Paper file found"),
    ]

    seen_skills: set[str] = set()
    for path_lower in paths_lower:
        for pattern, skill, detail in FILE_SIGNALS:
            if skill not in seen_skills and pattern in path_lower:
                seen_skills.add(skill)
                signals.append({
                    "skill":  skill,
                    "source": f"repo/{repo_name}",
                    "detail": detail,
                })

    return signals


# ════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════

def _error_result(message: str) -> dict:
    """Return a standardised error response."""
    return {
        "username":      None,
        "skills":        [],
        "repos_scanned": 0,
        "signals":       [],
        "error":         message,
    }


class GithubScanError(Exception):
    """Raised when GitHub API calls fail for any reason."""
    pass
