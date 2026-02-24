# app/analytics/planner.py
# ============================================================
# SEMESTER LEARNING PLANNER
#
# Converts a gap-analysis roadmap into a concrete weekly study
# schedule, distributing skills across weeks proportional to
# their estimated learning effort.
#
# ALGORITHM OVERVIEW
# ──────────────────
# 1. Flatten all learning paths from compute_skill_gap() into
#    an ordered, deduplicated sequence (respecting prerequisites:
#    prerequisites always appear before the skills that need them).
#
# 2. Assign a "difficulty weight" to each skill.
#    Weights are expressed in "study-weeks" — the expected number
#    of weeks a typical CS student needs to gain working proficiency.
#    These are manually calibrated estimates, not ML predictions.
#
# 3. Compute total_weeks = months × 4 (approximation).
#    Scale weights so they sum to exactly total_weeks.
#
# 4. Assign each skill to a week range [start_week, end_week].
#    Skills with weight < 1 are batched together in one week.
#
# WHY DETERMINISTIC WEIGHTS?
#   A reproducible planner is more academically useful than a
#   "smart" adaptive one that professors cannot audit. Each weight
#   is documented with its educational rationale below.
# ============================================================

from app.graph_engine import compute_skill_gap, TARGET_ROLES


# ── Skill difficulty weights ──────────────────────────────────
# Unit: estimated study-weeks for a motivated CS undergraduate.
# These are informed by standard CS curriculum credit-hour allocations
# and typical MOOCs (Coursera, edX) completion time data.

SKILL_WEIGHTS: dict[str, float] = {
    # Programming fundamentals — quick to learn with daily practice
    "Python":                       1.0,
    "File I/O and APIs":            0.5,
    "Object Oriented Programming":  1.0,
    "Design Patterns":              1.5,
    "Problem Solving":              1.0,

    # Data Structures & Algorithms — core CS, significant depth
    "Data Structures":              2.0,
    "Algorithms":                   2.5,

    # Mathematics — foundational but time-intensive
    "Calculus":                     3.0,
    "Linear Algebra":               3.0,
    "Probability":                  2.5,
    "Statistics":                   2.0,
    "Hypothesis Testing":           1.5,

    # ML / AI — broad fields requiring multiple prerequisites
    "Machine Learning":             4.0,
    "Deep Learning":                3.5,
    "Computer Vision":              3.0,
    "NLP":                          3.0,
    "Reinforcement Learning":       3.5,
    "PyTorch":                      2.0,
    "Data Science":                 2.0,
    "Research Methods":             2.0,

    # Software Engineering — largely practical, faster with projects
    "Git":                          0.5,
    "Linux / CLI":                  0.5,
    "Scripting":                    0.5,
    "Databases":                    1.5,
    "Networking Basics":            1.5,
    "Operating Systems":            2.0,
    "Backend Development":          2.0,
    "APIs and Microservices":       1.5,
    "System Design":                2.5,
    "Distributed Systems":          3.0,
    "CI/CD":                        1.0,
    "Collaborative Development":    0.5,
}

# Default weight for any skill not explicitly listed
DEFAULT_WEIGHT = 1.5


