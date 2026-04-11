import json
import logging
import os
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Set

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)


@dataclass
class RepositoryAnalysisResult:
    summary_text: str
    stats: Dict[str, Any]


class RepositoryAnalyzer:
    """
    Safely extracts and summarizes uploaded project archives for report context.
    """

    MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
    MAX_EXTRACTED_BYTES = 120 * 1024 * 1024
    MAX_ARCHIVE_FILES = 3000
    MAX_COMPRESSION_RATIO = 120
    MAX_FILE_READ_CHARS = 20000
    MAX_ROUTE_FILES = 12
    MAX_KEY_FILES = 15
    MAX_DEPENDENCIES = 20
    MAX_CONTEXT_CHARS = 2400
    CHUNK_SIZE = 1024 * 1024

    IGNORED_DIRS: Set[str] = {
        ".git",
        ".github",
        "node_modules",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".idea",
        ".vscode",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".venv",
        "venv",
        "env",
        "target",
        "coverage",
    }

    BINARY_EXTENSIONS: Set[str] = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".jar",
        ".class",
        ".mp4",
        ".mp3",
        ".woff",
        ".woff2",
    }

    KEY_FILENAMES: Set[str] = {
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "requirements.txt",
        "pyproject.toml",
        "poetry.lock",
        "main.py",
        "app.py",
        "server.js",
        "server.ts",
        "index.js",
        "index.ts",
        "manage.py",
    }

    async def analyze_upload(self, upload: UploadFile) -> RepositoryAnalysisResult:
        if not upload.filename or not upload.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Uploaded file must be a .zip archive")

        temp_root = tempfile.mkdtemp(prefix="repo_upload_")
        archive_path = os.path.join(temp_root, "source.zip")
        extract_dir = os.path.join(temp_root, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        try:
            archive_size = await self._persist_upload(upload, archive_path)
            return self._analyze_archive_path(archive_path, extract_dir, archive_size)
        finally:
            await upload.close()
            shutil.rmtree(temp_root, ignore_errors=True)

    def analyze_archive_bytes(self, filename: str, payload: bytes) -> RepositoryAnalysisResult:
        if not filename or not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Uploaded file must be a .zip archive")

        archive_size = len(payload)
        if archive_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded ZIP is empty")
        if archive_size > self.MAX_ARCHIVE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"ZIP exceeds {self.MAX_ARCHIVE_BYTES // (1024 * 1024)}MB limit",
            )

        temp_root = tempfile.mkdtemp(prefix="repo_upload_")
        archive_path = os.path.join(temp_root, "source.zip")
        extract_dir = os.path.join(temp_root, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        try:
            with open(archive_path, "wb") as archive_file:
                archive_file.write(payload)
            return self._analyze_archive_path(archive_path, extract_dir, archive_size)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def _analyze_archive_path(self, archive_path: str, extract_dir: str, archive_size: int) -> RepositoryAnalysisResult:
        extraction_stats = self._safe_extract(archive_path, extract_dir)
        summary_text, summary_stats = self._summarize(extract_dir)
        stats = {
            "archive_size_bytes": archive_size,
            "extracted_bytes": extraction_stats["extracted_bytes"],
            "extracted_files": extraction_stats["extracted_files"],
            **summary_stats,
        }
        return RepositoryAnalysisResult(summary_text=summary_text, stats=stats)

    async def _persist_upload(self, upload: UploadFile, output_path: str) -> int:
        total_bytes = 0
        with open(output_path, "wb") as out_file:
            while True:
                chunk = await upload.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > self.MAX_ARCHIVE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"ZIP exceeds {self.MAX_ARCHIVE_BYTES // (1024 * 1024)}MB limit",
                    )
                out_file.write(chunk)
        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded ZIP is empty")
        return total_bytes

    def _safe_extract(self, archive_path: str, extract_dir: str) -> Dict[str, int]:
        extracted_bytes = 0
        extracted_files = 0
        base_path = Path(extract_dir).resolve()

        try:
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()
                if len(members) > self.MAX_ARCHIVE_FILES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"ZIP has too many files (max {self.MAX_ARCHIVE_FILES})",
                    )

                for member in members:
                    if member.is_dir():
                        continue

                    extracted_bytes += member.file_size
                    if extracted_bytes > self.MAX_EXTRACTED_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Extracted content exceeds {self.MAX_EXTRACTED_BYTES // (1024 * 1024)}MB",
                        )

                    if member.compress_size > 0:
                        ratio = member.file_size / member.compress_size
                        if ratio > self.MAX_COMPRESSION_RATIO:
                            raise HTTPException(
                                status_code=400,
                                detail="ZIP appears unsafe (extreme compression ratio detected)",
                            )

                    member_path = PurePosixPath(member.filename)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise HTTPException(status_code=400, detail="ZIP contains unsafe file paths")

                    dest_path = (base_path / Path(*member_path.parts)).resolve()
                    if base_path not in dest_path.parents and dest_path != base_path:
                        raise HTTPException(status_code=400, detail="ZIP contains unsafe extraction targets")

                    os.makedirs(dest_path.parent, exist_ok=True)
                    with archive.open(member) as source, open(dest_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted_files += 1
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Invalid ZIP archive") from exc

        return {"extracted_bytes": extracted_bytes, "extracted_files": extracted_files}

    def _summarize(self, extract_dir: str) -> tuple[str, Dict[str, Any]]:
        language_counter: Counter = Counter()
        top_dirs: Counter = Counter()
        route_files: List[str] = []
        key_files: List[str] = []
        dependencies: Set[str] = set()
        readme_excerpt = ""
        total_files = 0

        for root, dirs, files in os.walk(extract_dir):
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS and not d.startswith(".")]

            for filename in files:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, extract_dir).replace("\\", "/")
                total_files += 1

                top = rel_path.split("/")[0]
                top_dirs[top] += 1

                ext = Path(filename).suffix.lower()
                if ext:
                    language_counter[self._language_name(ext)] += 1

                lowered_name = filename.lower()
                lowered_path = rel_path.lower()

                if lowered_name in self.KEY_FILENAMES and len(key_files) < self.MAX_KEY_FILES:
                    key_files.append(rel_path)

                if re.search(r"(route|router|controller|api|endpoint)", lowered_path):
                    if len(route_files) < self.MAX_ROUTE_FILES:
                        route_files.append(rel_path)

                if not readme_excerpt and lowered_name.startswith("readme"):
                    readme_excerpt = " ".join(self._read_text(filepath, 500).split())

                if lowered_name == "package.json":
                    dependencies.update(self._extract_node_dependencies(filepath))
                elif lowered_name == "requirements.txt":
                    dependencies.update(self._extract_python_requirements(filepath))
                elif lowered_name == "pyproject.toml":
                    dependencies.update(self._extract_pyproject_dependencies(filepath))

        detected_stack = self._detect_stack(dependencies, key_files, language_counter)
        sorted_languages = [name for name, _ in language_counter.most_common(5)]
        sorted_dirs = [name for name, _ in top_dirs.most_common(8)]
        top_dependencies = sorted(dependencies)[: self.MAX_DEPENDENCIES]

        summary_lines = [
            "CODEBASE ANALYSIS (auto extracted from uploaded archive):",
            f"- Total files scanned: {total_files}",
            f"- Primary languages: {', '.join(sorted_languages) if sorted_languages else 'Unknown'}",
            f"- Major directories: {', '.join(sorted_dirs) if sorted_dirs else 'Not detected'}",
            f"- Detected stack/frameworks: {', '.join(detected_stack) if detected_stack else 'Not confidently detected'}",
            f"- Key project files: {', '.join(key_files) if key_files else 'Not detected'}",
            f"- API/route-related files: {', '.join(route_files) if route_files else 'Not detected'}",
            f"- Representative dependencies: {', '.join(top_dependencies) if top_dependencies else 'Not detected'}",
        ]
        if readme_excerpt:
            summary_lines.append(f"- README excerpt: {readme_excerpt}")
        summary_lines.append(
            "Use this extracted evidence as primary context and avoid inventing architecture details that are not supported by the scan."
        )

        summary_text = "\n".join(summary_lines)
        if len(summary_text) > self.MAX_CONTEXT_CHARS:
            summary_text = summary_text[: self.MAX_CONTEXT_CHARS - 3] + "..."

        stats = {
            "scanned_files": total_files,
            "detected_stack": detected_stack,
            "top_languages": sorted_languages,
        }
        return summary_text, stats

    def _read_text(self, path: str, max_chars: int) -> str:
        ext = Path(path).suffix.lower()
        if ext in self.BINARY_EXTENSIONS:
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                return file.read(max_chars)
        except Exception:
            return ""

    def _extract_node_dependencies(self, package_json_path: str) -> Set[str]:
        text = self._read_text(package_json_path, self.MAX_FILE_READ_CHARS)
        if not text:
            return set()
        try:
            payload = json.loads(text)
            deps = payload.get("dependencies", {})
            dev_deps = payload.get("devDependencies", {})
            keys = set(deps.keys()) | set(dev_deps.keys())
            return {k.lower() for k in keys}
        except Exception:
            return set()

    def _extract_python_requirements(self, requirements_path: str) -> Set[str]:
        text = self._read_text(requirements_path, self.MAX_FILE_READ_CHARS)
        if not text:
            return set()

        deps = set()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            dep = re.split(r"[<>=~!]", stripped, maxsplit=1)[0].strip().lower()
            if dep:
                deps.add(dep)
        return deps

    def _extract_pyproject_dependencies(self, pyproject_path: str) -> Set[str]:
        text = self._read_text(pyproject_path, self.MAX_FILE_READ_CHARS)
        if not text:
            return set()

        deps = set()
        matches = re.findall(r'([A-Za-z0-9_\-\.]+)\s*(?:=|>=|<=|~=|>|<)', text)
        for match in matches:
            value = match.lower()
            if value not in {"python", "name", "version", "description"}:
                deps.add(value)
        return deps

    def _detect_stack(self, dependencies: Set[str], key_files: List[str], languages: Counter) -> List[str]:
        stack: List[str] = []
        dep_blob = " ".join(sorted(dependencies))
        key_blob = " ".join([k.lower() for k in key_files])

        if any(token in dep_blob for token in ["fastapi", "uvicorn", "pydantic"]):
            stack.append("FastAPI")
        if any(token in dep_blob for token in ["django", "djangorestframework"]):
            stack.append("Django")
        if any(token in dep_blob for token in ["flask", "gunicorn"]):
            stack.append("Flask")
        if any(token in dep_blob for token in ["react", "next", "vite"]):
            stack.append("React ecosystem")
        if any(token in dep_blob for token in ["express", "nestjs", "koa"]):
            stack.append("Node.js backend")
        if "dockerfile" in key_blob or "docker-compose" in key_blob:
            stack.append("Dockerized deployment")
        if languages.get("TypeScript", 0) > 0 and "React ecosystem" not in stack:
            stack.append("TypeScript project")
        if languages.get("Python", 0) > 0 and "FastAPI" not in stack and "Django" not in stack and "Flask" not in stack:
            stack.append("Python service")

        return stack

    def _language_name(self, extension: str) -> str:
        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".cs": "C#",
            ".php": "PHP",
            ".rb": "Ruby",
            ".kt": "Kotlin",
            ".swift": "Swift",
            ".sql": "SQL",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".md": "Markdown",
            ".json": "JSON",
            ".yml": "YAML",
            ".yaml": "YAML",
        }
        return mapping.get(extension, extension.strip(".").upper() or "Unknown")
