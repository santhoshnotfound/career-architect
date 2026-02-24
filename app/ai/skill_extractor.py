# app/ai/skill_extractor.py
# ============================================================
# AI-powered skill extraction from free-form text.
#
# This module bridges unstructured human text (resumes, project
# descriptions, GitHub READMEs) and the structured node names
# in our knowledge graph.
#
# Architecture decision:
#   We use an LLM for extraction because keyword matching fails
#   on paraphrases: "studied stochastic processes" should map
#   to "Probability", which regex cannot do reliably.
#
# The prompt is engineered to:
#   1. Extract only TECHNICAL skills (ignore "teamwork", etc.)
#   2. Normalize to Title Case to match graph node names
#   3. Map synonyms to canonical names ("PyTorch" not "torch")
#   4. Return structured JSON so we never need to parse prose
#
# Fallback strategy:
#   If the LLM API is unavailable or the key is missing,
#   the module falls back to a deterministic keyword matcher.
#   This means the app still works for demos without an API key.
# ============================================================

import os
import json
import re
import logging

import httpx  # Lightweight HTTP client; avoids heavyweight openai SDK

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────
# Read from environment variables so no secrets live in code.
# Set these before running the server:
#   export OPENAI_API_KEY="sk-..."
#   export OPENAI_BASE_URL="https://api.openai.com/v1"  # or any compatible URL
#   export OPENAI_MODEL="gpt-4o-mini"

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",    "gpt-4o-mini")

# ── Canonical skill list (graph node names) ───────────────────
# The LLM is instructed to match its output against this list.
# This prevents hallucinated skill names like "TensorFlow 2.0"
# that don't exist as graph nodes.
KNOWN_SKILLS = [
    "Python", "Data Structures", "Algorithms", "Object Oriented Programming",
    "File I/O and APIs", "Problem Solving", "Design Patterns",
    "Calculus", "Linear Algebra", "Probability", "Statistics",
    "Hypothesis Testing", "Research Methods", "Data Science",
    "Machine Learning", "Deep Learning", "Computer Vision", "NLP",
    "Reinforcement Learning", "PyTorch",
    "Git", "Collaborative Development", "CI/CD",
    "Linux / CLI", "Scripting", "Operating Systems",
    "Networking Basics", "Databases", "Backend Development",
    "System Design", "APIs and Microservices", "Distributed Systems",
]

# ── System prompt (the "brain" of extraction) ────────────────
# This is the most important piece of engineering in this module.
# Be explicit, structured, and give concrete examples.
SYSTEM_PROMPT = f"""You are a technical skill extractor for a computer science career tool.

Your ONLY job is to read text and extract technical skills from it.

Rules:
1. Extract ONLY technical, hard skills. Ignore all soft skills ("communication", "teamwork", "leadership").
2. Normalize to Title Case (e.g., "pytorch" → "PyTorch", "linear algebra" → "Linear Algebra").
3. Map synonyms to canonical names:
   - "torch", "pytorch", "PyTorch framework" → "PyTorch"
   - "ML", "machine learning" → "Machine Learning"
   - "DL", "deep learning" → "Deep Learning"
   - "NLP", "natural language processing" → "NLP"
   - "CV", "computer vision" → "Computer Vision"
   - "RL", "reinforcement learning" → "Reinforcement Learning"
   - "linear algebra", "matrices" → "Linear Algebra"
   - "probability", "stochastic", "probabilistic" → "Probability"
   - "stats", "statistics" → "Statistics"
   - "git", "github", "version control" → "Git"
   - "sql", "mysql", "postgresql", "database" → "Databases"
   - "docker", "kubernetes", "k8s" → map to "CI/CD" if deployment context
   - "bash", "shell", "terminal", "command line" → "Linux / CLI"
   - "OOP", "object oriented" → "Object Oriented Programming"
   - "REST", "APIs", "FastAPI", "Flask", "Django" → "Backend Development"
4. Only return skills from this list (exact spelling matters):
{json.dumps(KNOWN_SKILLS, indent=2)}
5. Return ONLY a valid JSON object in this exact format, no prose:
{{"skills": ["Skill One", "Skill Two"]}}
6. If no technical skills are found, return: {{"skills": []}}"""


# ── Main extraction function ──────────────────────────────────