def generate_study_plan(
    user_skills: list[str],
    target_role: str,
    hours_per_week: int,
    months: int,
) -> dict:
    """
    Generate a concrete weekly study plan for a student's skill gaps.

    The planner respects prerequisite ordering: if the roadmap says
    "learn Linear Algebra before Machine Learning", then Linear Algebra
    will always appear in an earlier week block than Machine Learning.

    Args:
        user_skills:    Skills the student currently has.
        target_role:    Career role (key from TARGET_ROLES).
        hours_per_week: How many hours per week the student can study.
                        Used to add effort context to each skill entry.
        months:         Total months available for the study plan.
                        Determines how many weeks are available.

    Returns:
        dict with keys:
            target_role     — the role name
            total_weeks     — months × 4
            hours_per_week  — as provided
            total_hours     — total_weeks × hours_per_week
            skills_to_learn — ordered list of skill names
            weeks           — list of week-block dicts (see below)
            summary         — plain-text description

        Each week-block dict:
            week_start     — int (1-indexed)
            week_end       — int (inclusive)
            skill          — skill name
            difficulty     — "Light" | "Moderate" | "Intensive"
            hours_required — estimated hours for this skill
            study_tips     — one-line actionable study tip

    Raises:
        ValueError: If role is unknown or months < 1.

    Academic use:
        A student can download this plan and track completion week-by-week.
        A professor can verify the plan is prerequisite-ordered.
    """
    if target_role not in TARGET_ROLES:
        raise ValueError(f"Role '{target_role}' not found. Valid: {list(TARGET_ROLES.keys())}")
    if months < 1:
        raise ValueError("months must be at least 1")

    # ── Step 1: Get ordered skill list from gap analysis ──────────
    gap = compute_skill_gap(user_skills, target_role)

    # Flatten paths into prerequisite-respecting order.
    # compute_skill_gap returns paths like:
    #   {"Machine Learning": ["Python", "Linear Algebra", "Machine Learning"]}
    # We walk each path in order so prerequisites are always scheduled first.
    seen   = set(gap["known_skills"])  # Don't re-schedule already-known skills
    skills = []
    for path in gap["learning_paths"].values():
        for skill in path:
            if skill not in seen:
                seen.add(skill)
                skills.append(skill)

    if not skills:
        return {
            "target_role":     target_role,
            "total_weeks":     months * 4,
            "hours_per_week":  hours_per_week,
            "total_hours":     months * 4 * hours_per_week,
            "skills_to_learn": [],
            "weeks":           [],
            "summary":         "No missing skills — student is already qualified for this role!",
        }

    # ── Step 2: Assign raw difficulty weights ─────────────────────
    raw_weights = [SKILL_WEIGHTS.get(s, DEFAULT_WEIGHT) for s in skills]
    total_raw   = sum(raw_weights)

    # ── Step 3: Scale weights to fit the available weeks ─────────
    total_weeks = months * 4
    # Scale each weight proportionally so they sum to total_weeks
    scale = total_weeks / total_raw
    scaled_weights = [max(1.0, w * scale) for w in raw_weights]

    # Re-normalize after clamping: recalculate so sum stays ≤ total_weeks
    weight_sum = sum(scaled_weights)
    if weight_sum > total_weeks:
        scaled_weights = [w * (total_weeks / weight_sum) for w in scaled_weights]

    # ── Step 4: Build week-block schedule ─────────────────────────
    week_blocks = []
    current_week = 1.0

    for skill, weight in zip(skills, scaled_weights):
        start = round(current_week)
        end   = round(current_week + weight - 1)
        end   = max(start, end)           # Guarantee at least 1 week
        end   = min(end, total_weeks)     # Don't exceed plan duration

        hours_for_skill = round(weight * hours_per_week)

        week_blocks.append({
            "week_start":     start,
            "week_end":       end,
            "skill":          skill,
            "difficulty":     _difficulty_label(SKILL_WEIGHTS.get(skill, DEFAULT_WEIGHT)),
            "hours_required": hours_for_skill,
            "study_tips":     STUDY_TIPS.get(skill, "Build projects that apply this skill in context."),
        })

        current_week += weight

    # ── Step 5: Build summary ─────────────────────────────────────
    total_hours   = total_weeks * hours_per_week
    summary = (
        f"Study plan for {target_role}: {len(skills)} skills over {total_weeks} weeks "
        f"({months} month{'s' if months > 1 else ''}), "
        f"~{hours_per_week} hours/week ({total_hours} hours total)."
    )

    return {
        "target_role":     target_role,
        "total_weeks":     total_weeks,
        "hours_per_week":  hours_per_week,
        "total_hours":     total_hours,
        "skills_to_learn": skills,
        "weeks":           week_blocks,
        "summary":         summary,
    }


