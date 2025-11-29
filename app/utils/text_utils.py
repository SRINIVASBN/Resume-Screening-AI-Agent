import re
from typing import List, Set

COMMON_SKILLS = {
    "python",
    "java",
    "c++",
    "sql",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "pandas",
    "numpy",
    "tensorflow",
    "pytorch",
    "nlp",
    "machine learning",
    "data analysis",
    "react",
    "javascript",
    "django",
    "flask",
    "spark",
    "hadoop",
    "tableau",
}


def clean_text(text: str) -> str:
    """
    Normalize whitespace for consistent downstream processing.
    """
    return re.sub(r"\s+", " ", text).strip()


def extract_skills(text: str) -> Set[str]:
    """
    Rough skill extraction via dictionary lookup.
    """
    lowered = text.lower()
    return {skill for skill in COMMON_SKILLS if skill in lowered}


def estimate_years_of_experience(text: str) -> float | None:
    """
    Estimate years of experience by scanning for patterns like '5 years'.
    """
    pattern = re.compile(r"(\d{1,2})(?:\+)?\s*(?:years|yrs)", re.IGNORECASE)
    matches = [int(m.group(1)) for m in pattern.finditer(text)]
    if matches:
        return sum(matches) / len(matches)
    return None


def split_sentences(text: str) -> List[str]:
    """
    Naive sentence splitter used for generating concise summaries.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def clean_llm_text(text: str) -> str:
    """
    Sanitize LLM output for UI/CSV consumption.
    """
    if not text:
        return ""
    sanitized = text.replace("***", "").replace("**", "")
    return " ".join(sanitized.split())


