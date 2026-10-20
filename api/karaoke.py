from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

OWNER = os.environ.get("KAGGLE_USERNAME", "").strip()
JOB_RE = re.compile(r"^[a-f0-9]{32}$")
MUKA_PATH_RE = re.compile(r"^/dynps/share/[A-Za-z0-9_%=-]+/?$")


def _safe_diagnostic(value: object) -> str:
    """Keep useful server diagnostics without exposing credentials or media links."""
    message = str(value)
    for key in ("SITE_ACCESS_PIN", "KAGGLE_API_TOKEN"):
        secret = os.environ.get(key, "")
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(r"https?://[^\s\"'<>]+", "[URL REDACTED]", message, flags=re.IGNORECASE)
    return message[:500]


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _kernel_slug(job_id: str) -> str:
    return f"karaoke-zapia-{job_id}"


def _kernel_id(job_id: str) -> str:
    return f"{OWNER}/{_kernel_slug(job_id)}"


def _blob_path(job_id: str) -> str:
    return f"karaoke/{job_id}/video.mp4"


def _valid_muka_url(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("Cole um link de compartilhamento do MukaPlay.")
    value = raw.strip()
    if value.lower().startswith("http://"):
        raise ValueError("Use o link HTTPS de compartilhamento do MukaPlay.")
    if not value.lower().startswith("https://"):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"mukaplay.com", "www.mukaplay.com"}:
        raise ValueError("Cole um link de compartilhamento do MukaPlay.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("O link do MukaPlay tem um formato inválido.") from exc
    if parsed.username or parsed.password or port not in (None, 443) or parsed.query or parsed.fragment:
        raise ValueError("O link do MukaPlay tem um formato inválido.")
    if not MUKA_PATH_RE.fullmatch(parsed.path):
        raise ValueError("Esse não parece ser um link de compartilhamento do MukaPlay.")
    return parsed._replace(path=parsed.path.rstrip("/")).geturl()


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    expected = os.environ.get("SITE_ACCESS_PIN", "")
    supplied = handler.headers.get("x-site-pin", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _env_for_kaggle() -> dict[str, str]:
    token = os.environ.get("KAGGLE_API_TOKEN", "")
    username = os.environ.get("KAGGLE_USERNAME", "")
    if not token or not username:
        raise RuntimeError("A integração com o Kaggle ainda não está configurada no servidor.")
    os.environ["KAGGLE_CONFIG_DIR"] = os.path.join(tempfile.gettempdir(), "zapia-kaggle-config")
    env = os.environ.copy()
    env["KAGGLE_API_TOKEN"] = token
    env["KAGGLE_USERNAME"] = username
    return env


def _run_kaggle(args: list[str], *, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from kaggle.cli import main; sys.argv=['kaggle', *sys.argv[1:]]; sys.exit(main())",
            *args,
        ],
        text=True,
        capture_output=True,
        timeout=timeout,
        env=_env_for_kaggle(),
        check=False,
    )


def _patched_notebook(url: str, semitones: int, destination: Path) -> None:
    source_path = Path(__file__).resolve().parents[1] / "KaraokeZapia_GPU_Kaggle.ipynb"
    if not source_path.is_file():
        raise RuntimeError("Não encontrei o notebook de processamento incluído no deploy.")
    notebook = json.loads(source_path.read_text(encoding="utf-8"))
    patched = False
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        text = "".join(source) if isinstance(source, list) else str(source)
        if 'MUKA_URL = ""' not in text or "AUTHORIZED_TO_PROCESS = False" not in text:
            continue
        text = text.replace('MUKA_URL = ""', f"MUKA_URL = {json.dumps(url, ensure_ascii=False)}", 1)
        text = re.sub(r"(?m)^SEMITONES = -?\d+.*$", f"SEMITONES = {semitones} # selecionado no site", text, count=1)
        text = re.sub(
            r"(?m)^AUTHORIZED_TO_PROCESS = (?:True|False).*$",
            "AUTHORIZED_TO_PROCESS = True # autorização confirmada pelo usuário no site",
            text,
            count=1,
        )
        cell["source"] = text.splitlines(keepends=True)
        patched = True
        break
    if not patched:
        raise RuntimeError("Não encontrei no notebook os campos de URL, tom e autorização esperados.")
    destination.write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")


def _start_job(url: str, semitones: int, job_id: str) -> str:
    if not OWNER:
        raise RuntimeError("A conta Kaggle não está configurada no servidor.")
    slug = _kernel_slug(job_id)
    with tempfile.TemporaryDirectory(prefix="zapia-kaggle-") as temp_name:
        stage = Path(temp_name)
        _patched_notebook(url, semitones, stage / "KaraokeZapia_GPU_Kaggle.ipynb")
        metadata = {
            "id": f"{OWNER}/{slug}",
            "title": f"Karaoke Zapia {job_id}",
            "code_file": "KaraokeZapia_GPU_Kaggle.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
        }
        (stage / "kernel-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        result = _run_kaggle(["kernels", "push", "-p", str(stage)], timeout=240)
        if result.returncode != 0:
            raw_detail = (result.stderr or result.stdout or "").strip()
            detail = _safe_diagnostic(raw_detail)
            if any(word in raw_detail.lower() for word in ("auth", "token", "credential")):
                raise RuntimeError(f"Kaggle kernels push returned {result.returncode}: {detail or 'authentication rejected'}")
            raise RuntimeError(f"Kaggle kernels push returned {result.returncode}: {detail or 'empty CLI output'}")
    return slug


def _safe_extract(archive: Path, destination: Path) -> None:
    base = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if target == base or base in target.parents:
                zf.extract(member, destination)


def _upload_video(job_id: str) -> bool:
    from vercel.blob import sync as blob

    pathname = _blob_path(job_id)
    try:
        blob.head_blob(pathname)
        return True
    except blob.BlobNotFoundError:
        pass

    kernel = _kernel_id(job_id)
    with tempfile.TemporaryDirectory(prefix="zapia-kaggle-output-") as temp_name:
        output_dir = Path(temp_name)
        result = _run_kaggle(["kernels", "output", kernel, "-p", str(output_dir), "-o"], timeout=240)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-1200:]
            raise RuntimeError(detail or "O Kaggle terminou, mas não consegui obter o arquivo de saída.")
        extract_dir = output_dir / "unzipped"
        extract_dir.mkdir()
        for archive in output_dir.rglob("*.zip"):
            if extract_dir not in archive.parents:
                try:
                    _safe_extract(archive, extract_dir)
                except zipfile.BadZipFile:
                    continue
        videos = [p for p in output_dir.rglob("*.mp4") if p.is_file()]
        if not videos:
            raise RuntimeError("O processamento terminou, mas não encontrei um MP4 nos arquivos de saída.")
        videos.sort(key=lambda p: ("karaoke" in p.name.lower(), p.stat().st_size), reverse=True)
        video_path = videos[0]
        size = video_path.stat().st_size
        if size <= 0 or size > 95 * 1024 * 1024:
            raise RuntimeError("O MP4 ficou vazio ou passou do limite de 95 MB do player privado.")
        with video_path.open("rb") as video_file:
            uploaded = blob.put_blob(
                pathname,
                video_file,
                content_length=size,
                access="private",
                content_type="video/mp4",
                add_random_suffix=False,
                allow_overwrite=False,
            )
        return bool(uploaded.url)


def _delete_video(job_id: str) -> None:
    from vercel.blob import sync as blob

    try:
        blob.delete_blob(_blob_path(job_id))
    except blob.BlobNotFoundError:
        return


class handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        # Avoid logging request headers, which carry the PIN.
        return

    def _send_json(self, status: int, data: object) -> None:
        body = _json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "GET, POST, DELETE, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        if not _authorized(self):
            self._send_json(401, {"error": "PIN incorreto ou ausente."})
            return
        query = parse_qs(urlparse(self.path).query)
        if query.get("check") == ["1"]:
            self._send_json(200, {"authenticated": True})
            return
        job_id = query.get("job", [""])[0]
        if not JOB_RE.fullmatch(job_id):
            self._send_json(400, {"error": "Identificador de processamento inválido."})
            return
        try:
            status = _run_kaggle(["kernels", "status", _kernel_id(job_id)], timeout=40)
            output = (status.stdout or status.stderr or "").strip()
            if status.returncode != 0:
                low = output.lower()
                if "not found" in low or "does not exist" in low:
                    self._send_json(404, {"error": "Não encontrei esse processamento no Kaggle."})
                else:
                    self._send_json(502, {"error": "Não consegui consultar o status no Kaggle."})
                return
            match = re.search(r"KernelWorkerStatus\.([A-Z_]+)", output)
            state = match.group(1) if match else ""
            if state in {"ERROR", "FAILED", "CANCELLED", "CANCELED"}:
                self._send_json(200, {"state": "failed", "message": "O Kaggle não conseguiu concluir esse processamento."})
                return
            if state in {"COMPLETE", "COMPLETED", "SUCCESS", "SUCCEEDED"}:
                ready = _upload_video(job_id)
                self._send_json(200, {"state": "completed", "media_ready": ready, "message": "Videokê pronto."})
                return
            self._send_json(200, {"state": "running", "message": "Processando no Kaggle com GPU…"})
        except subprocess.TimeoutExpired:
            self._send_json(504, {"error": "A consulta ao Kaggle demorou demais. Tente de novo em alguns segundos."})
        except Exception:
            self._send_json(502, {"error": "Não consegui concluir a consulta ou preparar o MP4 privado."})

    def do_POST(self) -> None:
        if not _authorized(self):
            self._send_json(401, {"error": "PIN incorreto ou ausente."})
            return
        try:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Requisição inválida.") from exc
            if length <= 0 or length > 16_384:
                self._send_json(413 if length > 16_384 else 400, {"error": "Requisição inválida ou muito grande."})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Requisição inválida.")
            action = payload.get("action", "submit")
            if action == "delete":
                job_id = str(payload.get("job", ""))
                if not JOB_RE.fullmatch(job_id):
                    self._send_json(400, {"error": "Identificador inválido."})
                    return
                _delete_video(job_id)
                self._send_json(200, {"deleted": True})
                return
            if payload.get("authorized") is not True:
                self._send_json(403, {"error": "Confirme que tem autorização para salvar e processar esse conteúdo."})
                return
            url = _valid_muka_url(payload.get("muka_url"))
            try:
                raw_semitones = payload.get("semitones", 0)
                if isinstance(raw_semitones, bool):
                    raise ValueError
                semitones = int(raw_semitones)
                if isinstance(raw_semitones, float) and not raw_semitones.is_integer():
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise ValueError("Escolha um tom entre -6 e +6 semitons.") from exc
            if not -6 <= semitones <= 6:
                raise ValueError("Escolha um tom entre -6 e +6 semitons.")
            job_id = uuid.uuid4().hex
            _start_job(url, semitones, job_id)
            self._send_json(202, {"job": job_id, "state": "submitted", "message": "Pedido enviado ao Kaggle."})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": str(exc)})
        except subprocess.TimeoutExpired:
            self._send_json(504, {"error": "O envio ao Kaggle demorou demais. Não consegui confirmar se o processamento foi iniciado."})
        except Exception as exc:
            error_id = uuid.uuid4().hex[:10]
            print(f"[videoke-submit:{error_id}] {type(exc).__name__}: {_safe_diagnostic(exc)}")
            self._send_json(502, {"error": "Não consegui iniciar a solicitação no servidor."})

    def do_DELETE(self) -> None:
        if not _authorized(self):
            self._send_json(401, {"error": "PIN incorreto ou ausente."})
            return
        query = parse_qs(urlparse(self.path).query)
        job_id = query.get("job", [""])[0]
        if not JOB_RE.fullmatch(job_id):
            self._send_json(400, {"error": "Identificador inválido."})
            return
        try:
            _delete_video(job_id)
            self._send_json(200, {"deleted": True})
        except Exception:
            self._send_json(502, {"error": "Não consegui apagar o MP4 do armazenamento privado."})