def extract_skills_from_text(text: str) -> list[str]:
    """
    Extracts technical skills from free-form text using an LLM.

    If the OPENAI_API_KEY environment variable is set, this
    function calls the LLM API. Otherwise, it falls back to
    a deterministic keyword matcher (useful for demos).

    Args:
        text: Any free-form text. Resume, project description,
              GitHub README, cover letter, etc.

    Returns:
        A deduplicated list of canonical skill names that match
        nodes in the knowledge graph.

    Example:
        Input:  "Built a CNN with PyTorch, know linear algebra"
        Output: ["PyTorch", "Linear Algebra", "Deep Learning"]
    """
    if not text or not text.strip():
        return []

    if OPENAI_API_KEY:
        logger.info("Using LLM for skill extraction")
        return _extract_with_llm(text)
    else:
        logger.info("No API key found — using keyword fallback extractor")
        return _extract_with_keywords(text)


def _extract_with_llm(text: str) -> list[str]:
    """
    Calls the OpenAI-compatible API to extract skills.

    Uses httpx directly instead of the openai SDK to keep
    dependencies minimal and make the HTTP call visible/debuggable.

    The response is expected to be a JSON object:
        {"skills": ["Python", "PyTorch", ...]}
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0,           # Deterministic output — we want facts, not creativity
        "max_tokens": 300,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Extract skills from this text:\n\n{text}"},
        ],
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()

        # Parse the JSON response from the LLM
        parsed = json.loads(content)
        raw_skills = parsed.get("skills", [])

        # Final safety filter: only return skills that actually exist in the graph
        # This prevents hallucinated skill names from breaking gap analysis
        valid = {s.lower(): s for s in KNOWN_SKILLS}
        return [valid[s.lower()] for s in raw_skills if s.lower() in valid]

    except httpx.HTTPError as e:
        logger.error(f"LLM API HTTP error: {e}")
        return _extract_with_keywords(text)   # Fall back gracefully
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"LLM response parse error: {e}")
        return _extract_with_keywords(text)   # Fall back gracefully


def _extract_with_keywords(text: str) -> list[str]:
    """
    Deterministic skill extractor using multi-strategy keyword matching.

    This is the primary extraction method when no LLM API key is set.
    It uses four complementary strategies so that no matter how a student
    phrases their experience, the right skill gets detected.

    STRATEGY 1 — Exact keyword phrases
        Simple substring match on the lowercased text.
        Handles: "pytorch", "linear algebra", "github actions"

    STRATEGY 2 — Synonym / alias expansion
        Many skills have multiple common names.
        Handles: "torch" → PyTorch, "sklearn" → Machine Learning,
                 "backprop" → Deep Learning, "BERT" → NLP

    STRATEGY 3 — Concept phrases
        Longer phrasings students use to describe knowledge.
        Handles: "I studied random variables" → Probability,
                 "built feedforward networks" → Deep Learning,
                 "ran A/B tests" → Hypothesis Testing

    STRATEGY 4 — Library / tool names
        Specific libraries that imply a skill even when the skill
        name itself isn't mentioned.
        Handles: "used matplotlib" → Data Science,
                 "implemented ResNet" → Deep Learning,
                 "XGBoost model" → Machine Learning

    WHY NOT JUST USE REGEX?
        Simple regex misses context. "class" appears in "world-class"
        and "classification" but should only trigger OOP if clearly
        in a programming context. We use whole-word boundary checks
        on short keywords (< 5 chars) to avoid false positives.

    Args:
        text: Raw resume or project description text.

    Returns:
        Deduplicated list of canonical skill names from KNOWN_SKILLS.
    """
    t = text.lower()

    # ── Helper: safe whole-word check for short/ambiguous terms ──
    # For short keywords like "ml", "rl", "dl" we require word
    # boundaries to avoid matching "html", "url", "null" etc.
    def word_match(keyword: str) -> bool:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', t))

    def any_in(phrases: list[str]) -> bool:
        return any(p in t for p in phrases)

    def any_word(words: list[str]) -> bool:
        return any(word_match(w) for w in words)

    # ── Skill detection rules ─────────────────────────────────────
    # Each entry: (canonical_skill_name, detection_function)
    # Detection function returns True if the skill is present.
    #
    # Rules are ordered from most specific to least specific
    # to make the logic easy to audit and extend.

    RULES: list[tuple[str, any]] = [

        # ── PROGRAMMING FUNDAMENTALS ─────────────────────────────

        ("Python", lambda: any_in([
            "python", "django", "flask", "fastapi", "pip install",
            ".py", "pip ", "python3", "python2", "pycharm",
            "jupyter", "ipython", "anaconda", "conda env",
        ]) or any_word(["py"])),

        ("Object Oriented Programming", lambda: any_in([
            "object oriented", "object-oriented", "oop", "oops",
            "inheritance", "polymorphism", "encapsulation", "abstraction",
            "class and object", "classes and objects", "solid principle",
            "design class", "designed classes",
        ]) or (any_in(["class"]) and any_in(["inherit", "override", "extend", "interface", "abstract"]))),

        ("Design Patterns", lambda: any_in([
            "design pattern", "singleton", "factory pattern", "observer pattern",
            "decorator pattern", "strategy pattern", "mvc", "mvvm",
            "dependency injection", "facade", "adapter pattern",
            "solid principle",
        ])),

        ("File I/O and APIs", lambda: any_in([
            "file i/o", "file io", "read file", "write file", "csv file",
            "json file", "rest api", "api call", "http request",
            "requests library", "httpx", "urllib", "fetch data",
            "parse json", "xml parsing",
        ])),


        # ── MATHEMATICS ──────────────────────────────────────────

        ("Calculus", lambda: any_in([
            "calculus", "derivative", "partial derivative", "chain rule",
            "gradient descent", "backpropagation", "backprop",
            "differentiation", "integration", "taylor series",
            "optimization method", "gradient-based", "lagrangian",
            "convex optim",
        ])),

        ("Linear Algebra", lambda: any_in([
            "linear algebra", "matrix", "matrices", "vector space",
            "eigenvector", "eigenvalue", "singular value", "svd",
            "dot product", "cross product", "tensor", "determinant",
            "matrix multiplication", "orthogonal", "projection",
            "basis vector", "span", "rank of matrix",
        ])),

        ("Probability", lambda: any_in([
            "probability", "probabilistic", "stochastic", "bayesian",
            "random variable", "random process", "markov chain",
            "markov model", "conditional probability", "bayes theorem",
            "prior", "posterior", "likelihood", "expectation",
            "variance", "distribution", "poisson", "gaussian",
            "bernoulli", "monte carlo", "sampling method",
        ])),

        ("Statistics", lambda: any_in([
            "statistics", "statistical", "regression", "linear regression",
            "logistic regression", "correlation", "covariance",
            "standard deviation", "mean and median", "mean, median",
            "normal distribution", "bell curve",
            "t-test", "chi-square", "anova", "confidence interval",
            "statistical analysis", "data modelling", "inferential",
            "descriptive statistics", "outlier detection",
            "variance analysis", "probability distribution",
        ])),

        ("Hypothesis Testing", lambda: any_in([
            "hypothesis testing", "hypothesis test", "p-value", "p value",
            "null hypothesis", "t-test", "chi-square test", "anova",
            "significance test", "statistical significance",
            "a/b test", "ab test", "split test", "z-test",
            "one-sample", "two-sample", "paired test",
        ])),

        ("Research Methods", lambda: any_in([
            "research method", "literature review", "arxiv", "arxiv",
            "research paper", "academic paper", "published paper",
            "ablation study", "ablation test", "ablation",
            "experiment design", "conducted experiment",
            "scientific method", "peer review", "citation",
            "survey paper", "benchmark", "sota", "state of the art",
            "research project", "thesis", "dissertation",
            "read papers", "reading papers", "ml paper",
        ])),

        ("Problem Solving", lambda: any_in([
            "problem solving", "problem-solving", "algorithmic thinking",
            "analytical thinking", "logical thinking", "critical thinking",
            "competitive programming", "hackathon", "coding contest",
            "leetcode", "codeforces", "hackerrank", "codechef",
            "algorithmic challenge", "complex challenge",
            "debugging", "root cause analysis",
        ])),

        ("Distributed Systems", lambda: any_in([
            "distributed system", "distributed computing",
            "message queue", "apache kafka", "rabbitmq",
            "event-driven architecture", "event driven",
            "redis cluster", "redis caching", "used redis",
            "eventual consistency", "consensus algorithm",
            "raft consensus", "paxos", "zookeeper",
            "distributed database", "replication", "sharding",
            "service discovery", "kubernetes cluster",
        ])),

        ("System Design", lambda: any_in([
            "system design", "scalability", "scalable system",
            "scalable architecture", "scalable backend",
            "load balancer", "load balancing", "caching strategy",
            "cdn", "database replication",
            "cap theorem", "consistency", "availability",
            "partition tolerance", "rate limiting", "api rate",
            "horizontal scaling", "vertical scaling",
            "high availability", "fault tolerance", "design interview",
        ])),

        ("Networking Basics", lambda: any_in([
            "tcp/ip", "tcp ip", "udp protocol",
            "http request", "https request", "http protocol", "https protocol",
            "http method", "get request", "post request",
            "dns server", "dhcp", "socket programming", "websocket",
            "ip address", "subnet mask", "routing protocol",
            "firewall configuration", "load balancing",
            "rest vs graphql", "graphql", "grpc", "network protocol",
            "network security", "ssl certificate", "tls handshake", "vpn",
            "network topology", "osi model", "computer network",
            "networking course", "network layer", "ip routing",
            "computer networking", "studied networking",
        ])),

        # ── MACHINE LEARNING & AI ─────────────────────────────────

        ("Machine Learning", lambda: any_in([
            "machine learning", "scikit", "sklearn", "supervised learning",
            "unsupervised learning", "semi-supervised",
            "classifier", "classifiers", "classification model",
            "regressor", "regressors", "regression model",
            "clustering", "xgboost", "lightgbm",
            "catboost", "random forest", "decision tree", "svm",
            "support vector", "knn", "k-nearest", "feature engineering",
            "feature selection", "hyperparameter", "cross-validation",
            "train test split", "overfitting", "underfitting",
            "bias-variance", "model evaluation", "model selection",
            "gradient boosting", "ensemble method", "bagging", "boosting",
            "dimensionality reduction", "pca", "t-sne",
        ]) or any_word(["ml"])),

        ("Deep Learning", lambda: any_in([
            "deep learning", "neural network", "feedforward", "backpropagation",
            "backprop", "cnn", "rnn", "lstm", "gru", "attention mechanism",
            "self-attention", "transformer model", "resnet", "vgg",
            "inception", "mobilenet", "efficientnet", "gan",
            "generative adversarial", "variational autoencoder", "vae",
            "diffusion model", "bert", "gpt", "llm", "large language",
            "encoder-decoder", "seq2seq", "embedding layer",
            "batch normalization", "dropout layer", "activation function",
            "relu", "sigmoid activation", "weight initialization",
            "epoch", "training loop", "fine-tuning", "pretrained model",
            "transfer learning",
        ]) or any_word(["dl"])),

        ("NLP", lambda: any_in([
            "nlp", "natural language", "text classification", "sentiment",
            "text summarization", "machine translation", "chatbot",
            "question answering", "named entity", "ner", "pos tagging",
            "word embedding", "word2vec", "glove embedding", "fasttext",
            "tokenization", "tokenizer", "bert", "gpt", "roberta",
            "language model", "text generation", "speech recognition",
            "information extraction", "coreference", "dependency parsing",
            "hugging face", "huggingface", "transformers library",
        ])),

        ("Computer Vision", lambda: any_in([
            "computer vision", "image recognition", "image classification",
            "object detection", "image segmentation", "semantic segmentation",
            "instance segmentation", "opencv", "cv2", "pillow", "pil",
            "convolutional network", "image dataset", "yolo", "rcnn",
            "imagenet", "cifar", "image augmentation", "bounding box",
            "facial recognition", "pose estimation", "optical flow",
            "image processing", "video analysis",
        ])),

        ("Reinforcement Learning", lambda: any_in([
            "reinforcement learning", "q-learning", "q learning",
            "policy gradient", "dqn", "deep q", "ppo", "a3c", "actor-critic",
            "reward function", "exploration vs exploitation", "markov decision",
            "mdp", "gymnasium", "openai gym", "environment simulation",
            "agent training", "monte carlo tree",
        ]) or any_word(["rl"])),

        ("PyTorch", lambda: any_in([
            "pytorch", "torch", "torchvision", "torchaudio",
            "torch.nn", "dataloader", "tensor operations",
        ])),

        ("Data Science", lambda: any_in([
            "data science", "data analysis", "exploratory data",
            "eda", "pandas", "numpy", "matplotlib", "seaborn",
            "plotly", "bokeh", "data visualization", "visualization",
            "visualisation", "data cleaning", "data wrangling",
            "data pipeline", "feature extraction",
            "statistical analysis", "jupyter notebook", "jupyter lab",
            "data exploration", "data insight", "dashboard",
            "tableau", "power bi", "data storytelling",
            "created charts", "plotted graphs",
        ])),

        # ── SOFTWARE ENGINEERING ──────────────────────────────────

        ("Data Structures", lambda: any_in([
            "data structure", "linked list", "doubly linked", "hash map",
            "hash table", "binary tree", "binary search tree", "bst",
            "heap", "priority queue", "stack", "queue", "deque",
            "trie", "graph traversal", "adjacency", "red-black tree",
            "avl tree", "segment tree", "disjoint set", "union find",
            "arrays and strings",
        ])),

        ("Algorithms", lambda: any_in([
            "algorithm", "sorting", "binary search", "searching",
            "dynamic programming", "dp problem", "memoization",
            "greedy algorithm", "divide and conquer", "recursion",
            "backtracking", "graph algorithm", "bfs", "dfs",
            "dijkstra", "bellman ford", "floyd warshall", "kruskal",
            "prim", "topological sort", "time complexity", "space complexity",
            "big o", "big-o", "asymptotic", "leetcode", "codeforces",
            "competitive programming", "two pointer", "sliding window",
        ])),

        ("Git", lambda: any_in([
            "git", "github", "gitlab", "bitbucket", "version control",
            "commit", "pull request", "merge request", "branching",
            "git merge", "git rebase", "git clone", "repository",
            "source control",
        ])),

        ("Collaborative Development", lambda: any_in([
            "collaborative development", "code review", "pair programming",
            "team project", "open source contribution", "pull request",
            "agile", "scrum", "sprint", "kanban", "jira",
            "documentation", "technical writing", "api documentation",
        ])),

        ("CI/CD", lambda: any_in([
            "ci/cd", "cicd", "continuous integration", "continuous deployment",
            "continuous delivery", "docker", "dockerfile", "containerization",
            "kubernetes", "k8s", "helm chart", "jenkins", "travis ci",
            "github actions", "gitlab ci", "circleci", "devops",
            "deployment pipeline", "automated testing", "unit testing",
            "integration testing", "pytest", "jest", "mocha",
        ])),

        ("Linux / CLI", lambda: any_in([
            "linux", "unix", "bash", "shell script", "terminal",
            "command line", "command-line", "ssh", "vim", "nano",
            "file system", "chmod", "grep", "awk", "sed", "curl",
            "wget", "cron job", "systemd", "ubuntu", "debian",
            "centos", "wsl", "powershell scripting",
        ])),

        ("Scripting", lambda: any_in([
            "scripting", "automation script", "bash script", "shell script",
            "python script", "task automation", "cron", "scheduled job",
            "batch processing", "file automation", "web scraping",
            "scraper", "beautifulsoup", "selenium automation",
        ])),

        ("Operating Systems", lambda: any_in([
            "operating system", "os concepts", "process management",
            "thread", "multithreading", "concurrency", "deadlock",
            "memory management", "virtual memory", "paging", "segmentation",
            "cpu scheduling", "file system", "ipc",
            "inter-process communication", "kernel",
        ])),

        ("Databases", lambda: any_in([
            "database", "sql", "mysql", "postgresql", "postgres",
            "sqlite", "mongodb", "nosql", "redis", "cassandra",
            "dynamodb", "firebase", "supabase", "orm",
            "sqlalchemy", "prisma", "sequelize", "query optimization",
            "indexing", "database schema", "normalization",
            "stored procedure", "database design",
        ])),

        ("Backend Development", lambda: any_in([
            "backend", "back-end", "back end", "server-side",
            "fastapi", "flask", "django", "express", "node.js",
            "nodejs", "spring boot", "web server", "rest api",
            "restful", "api development", "api endpoint",
            "developed api", "developed apis", "built api", "built apis",
            "middleware", "authentication", "authorization",
            "jwt", "oauth", "web framework", "server development",
        ])),

        ("APIs and Microservices", lambda: any_in([
            "microservice", "micro-service", "service mesh",
            "api gateway", "event-driven",
            "rabbitmq", "apache kafka", "grpc", "graphql api",
            "service oriented", "api design", "openapi",
            "swagger", "api versioning",
        ])),

    ]

    # ── Run all rules and collect matching skills ─────────────────
    # Deduplicate: a skill can only appear once even if multiple
    # rules match (e.g. both "pytorch" and "torch" match PyTorch).
    found: list[str] = []
    seen: set[str] = set()
    for skill_name, detect_fn in RULES:
        if skill_name in seen:
            continue  # Skip duplicate rule entries
        try:
            if detect_fn():
                found.append(skill_name)
                seen.add(skill_name)
        except Exception:
            # Never let a bad regex or rule crash extraction
            continue

    return found
