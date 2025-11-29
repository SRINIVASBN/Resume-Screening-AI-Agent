from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

from app.utils.text_utils import (
    clean_text,
    estimate_years_of_experience,
    extract_skills,
)

logger = logging.getLogger(__name__)


@dataclass
class CandidateScore:
    candidate_name: str
    file_name: str
    similarity: float
    skill_alignment: float
    experience_score: float
    match_score: float
    llm_feedback: Dict[str, str]


class CandidateScorer:
    """
    Calculate composite scores for each candidate.
    """

    def __init__(self, vector_manager, llm_client):
        self.vector_manager = vector_manager
        self.llm_client = llm_client

    def evaluate(
        self,
        jd_text: str,
        jd_vector: List[float],
        top_k: int | None = None,
    ) -> List[CandidateScore]:
        search_results = self.vector_manager.similarity_search_with_scores(
            jd_vector, k=top_k
        )

        jd_skills = extract_skills(jd_text)
        jd_experience = estimate_years_of_experience(jd_text)

        evaluations: List[CandidateScore] = []
        for metadata, score in search_results:
            resume_id = metadata.get("candidate_id")
            resume_entry = self.vector_manager.get_resume_by_id(resume_id)
            if not resume_entry:
                continue

            resume_text = resume_entry["text"]
            cleaned_resume = clean_text(resume_text)
            similarity = self._normalize_similarity(score)
            skill_alignment = self._score_skills(jd_skills, resume_text)
            experience_score = self._score_experience(jd_experience, resume_text)
            match_score = self._blend_scores(
                similarity, skill_alignment, experience_score
            )
            feedback = self.llm_client.analyze_candidate(
                metadata.get("candidate_name", "Candidate"),
                jd_text,
                cleaned_resume,
            )

            evaluations.append(
                CandidateScore(
                    candidate_name=metadata.get("candidate_name", "Candidate"),
                    file_name=metadata.get("file_name", "N/A"),
                    similarity=round(similarity * 100, 2),
                    skill_alignment=round(skill_alignment * 100, 2),
                    experience_score=round(experience_score * 100, 2),
                    match_score=round(match_score * 100, 2),
                    llm_feedback=feedback,
                )
            )

        return sorted(evaluations, key=lambda c: c.match_score, reverse=True)

    @staticmethod
    def _normalize_similarity(distance: float) -> float:
        return 1 / (1 + distance)

    @staticmethod
    def _score_skills(jd_skills, resume_text: str) -> float:
        if not jd_skills:
            return 0.5
        resume_skills = extract_skills(resume_text)
        overlap = jd_skills.intersection(resume_skills)
        return len(overlap) / len(jd_skills) if jd_skills else 0.5

    @staticmethod
    def _score_experience(jd_experience, resume_text: str) -> float:
        resume_experience = estimate_years_of_experience(resume_text)
        if jd_experience and resume_experience:
            ratio = resume_experience / jd_experience
            return min(ratio, 1.2) / 1.2
        if resume_experience:
            return min(resume_experience / 10, 1.0)
        return 0.4

    @staticmethod
    def _blend_scores(similarity: float, skills: float, experience: float) -> float:
        return 0.55 * similarity + 0.25 * skills + 0.2 * experience

