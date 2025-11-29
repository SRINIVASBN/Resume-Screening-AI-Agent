from __future__ import annotations

import io
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app.embeddings.embedding_service import EmbeddingService, VectorStoreManager
from app.parsing.parser import DocumentParser
from app.ranking.matcher import CandidateScorer
from app.utils.file_manager import FileManager
from app.utils.llm_client import LLMClient
from app.utils.logger import configure_logging
from app.utils.text_utils import clean_llm_text, clean_text

st.set_page_config(page_title="Rooman Resume Screening AI Agent", layout="wide")
st.markdown(
    """
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {padding-top: 0.2rem !important;}
    body {background-color: #0f1116;}
    .run-btn {
        display: flex;
        align-items: flex-end;
        justify-content: center;
        height: 100%;
    }
    .run-btn button {
        width: 80%;
        animation: pulseGlow 2s ease-in-out infinite;
    }
    @keyframes pulseGlow {
        0% {transform: translateY(0); box-shadow: 0 0 0 rgba(64,153,255,0.0);}
        50% {transform: translateY(-2px); box-shadow: 0 6px 18px rgba(64,153,255,0.35);}
        100% {transform: translateY(0); box-shadow: 0 0 0 rgba(64,153,255,0.0);}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
CHROMA_DIR = BASE_DIR / "storage" / "chroma"
LOG_DIR = BASE_DIR / "storage"


def init_services():
    configure_logging(LOG_DIR)
    logger = logging.getLogger(__name__)
    logger.info("Initializing services...")
    file_manager = FileManager(UPLOAD_DIR)
    parser = DocumentParser()
    embedding_service = EmbeddingService()
    vector_manager = VectorStoreManager(CHROMA_DIR)
    llm_client = LLMClient()
    scorer = CandidateScorer(vector_manager, llm_client)
    return file_manager, parser, embedding_service, vector_manager, llm_client, scorer


def run_ollama_health_check(llm_client: LLMClient) -> dict:
    try:
        if hasattr(llm_client, "health_check"):
            return llm_client.health_check()
    except Exception as exc:  # pragma: no cover - diagnostic helper
        return {"ok": False, "msg": str(exc), "models": None}
    return {"ok": False, "msg": "health_check not available", "models": None}


def render_sidebar(llm_client: LLMClient):
    st.markdown(
        """
        <style>
        .info-box {
            background: #284b63;
            color: #fff;
            padding: 14px;
            border-radius: 8px;
            margin-bottom: 12px;
            animation: pulse 3s ease-in-out infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 rgba(40,75,99,0); transform: translateY(0); }
            50% { box-shadow: 0 6px 20px rgba(40,75,99,0.08); transform: translateY(-2px); }
            100% { box-shadow: 0 0 0 rgba(40,75,99,0); transform: translateY(0); }
        }
        .status-badge { display:flex; align-items:center; gap:8px; }
        .status-icon { font-size: 1.2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "ollama_status" not in st.session_state:
        st.session_state.ollama_status = run_ollama_health_check(llm_client)
        st.session_state.ollama_checked_at = time.time()
    if "ollama_checking" not in st.session_state:
        st.session_state.ollama_checking = False

    with st.sidebar:
        st.markdown("### Screening Checklist")
        st.markdown(
            "- Upload a JD (PDF/TXT) or paste text\n"
            "- Upload multiple resumes (PDF/TXT)\n"
            "- Ensure Ollama is running locally\n"
            "- Click Run Screening to generate shortlist\n"
        )
        st.markdown(
            '<div class="info-box">All data stays local. Delete files by clearing the uploads folder.</div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("### System Status")

        if st.session_state.ollama_checking:
            st.button("Re-check Ollama", disabled=True, use_container_width=True)
        else:
            if st.button("Re-check Ollama", use_container_width=True):
                st.session_state.ollama_checking = True
                with st.spinner("Checking Ollama..."):
                    st.session_state.ollama_status = run_ollama_health_check(llm_client)
                    st.session_state.ollama_checked_at = time.time()
                st.session_state.ollama_checking = False

        status = st.session_state.ollama_status
        if status.get("ok"):
            st.markdown(
                '<div class="status-badge"><span class="status-icon">📶</span><b>Ollama: Connected</b></div>',
                unsafe_allow_html=True,
            )
            models = status.get("models") or []
            if models:
                st.caption("Models: " + ", ".join(models))
        else:
            st.markdown(
                '<div class="status-badge"><span class="status-icon">📵</span><b>Ollama: Not reachable</b></div>',
                unsafe_allow_html=True,
            )
            st.caption(status.get("msg") or "No response")

        checked_at = st.session_state.get("ollama_checked_at", time.time())
        st.caption(
            f"Last checked: {datetime.fromtimestamp(checked_at).strftime('%Y-%m-%d %H:%M:%S')}"
        )


def main():
    (
        file_manager,
        parser,
        embedding_service,
        vector_manager,
        llm_client,
        scorer,
    ) = init_services()
    render_sidebar(llm_client)

    st.markdown(
        """
        <style>
        .stExpander {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 0.75rem;
        }
        .metric-card {
            padding: 0.5rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <h1 style="white-space: nowrap; font-size: 2.6rem; margin-bottom: 0.1rem;">
            Rooman Resume Screening AI Agent
        </h1>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Job Description Input")
    jd_upload_col, jd_paste_col = st.columns([1, 1])
    with jd_upload_col:
        jd_upload = st.file_uploader(
            "Upload JD (PDF/TXT)", type=["pdf", "txt"], accept_multiple_files=False
        )
        st.caption("Use real employer-provided files for best parsing accuracy.")
    with jd_paste_col:
        jd_text_input = st.text_area(
            "Or paste job description text", height=140, placeholder="Paste JD text..."
        )
        use_pasted = st.checkbox(
            "Use pasted JD instead of uploaded file", value=False
        )
        st.caption("Great for quick edits or when you only have plain text.")

    st.markdown("### Upload Candidate Resumes")
    resume_col, run_col = st.columns([1, 1])
    with resume_col:
        resume_uploads = st.file_uploader(
            "Upload Resumes (PDF or TXT)",
            type=["pdf", "txt"],
            accept_multiple_files=True,
            key="resume_uploader",
        )
    with run_col:
        st.markdown("<div class='run-btn'>", unsafe_allow_html=True)
        st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="display:flex; justify-content:center;">
                <div style="width:70%;">
                    """
            ,
            unsafe_allow_html=True,
        )
        process = st.button("Run Screening", type="primary", key="run_screening")
        st.markdown("</div></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if not process:
        st.stop()

    if use_pasted and not jd_text_input.strip():
        st.error("Pasted JD is empty. Please add text or disable the override.")
        st.stop()

    if not use_pasted and not jd_upload:
        st.error("Please upload a JD file or enable the pasted JD option.")
        st.stop()

    if not resume_uploads:
        st.error("Please upload at least one resume.")
        st.stop()

    with st.spinner("Processing files..."):
        if use_pasted:
            jd_text = clean_text(jd_text_input)
            if not jd_text:
                st.error("Pasted job description is empty after cleaning.")
                st.stop()
            jd_display_name = "Pasted JD"
        else:
            jd_name, jd_path = next(
                file_manager.stage_files([jd_upload], prefix="jd"), (None, None)
            )
            if not jd_path:
                st.error("Failed to read job description.")
                st.stop()

            try:
                parsed_text = parser.extract_text(jd_path)
            except Exception as exc:
                st.error(f"Unable to parse job description: {exc}")
                st.stop()

            jd_text = clean_text(parsed_text)
            jd_display_name = jd_name or "Uploaded JD"

        if not jd_text:
            st.error("Job description is empty after parsing.")
            st.stop()

        resume_entries = []
        for idx, (original_name, path) in enumerate(
            file_manager.stage_files(resume_uploads, prefix="resume"), start=1
        ):
            try:
                text = parser.extract_text(path)
                if not text:
                    st.warning(f"{original_name} produced no text and will be skipped.")
                    continue
                resume_entries.append(
                    {
                        "text": text,
                        "metadata": {
                            "candidate_name": Path(original_name).stem.title(),
                            "file_name": original_name,
                        },
                    }
                )
            except Exception as exc:
                st.warning(f"Skipping {original_name}: {exc}")

        if not resume_entries:
            st.error("No valid resumes to process.")
            st.stop()

        vector_manager.build_store(resume_entries, embedding_service)
        try:
            jd_vector = embedding_service.embed_text(jd_text)
        except Exception as exc:
            st.error(f"Embedding generation failed: {exc}")
            st.stop()

        evaluations = scorer.evaluate(jd_text, jd_vector)

    if not evaluations:
        st.warning("No candidates were scored. Check logs for details.")
        st.stop()

    st.success(f"Screening complete for {jd_display_name}.")

    summary_rows = []
    for eval in evaluations:
        summary_rows.append(
            {
                "Candidate": eval.candidate_name,
                "File": eval.file_name,
                "Match %": eval.match_score,
                "Similarity %": eval.similarity,
                "Skill Alignment %": eval.skill_alignment,
                "Experience %": eval.experience_score,
                "Strengths": clean_llm_text(eval.llm_feedback["strengths"]),
                "Weaknesses": clean_llm_text(eval.llm_feedback["weaknesses"]),
                "Reasoning": clean_llm_text(eval.llm_feedback["reasoning"]),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df[["Candidate", "File", "Match %", "Similarity %", "Skill Alignment %", "Experience %"]], use_container_width=True)

    export_df = summary_df.copy()
    for col in ["Strengths", "Weaknesses", "Reasoning"]:
        if col in export_df.columns:
            export_df[col] = (
                export_df[col]
                .astype(str)
                .str.replace("\n", " ", regex=False)
                .str.replace(",", ";", regex=False)
            )

    csv_buffer = io.StringIO()
    export_df.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download Results (CSV)",
        data=csv_buffer.getvalue(),
        file_name="resume_results.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.subheader("Candidate Insights")
    for eval in evaluations:
        strengths = clean_llm_text(eval.llm_feedback["strengths"])
        weaknesses = clean_llm_text(eval.llm_feedback["weaknesses"])
        reasoning = clean_llm_text(eval.llm_feedback["reasoning"])

        with st.expander(f"{eval.candidate_name} — Match {eval.match_score}%"):
            metric_cols = st.columns(3)
            metric_cols[0].metric("Match %", f"{eval.match_score}%")
            metric_cols[1].metric("Similarity %", f"{eval.similarity}%")
            metric_cols[2].metric("Skill Align %", f"{eval.skill_alignment}%")

            skill_cols = st.columns(2)
            skill_cols[0].markdown(f"**Strengths**\n\n{strengths or 'Not provided.'}")
            skill_cols[1].markdown(f"**Weaknesses**\n\n{weaknesses or 'Not provided.'}")
            st.markdown(f"**Reasoning**\n\n{reasoning or 'Not provided.'}")

    st.info("Tip: rerun with refined JD keywords or adjust pasted JD text to tweak weighting.")


if __name__ == "__main__":
    main()

