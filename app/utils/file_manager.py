from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Tuple

import streamlit as st


class FileManager:
    """
    Utility wrapper to persist uploaded files into local storage.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_uploaded_file(self, uploaded_file, prefix: str) -> Path:
        """
        Persist an uploaded file under the base directory.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        safe_name = uploaded_file.name.replace(" ", "_")
        target_path = self.base_dir / f"{prefix}_{timestamp}_{safe_name}"

        with open(target_path, "wb") as dst:
            dst.write(uploaded_file.getbuffer())

        return target_path

    def stage_files(
        self, files: Iterable, prefix: str
    ) -> Iterable[Tuple[str, Path]]:
        """
        Save multiple files and return their names with paths.
        """
        for uploaded in files:
            try:
                saved_path = self.save_uploaded_file(uploaded, prefix)
                yield uploaded.name, saved_path
            except Exception as exc:  # pragma: no cover - streamlit runtime
                st.error(f"Failed to save {uploaded.name}: {exc}")

    @staticmethod
    def copy_to(source: Path, destination: Path) -> None:
        """
        Copy artifacts (e.g., CSV output) into a user-accessible folder.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


