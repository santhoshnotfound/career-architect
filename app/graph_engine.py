# graph_engine.py
# ============================================================
# The core reasoning engine for Career Architect.
#
# EXPANSION v2 — 32 → 83 skills, 4 → 7 roles
# New domains: Web Development, MLOps/DevOps, Data Engineering
# ============================================================

import networkx as nx


def load_default_graph() -> nx.DiGraph:
    G = nx.DiGraph()

    # ── Domain 1: Programming Fundamentals ───────────────────
    G.add_edges_from([
        ("Python",                      "Data Structures"),
        ("Python",                      "Object Oriented Programming"),
        ("Python",                      "File I/O and APIs"),
        ("Python",                      "Scripting"),
        ("Python",                      "Testing and TDD"),
        ("Data Structures",             "Algorithms"),
        ("Algorithms",                  "Problem Solving"),
        ("Object Oriented Programming", "Design Patterns"),
        ("Object Oriented Programming", "Testing and TDD"),
        ("Object Oriented Programming", "Type Systems"),
        ("Design Patterns",             "System Design"),
        ("Type Systems",                "Design Patterns"),
        ("Operating Systems",           "Concurrency"),
        ("Concurrency",                 "Distributed Systems"),
        ("Testing and TDD",             "CI/CD"),
    ])

    # ── Domain 2: Mathematics ─────────────────────────────────
    G.add_edges_from([
        ("Calculus",            "Linear Algebra"),
        ("Calculus",            "Probability"),
        ("Calculus",            "Optimisation"),
        ("Linear Algebra",      "Machine Learning"),
        ("Linear Algebra",      "Optimisation"),
        ("Probability",         "Machine Learning"),
        ("Probability",         "Statistics"),
        ("Probability",         "Information Theory"),
        ("Statistics",          "Data Science"),
        ("Statistics",          "Hypothesis Testing"),
        ("Statistics",          "Time Series Analysis"),
        ("Hypothesis Testing",  "Research Methods"),
        ("Optimisation",        "Machine Learning"),
        ("Optimisation",        "Deep Learning"),
        ("Discrete Mathematics","Algorithms"),
        ("Discrete Mathematics","Cryptography"),
        ("Cryptography",        "Network Security"),
        ("Information Theory",  "NLP"),
        ("Information Theory",  "Data Compression"),
    ])

    # ── Domain 3: Machine Learning & AI ───────────────────────
    G.add_edges_from([
        ("Machine Learning",    "Deep Learning"),
        ("Machine Learning",    "Computer Vision"),
        ("Machine Learning",    "NLP"),
        ("Machine Learning",    "Reinforcement Learning"),
        ("Machine Learning",    "MLOps"),
        ("Machine Learning",    "Experiment Tracking"),
        ("Machine Learning",    "Time Series Analysis"),
        ("Deep Learning",       "PyTorch"),
        ("Deep Learning",       "Computer Vision"),
        ("Deep Learning",       "NLP"),
        ("Deep Learning",       "Large Language Models"),
        ("Deep Learning",       "MLOps"),
        ("PyTorch",             "Research Methods"),
        ("NLP",                 "Large Language Models"),
        ("Large Language Models","Prompt Engineering"),
        ("Large Language Models","RAG Systems"),
        ("RAG Systems",         "Vector Databases"),
        ("Vector Databases",    "MLOps"),
        ("MLOps",               "Model Serving"),
        ("Model Serving",       "ML System Design"),
        ("Experiment Tracking", "MLOps"),
        ("Feature Engineering", "ML System Design"),
        ("Data Science",        "Machine Learning"),
        ("Data Science",        "Feature Engineering"),
        ("Research Methods",    "Large Language Models"),
        ("CI/CD",               "MLOps"),
    ])

    # ── Domain 4: Software Engineering & DevOps ───────────────
    G.add_edges_from([
        ("Git",                 "Collaborative Development"),
        ("Git",                 "CI/CD"),
        ("Linux / CLI",         "Scripting"),
        ("Linux / CLI",         "Operating Systems"),
        ("Linux / CLI",         "Docker"),
        ("Operating Systems",   "Distributed Systems"),
        ("Networking Basics",   "Distributed Systems"),
        ("Networking Basics",   "Backend Development"),
        ("Networking Basics",   "Cloud Platforms"),
        ("Networking Basics",   "Network Security"),
        ("Databases",           "Backend Development"),
        ("Algorithms",          "Databases"),
        ("Problem Solving",     "Research Methods"),
        ("File I/O and APIs",   "Backend Development"),
        ("Scripting",           "CI/CD"),
        ("Scripting",           "Infrastructure as Code"),
        ("Backend Development", "System Design"),
        ("Backend Development", "APIs and Microservices"),
        ("Backend Development", "Observability"),
        ("Backend Development", "ML System Design"),
        ("System Design",       "Distributed Systems"),
        ("Docker",              "Kubernetes"),
        ("Docker",              "CI/CD"),
        ("Kubernetes",          "Cloud Platforms"),
        ("Kubernetes",          "Distributed Systems"),
        ("Cloud Platforms",     "MLOps"),
        ("Cloud Platforms",     "Data Engineering"),
        ("Cloud Platforms",     "Infrastructure as Code"),
        ("Infrastructure as Code","CI/CD"),
        ("Network Security",    "System Design"),
        ("Distributed Systems", "Observability"),
    ])

    # ── Domain 5: Web Development ─────────────────────────────
    G.add_edges_from([
        ("HTML and CSS",        "JavaScript"),
        ("HTML and CSS",        "Responsive Design"),
        ("JavaScript",          "TypeScript"),
        ("JavaScript",          "React"),
        ("JavaScript",          "Node.js"),
        ("JavaScript",          "Testing and TDD"),
        ("JavaScript",          "Web Performance"),
        ("TypeScript",          "React"),
        ("TypeScript",          "Node.js"),
        ("Responsive Design",   "React"),
        ("React",               "Next.js"),
        ("React",               "State Management"),
        ("React",               "Web Performance"),
        ("Node.js",             "Backend Development"),
        ("Python",              "Backend Development"),
    ])

    # ── Domain 6: Data Engineering ────────────────────────────
    G.add_edges_from([
        ("Databases",           "SQL Advanced"),
        ("SQL Advanced",        "Data Warehousing"),
        ("Data Warehousing",    "dbt"),
        ("dbt",                 "Data Engineering"),
        ("Python",              "Apache Spark"),
        ("Databases",           "Apache Spark"),
        ("Apache Spark",        "Data Engineering"),
        ("Distributed Systems", "Apache Kafka"),
        ("Apache Kafka",        "Data Engineering"),
        ("Apache Kafka",        "Real-time Processing"),
        ("Python",              "Workflow Orchestration"),
        ("Data Engineering",    "Workflow Orchestration"),
        ("Data Engineering",    "Data Quality"),
        ("Data Warehousing",    "Data Quality"),
        ("Cloud Platforms",     "Data Engineering"),
        ("Data Science",        "Data Engineering"),
    ])

    return G


