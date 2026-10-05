from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from app.core.config import get_settings

settings = get_settings()


class PdfExportError(RuntimeError):
    pass


class PdfExporter:
    def convert_docx(self, docx_path: Path, pdf_path: Path) -> Path:
        binary = shutil.which(settings.libreoffice_binary) or shutil.which("libreoffice")
        if not binary:
            raise PdfExportError("LibreOffice/soffice is not installed")

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile:
            cmd = [
                binary,
                "--headless",
                f"-env:UserInstallation=file://{Path(profile).as_posix()}",
                "--convert-to", "pdf",
                "--outdir", str(pdf_path.parent),
                str(docx_path),
            ]
            env = os.environ.copy()
            env["HOME"] = profile
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=90,
                env=env,
            )

        generated = pdf_path.parent / (docx_path.stem + ".pdf")
        if not generated.exists() or generated.stat().st_size == 0:
            raise PdfExportError(
                "PDF conversion failed. stdout=" + proc.stdout[-500:] + " stderr=" + proc.stderr[-500:]
            )
        if generated != pdf_path:
            if pdf_path.exists():
                pdf_path.unlink()
            generated.replace(pdf_path)
        return pdf_path
