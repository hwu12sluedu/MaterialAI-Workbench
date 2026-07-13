"""Persistent serial Abaqus job queue."""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.config import ABAQUS_BAT
from material_ai_workbench.logging_config import get_logger


logger = get_logger(__name__)
QUEUE_FILE = Path(__file__).resolve().parent / "job_queue.json"
HISTORY_FILE = Path(__file__).resolve().parent / "job_queue_history.json"


@dataclass
class QueuedJob:
    job_id: str
    name: str
    input_file: str
    work_dir: str
    status: str = "queued"
    cpus: int = 4
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started_at: str | None = None
    finished_at: str | None = None
    return_code: int | None = None
    log_path: str | None = None
    error_message: str | None = None
    retry_of: str | None = None


class JobQueue:
    """Small disk-backed FIFO queue for local Abaqus jobs."""

    def __init__(
        self,
        queue_file: Path | str = QUEUE_FILE,
        abaqus_bat: Path | str = ABAQUS_BAT,
        history_file: Path | str | None = None,
    ):
        self.queue_file = Path(queue_file)
        self.abaqus_bat = Path(abaqus_bat)
        self.history_file = Path(history_file) if history_file else self.queue_file.with_name(HISTORY_FILE.name)
        self.jobs: list[QueuedJob] = []
        self._running = False
        self._load()

    def submit(
        self,
        name: str,
        input_file: str | Path,
        work_dir: str | Path,
        cpus: int = 4,
        *,
        retry_of: str | None = None,
    ) -> QueuedJob:
        inp = Path(input_file).expanduser()
        wd = Path(work_dir).expanduser()
        job = QueuedJob(
            job_id=uuid.uuid4().hex[:8],
            name=_safe_job_name(name),
            input_file=str(inp),
            work_dir=str(wd),
            cpus=max(1, int(cpus)),
            retry_of=retry_of,
        )
        self.jobs.append(job)
        self._save()
        logger.info("Abaqus job queued: %s", job.name)
        return job

    def process_next(self, timeout_seconds: int = 7200) -> bool:
        if self._running:
            return False
        pending = [job for job in self.jobs if job.status == "queued"]
        if not pending:
            return False

        job = pending[0]
        job.status = "running"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        job.log_path = str(Path(job.work_dir) / f"{job.name}.log")
        self._running = True
        self._save()

        try:
            input_path = Path(job.input_file)
            command = [
                str(self.abaqus_bat),
                f"job={job.name}",
                f"input={input_path}",
                f"cpus={job.cpus}",
                "interactive",
            ]
            proc = subprocess.run(
                command,
                cwd=job.work_dir,
                capture_output=True,
                text=True,
                timeout=int(timeout_seconds),
            )
            Path(job.log_path).write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8", errors="replace")
            job.return_code = proc.returncode
            job.status = "completed" if proc.returncode == 0 else "failed"
            if proc.returncode != 0:
                job.error_message = (proc.stderr or proc.stdout or "")[-2000:]
        except subprocess.TimeoutExpired as exc:
            job.status = "failed"
            job.error_message = f"Job timed out after {timeout_seconds} seconds."
            if job.log_path:
                Path(job.log_path).write_text(str(exc), encoding="utf-8", errors="replace")
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            logger.exception("Abaqus job failed before completion: %s", job.name)
        finally:
            job.finished_at = datetime.now().isoformat(timespec="seconds")
            self._append_history(job)
            self._running = False
            self._save()
        return True

    def status(self) -> dict[str, Any]:
        counts: dict[str, int] = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
        for job in self.jobs:
            counts[job.status] = counts.get(job.status, 0) + 1
        return {"total": len(self.jobs), **counts, "is_processing": self._running}

    def list_jobs(self) -> list[QueuedJob]:
        return list(self.jobs)

    def clear_completed(self) -> None:
        self.jobs = [job for job in self.jobs if job.status in {"queued", "running"}]
        self._save()

    def retry(self, job_id: str) -> QueuedJob:
        source = self._find_job(job_id)
        if source.status not in {"failed", "timeout"}:
            raise ValueError("Only failed jobs can be retried.")
        return self.submit(
            f"{source.name}_retry",
            source.input_file,
            source.work_dir,
            cpus=source.cpus,
            retry_of=source.job_id,
        )

    def history(self) -> list[dict[str, Any]]:
        if not self.history_file.exists():
            return []
        try:
            payload = json.loads(self.history_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        rows = payload.get("history", [])
        return rows if isinstance(rows, list) else []

    def statistics(self) -> dict[str, Any]:
        history = self.history()
        completed = [row for row in history if row.get("status") == "completed"]
        failed = [row for row in history if row.get("status") == "failed"]
        finished = completed + failed
        durations = [_duration_seconds(row.get("started_at"), row.get("finished_at")) for row in finished]
        durations = [value for value in durations if value is not None]
        return {
            **self.status(),
            "history_total": len(history),
            "history_completed": len(completed),
            "history_failed": len(failed),
            "success_rate": (len(completed) / len(finished)) if finished else None,
            "average_duration_seconds": (sum(durations) / len(durations)) if durations else None,
        }

    def log_text(self, job_id: str, *, max_chars: int = 8000) -> str:
        job = self._find_job(job_id)
        if not job.log_path:
            return ""
        path = Path(job.log_path)
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max(1, int(max_chars)) :]

    def _find_job(self, job_id: str) -> QueuedJob:
        for job in self.jobs:
            if job.job_id == job_id:
                return job
        raise KeyError(f"Job not found: {job_id}")

    def _load(self) -> None:
        if not self.queue_file.exists():
            return
        payload = json.loads(self.queue_file.read_text(encoding="utf-8"))
        self.jobs = [QueuedJob(**item) for item in payload.get("jobs", []) if isinstance(item, dict)]

    def _save(self) -> None:
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "abaqus_bat": str(self.abaqus_bat),
            "jobs": [asdict(job) for job in self.jobs],
        }
        self.queue_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _append_history(self, job: QueuedJob) -> None:
        if job.status not in {"completed", "failed"}:
            return
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": datetime.now().isoformat(timespec="seconds"), "history": self.history()}
        row = asdict(job)
        row["archived_at"] = datetime.now().isoformat(timespec="seconds")
        payload["history"].append(row)
        self.history_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _safe_job_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value).strip())
    return safe or "abaqus_job"


def _duration_seconds(started_at: Any, finished_at: Any) -> float | None:
    try:
        start = datetime.fromisoformat(str(started_at))
        finish = datetime.fromisoformat(str(finished_at))
    except (TypeError, ValueError):
        return None
    return max(0.0, (finish - start).total_seconds())