# ── Skill domain classification (83 skills) ──────────────────
SKILL_DOMAINS: dict[str, str] = {
    # Programming
    "Python":                       "programming",
    "Data Structures":              "programming",
    "Algorithms":                   "programming",
    "Object Oriented Programming":  "programming",
    "File I/O and APIs":            "programming",
    "Problem Solving":              "programming",
    "Design Patterns":              "programming",
    "Testing and TDD":              "programming",
    "Type Systems":                 "programming",
    "Concurrency":                  "programming",
    "Scripting":                    "programming",
    # Math
    "Calculus":                     "math",
    "Linear Algebra":               "math",
    "Probability":                  "math",
    "Statistics":                   "math",
    "Hypothesis Testing":           "math",
    "Research Methods":             "math",
    "Data Science":                 "math",
    "Discrete Mathematics":         "math",
    "Optimisation":                 "math",
    "Information Theory":           "math",
    "Data Compression":             "math",
    "Time Series Analysis":         "math",
    "Feature Engineering":          "math",
    # ML / AI
    "Machine Learning":             "ml",
    "Deep Learning":                "ml",
    "Computer Vision":              "ml",
    "NLP":                          "ml",
    "Reinforcement Learning":       "ml",
    "PyTorch":                      "ml",
    "Large Language Models":        "ml",
    "Prompt Engineering":           "ml",
    "RAG Systems":                  "ml",
    "Vector Databases":             "ml",
    "MLOps":                        "ml",
    "Model Serving":                "ml",
    "ML System Design":             "ml",
    "Experiment Tracking":          "ml",
    # Engineering / DevOps
    "Git":                          "engineering",
    "Collaborative Development":    "engineering",
    "CI/CD":                        "engineering",
    "Linux / CLI":                  "engineering",
    "Operating Systems":            "engineering",
    "Networking Basics":            "engineering",
    "Databases":                    "engineering",
    "Backend Development":          "engineering",
    "System Design":                "engineering",
    "APIs and Microservices":       "engineering",
    "Distributed Systems":          "engineering",
    "Docker":                       "engineering",
    "Kubernetes":                   "engineering",
    "Cloud Platforms":              "engineering",
    "Infrastructure as Code":       "engineering",
    "Network Security":             "engineering",
    "Cryptography":                 "engineering",
    "Observability":                "engineering",
    "Concurrency":                  "engineering",
    # Web
    "HTML and CSS":                 "web",
    "JavaScript":                   "web",
    "TypeScript":                   "web",
    "React":                        "web",
    "Next.js":                      "web",
    "State Management":             "web",
    "Responsive Design":            "web",
    "Node.js":                      "web",
    "Web Performance":              "web",
    # Data Engineering
    "SQL Advanced":                 "data",
    "Data Warehousing":             "data",
    "dbt":                          "data",
    "Data Engineering":             "data",
    "Apache Spark":                 "data",
    "Apache Kafka":                 "data",
    "Real-time Processing":         "data",
    "Workflow Orchestration":       "data",
    "Data Quality":                 "data",
}


