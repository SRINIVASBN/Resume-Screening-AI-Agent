CANDIDATE_FEEDBACK_PROMPT = """
You are an expert technical recruiter.
Given the job description and a candidate resume, summarize:
1. Key strengths (bullet friendly sentence).
2. Potential weaknesses or red flags.
3. Provide a short reasoning paragraph (2-3 sentences) on overall fit.

Format response as:
Strengths: ...
Weaknesses: ...
Reasoning: ...

Candidate: {candidate_name}
Job Description:
{job_description}

Resume:
{resume_text}
"""