def _difficulty_label(raw_weight: float) -> str:
    """
    Convert a raw difficulty weight into a human-readable label.

    Labels map to approximate study intensity:
        Light     → < 1.5 weeks  (quick review, daily practice sufficient)
        Moderate  → 1.5–2.5 weeks (structured learning + exercises needed)
        Intensive → > 2.5 weeks  (deep topic, project-based learning required)
    """
    if raw_weight < 1.5:
        return "Light"
    elif raw_weight <= 2.5:
        return "Moderate"
    else:
        return "Intensive"


# ── Study tips library ────────────────────────────────────────
# One actionable sentence per skill, shown in the study plan.
STUDY_TIPS: dict[str, str] = {
    "Python":                    "Complete 'Python for Everybody' (Coursera) and write a small CLI tool.",
    "Data Structures":           "Implement stacks, queues, trees and hash maps from scratch in Python.",
    "Algorithms":                "Work through 50 LeetCode problems (Easy → Medium). Focus on Big-O analysis.",
    "Object Oriented Programming": "Refactor a past project into classes; study SOLID principles.",
    "Design Patterns":           "Read 'Head First Design Patterns'; implement 5 patterns from memory.",
    "Calculus":                  "Work through 3Blue1Brown 'Essence of Calculus' + Khan Academy exercises.",
    "Linear Algebra":            "Study '3Blue1Brown: Essence of Linear Algebra' then Gilbert Strang MIT OCW.",
    "Probability":               "Work through Blitzstein & Hwang 'Introduction to Probability' (free PDF).",
    "Statistics":                "Complete StatQuest on YouTube + run real analyses on a public dataset.",
    "Hypothesis Testing":        "Design and run 3 A/B tests on a dataset; report p-values and effect sizes.",
    "Research Methods":          "Read 5 top ML papers on arXiv; write a 1-page summary of each.",
    "Machine Learning":          "Complete Andrew Ng's ML Specialization (Coursera) with all assignments.",
    "Deep Learning":             "Complete fast.ai Part 1 + build a CNN from scratch with PyTorch.",
    "PyTorch":                   "Reproduce a paper from arXiv in PyTorch and publish to GitHub.",
    "NLP":                       "Build a text classifier and fine-tune a HuggingFace BERT model.",
    "Computer Vision":           "Train a YOLO model on a custom dataset; study the original CV papers.",
    "Reinforcement Learning":    "Complete David Silver's RL course + implement DQN from scratch.",
    "Data Science":              "Complete a full EDA + modeling project on a Kaggle dataset.",
    "Git":                       "Contribute to any open-source project via pull request.",
    "Linux / CLI":               "Set up a Linux VM; practice scripting and file management for 1 week.",
    "Databases":                 "Complete SQLZoo + build a CRUD app with PostgreSQL.",
    "Networking Basics":         "Study Tanenbaum Ch. 1–5; capture and analyse traffic with Wireshark.",
    "Operating Systems":         "Study OSTEP (free textbook) + implement a shell in C.",
    "Backend Development":       "Build a REST API with FastAPI and deploy it on a cloud VM.",
    "System Design":             "Study 'Designing Data-Intensive Applications' (Kleppmann), Chapter 1–3.",
    "Distributed Systems":       "Study Kleppmann Ch. 5–9 + implement a basic Raft consensus in Python.",
    "CI/CD":                     "Set up GitHub Actions to lint, test, and deploy a small project.",
    "APIs and Microservices":    "Decompose a monolithic app into 3 microservices with API gateways.",
    "Scripting":                 "Automate a repetitive task (file sync, data fetch) with a bash/Python script.",
    "Collaborative Development": "Participate in a team project with PRs, code review, and issue tracking.",
}