# ── Role requirements (7 roles) ──────────────────────────────
TARGET_ROLES: dict[str, list[str]] = {

    "AI Researcher": [
        "Python", "Linear Algebra", "Probability", "Statistics",
        "Calculus", "Optimisation", "Machine Learning", "Deep Learning",
        "PyTorch", "Research Methods", "Data Structures", "Algorithms",
        "Experiment Tracking", "Large Language Models",
    ],

    "Machine Learning Engineer": [
        "Python", "Linear Algebra", "Machine Learning", "Deep Learning",
        "PyTorch", "Feature Engineering", "Data Structures", "Algorithms",
        "Git", "Databases", "Backend Development", "Docker",
        "MLOps", "Model Serving", "Experiment Tracking",
    ],

    "Backend Engineer": [
        "Python", "Data Structures", "Algorithms",
        "Object Oriented Programming", "Design Patterns",
        "Databases", "SQL Advanced", "Backend Development",
        "System Design", "APIs and Microservices",
        "Git", "Linux / CLI", "Networking Basics",
        "Docker", "Testing and TDD", "Observability",
    ],

    "Data Scientist": [
        "Python", "Statistics", "Probability", "Linear Algebra",
        "Machine Learning", "Data Science", "Feature Engineering",
        "Hypothesis Testing", "Data Structures", "Git",
        "Databases", "SQL Advanced", "Time Series Analysis",
        "Data Engineering",
    ],

    "Full-Stack Developer": [
        "HTML and CSS", "JavaScript", "TypeScript", "React",
        "Node.js", "Python", "Databases", "SQL Advanced",
        "Backend Development", "APIs and Microservices",
        "Git", "Testing and TDD", "Responsive Design",
        "Docker", "Web Performance",
    ],

    "MLOps Engineer": [
        "Python", "Machine Learning", "Docker", "Kubernetes",
        "Cloud Platforms", "CI/CD", "MLOps", "Model Serving",
        "Infrastructure as Code", "Observability",
        "Experiment Tracking", "Linux / CLI", "Git",
        "Distributed Systems",
    ],

    "Data Engineer": [
        "Python", "SQL Advanced", "Data Warehousing", "dbt",
        "Apache Spark", "Apache Kafka", "Data Engineering",
        "Workflow Orchestration", "Cloud Platforms",
        "Data Quality", "Git", "Linux / CLI",
        "Distributed Systems", "Databases",
    ],
}


# ── Gap analysis engine (unchanged algorithm) ─────────────────
def compute_skill_gap(user_skills: list[str], role: str) -> dict:
    if role not in TARGET_ROLES:
        valid = ", ".join(TARGET_ROLES.keys())
        raise ValueError(f"Role '{role}' not found. Valid roles: {valid}")

    G = load_default_graph()
    required_skills = TARGET_ROLES[role]
    graph_nodes_lower = {node.lower(): node for node in G.nodes()}

    user_skills_canonical = []
    for skill in user_skills:
        canonical = graph_nodes_lower.get(skill.lower())
        user_skills_canonical.append(canonical if canonical else skill)

    user_skill_set     = set(user_skills_canonical)
    required_skill_set = set(required_skills)
    known_skills       = sorted(required_skill_set & user_skill_set)
    missing_skills     = sorted(required_skill_set - user_skill_set)

    learning_paths: dict[str, list[str]] = {}
    for target_skill in missing_skills:
        if target_skill not in G.nodes():
            learning_paths[target_skill] = [target_skill]
            continue
        best_path = None
        for start_skill in user_skill_set:
            if start_skill not in G.nodes() or start_skill == target_skill:
                continue
            try:
                path = nx.shortest_path(G, source=start_skill, target=target_skill)
                if best_path is None or len(path) < len(best_path):
                    best_path = path
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
        learning_paths[target_skill] = best_path if best_path else [target_skill]

    return {
        "known_skills":   known_skills,
        "missing_skills": missing_skills,
        "learning_paths": learning_paths,
    }


def get_graph_summary() -> dict:
    G = load_default_graph()
    return {
        "total_nodes":     G.number_of_nodes(),
        "total_edges":     G.number_of_edges(),
        "all_skills":      sorted(G.nodes()),
        "available_roles": list(TARGET_ROLES.keys()),
        "is_dag":          nx.is_directed_acyclic_graph(G),
    }
