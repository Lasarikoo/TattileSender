import os
import sys
import time
import json
import base64
import shutil
import threading
import traceback
import re
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty

import win32event
import win32service
import win32serviceutil
import servicemanager

from fastapi import FastAPI, Request
import uvicorn

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import urllib.request
import urllib.error


# ==========================================================
# CONFIG (EDITA AQUÍ)
# ==========================================================
HOST = "0.0.0.0"
PORT = 5055

INGEST_JSON_DIR = Path(r"C:\ProgramData\LectorVision\Ingest\json")
SENDER_JSON_DIR = Path(r"C:\ProgramData\LectorVision\Sender\json")
SENDER_PENDING_DIR = Path(r"C:\ProgramData\LectorVision\Sender\pending")
SENDER_FAILED_DIR = Path(r"C:\ProgramData\LectorVision\Sender\failed")

LOG_DIR = Path(r"C:\ProgramData\LectorVision\logs")
LOG_BUCKET_MINUTES = 30
LOG_RETENTION_HOURS = 4
LOG_CLEAN_INTERVAL_SEC = 300

SRC_DIR = Path(r"C:\Program Files (x86)\LectorVision\RedLight\PlateImageDir")
CLONED_DIR = Path(r"C:\Program Files (x86)\LectorVision\RedLight\Images")

# ✅ 45 minutos
IMAGE_RETENTION_HOURS = 0.75
IMAGE_CLEAN_INTERVAL_SEC = 600

FAILED_RETENTION_HOURS = 1
FAILED_CLEAN_INTERVAL_SEC = 3600

PENDING_RETENTION_HOURS = 1
PENDING_CLEAN_INTERVAL_SEC = 3600

INGEST_RETENTION_HOURS = 1
INGEST_CLEAN_INTERVAL_SEC = 3600

SCAN_INTERVAL_SEC = 0.5
COPY_MAX_TRIES = 25
COPY_RETRY_DELAY_SEC = 0.04
MIRROR_SUMMARY_EVERY_SEC = 60
LOG_MIRROR_EACH_COPY = False

# ✅ para evitar copiar “renders parciales”
IMAGE_STABLE_SEC = 0.25

PROC_POLL_SEC = 0.5
PROC_STABLE_SEC = 0.6
MAX_JSON_BYTES = 50 * 1024 * 1024
MAX_BODY_BYTES = 20 * 1024 * 1024

OCR_PATH_KEYS = ["OCRImagePath"]
OCR_B64_KEYS = ["ImageOCR", "IMAGE_OCR"]

CROP_PATH_KEYS = ["CROPImagePath", "CropImagePath"]
CROP_B64_KEYS = ["ImageCrop", "IMAGE_CROP"]

CTX_PATH_KEYS = ["ColorImagePath"]
CTX_B64_KEYS = ["ImageCTX", "IMAGE_CTX"]

# (lo dejaste desactivado)
ENABLE_STRICT_FILTERS = False

SEND_ENABLED = True
SEND_URL = "http://217.160.227.164:33335/ingest/lectorvision"
SEND_HEADERS = {"Content-Type": "application/json"}
SEND_TIMEOUT_SEC = 10
SEND_OK_CODES = {200, 201, 202, 204}
SEND_DELETE_ON_SUCCESS = True
SEND_POLL_SEC = 0.6
SEND_BACKOFF_ON_FAIL_SEC = 3.0
SEND_SUMMARY_EVERY_SEC = 60

SEND_FAIL_FAST_4XX = True
SEND_FAIL_FAST_EXCEPT_429 = True
# ==========================================================


try:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
except Exception:
    pass


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _bucket_start(dt: datetime, bucket_minutes: int) -> datetime:
    minute_bucket = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=minute_bucket, second=0, microsecond=0)

def _log_path(category: str, dt: datetime) -> Path:
    cat = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", category.strip().lower() or "general")
    bucket = _bucket_start(dt, LOG_BUCKET_MINUTES)
    fname = bucket.strftime("%Y%m%d_%H%M") + ".log"
    return LOG_DIR / cat / fname

def log(category: str, msg: str) -> None:
    try:
        dt = datetime.now()
        p = _log_path(category, dt)
        ensure_dir(p.parent)
        ts = dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        with open(p, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"{ts} [{category.upper()}] {msg}\n")
    except Exception:
        pass

def cleanup_old_logs():
    try:
        cutoff = time.time() - (LOG_RETENTION_HOURS * 3600)
        deleted = 0
        scanned = 0
        if not LOG_DIR.exists():
            return
        for cat_dir in LOG_DIR.iterdir():
            if not cat_dir.is_dir():
                continue
            for f in cat_dir.iterdir():
                if not f.is_file():
                    continue
                scanned += 1
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink(missing_ok=True)
                        deleted += 1
                except Exception:
                    pass
        if deleted:
            log("cleanup", f"Log cleanup: deleted={deleted} scanned={scanned} retention_hours={LOG_RETENTION_HOURS}")
    except Exception:
        log("cleanup", "Log cleanup error:\n" + traceback.format_exc())


def safe_filename(s: str, maxlen: int = 120) -> str:
    invalid = '<>:"/\\|?*'
    for c in invalid:
        s = s.replace(c, "_")
    s = s.strip()
    return s[:maxlen] if len(s) > maxlen else s

def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    base = path.with_suffix("")
    ext = path.suffix
    for i in range(1, 10000):
        p = Path(f"{base}_{i}{ext}")
        if not p.exists():
            return p
    return Path(f"{base}_{int(time.time()*1000)}{ext}")

def wait_until_stable(path: Path, stable_seconds: float) -> bool:
    try:
        last_size = path.stat().st_size
    except Exception:
        return False
    last_change = time.time()
    while True:
        time.sleep(0.15)
        try:
            new_size = path.stat().st_size
        except Exception:
            return False
        if new_size != last_size:
            last_size = new_size
            last_change = time.time()
        else:
            if time.time() - last_change >= stable_seconds:
                return True

def wait_until_stable_file(path: Path, stable_seconds: float) -> bool:
    # Igual que wait_until_stable, pero con pasos pequeños para imágenes
    try:
        last_size = path.stat().st_size
    except Exception:
        return False
    last_change = time.time()
    while True:
        time.sleep(0.05)
        try:
            new_size = path.stat().st_size
        except Exception:
            return False
        if new_size != last_size:
            last_size = new_size
            last_change = time.time()
        else:
            if time.time() - last_change >= stable_seconds:
                return True

def atomic_write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

def load_json_safe(path: Path) -> object:
    size = path.stat().st_size
    if size > MAX_JSON_BYTES:
        raise ValueError(f"JSON demasiado grande ({size} bytes): {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def is_probably_base64(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    if not s or len(s) < 80:
        return False
    if "\\" in s or "/" in s or ":" in s:
        return False
    if s.startswith("/9j/") or s.startswith("iVBOR") or s.startswith("R0lGOD"):
        return True
    if re.fullmatch(r"[A-Za-z0-9+/=]+", s) and (len(s) % 4 == 0 or len(s) > 500):
        return True
    return False

def basename_from_any_path(s: str) -> str:
    s = s.strip().strip('"').strip("'")
    s = s.replace("/", "\\")
    return s.split("\\")[-1] if "\\" in s else s

def safe_inside_dir(file_path: Path, parent_dir: Path) -> bool:
    try:
        file_path.resolve().relative_to(parent_dir.resolve())
        return True
    except Exception:
        return False

def file_to_base64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode("ascii")

def first_nonempty_str(record: dict, keys: list[str]) -> str | None:
    for k in keys:
        v = record.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def any_base64_present(record: dict, keys: list[str]) -> bool:
    for k in keys:
        v = record.get(k)
        if isinstance(v, str) and is_probably_base64(v):
            return True
    return False

def get_or_create_target_key(record: dict, keys: list[str]) -> str:
    for k in keys:
        if k in record:
            return k
    record[keys[0]] = ""
    return keys[0]

def looks_like_image_ref(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    if not s:
        return False
    name = basename_from_any_path(s)
    low = name.lower()
    return low.endswith(".jpg") or low.endswith(".jpeg") or low.endswith(".png") or low.endswith(".bmp")

def find_in_cloned_dir_by_name(filename: str) -> Path | None:
    direct = CLONED_DIR / filename
    if direct.exists() and direct.is_file():
        return direct
    try:
        for p in CLONED_DIR.rglob(filename):
            if p.is_file():
                return p
    except Exception:
        return None
    return None


# ==========================================================
# ✅ MIRROR FIX: copia SIEMPRE al mismo nombre, y espera estabilidad
# ==========================================================
def copy_image_exact_name(src_path: Path, dst_dir: Path) -> tuple[bool, Path | None, str | None]:
    if not src_path.is_file():
        return (False, None, "missing")
    ensure_dir(dst_dir)

    # Espera a que el archivo termine de escribirse
    if not wait_until_stable_file(src_path, IMAGE_STABLE_SEC):
        return (False, None, "unstable")

    dst_path = dst_dir / src_path.name

    # Si ya existe y coincide tamaño, no copiar
    try:
        if dst_path.exists():
            if dst_path.stat().st_size == src_path.stat().st_size:
                return (True, dst_path, "skip_same")
    except Exception:
        pass

    # Copia segura: tmp + replace
    tmp = dst_path.with_suffix(dst_path.suffix + ".tmp")
    for _ in range(COPY_MAX_TRIES):
        try:
            shutil.copy2(src_path, tmp)
            os.replace(tmp, dst_path)
            return (True, dst_path, None)
        except PermissionError:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            return (False, None, "perm")
        except OSError:
            time.sleep(COPY_RETRY_DELAY_SEC)

    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass
    return (False, None, "other")
# ==========================================================


def image_cleanup_worker(stop_event: threading.Event):
    ensure_dir(CLONED_DIR)
    while not stop_event.is_set():
        try:
            cutoff = time.time() - (IMAGE_RETENTION_HOURS * 3600)
            deleted = 0
            scanned = 0
            for p in CLONED_DIR.iterdir():
                if not p.is_file():
                    continue
                scanned += 1
                try:
                    if p.stat().st_mtime < cutoff:
                        p.unlink(missing_ok=True)
                        deleted += 1
                except Exception:
                    pass
            if deleted:
                log("cleanup", f"Image cleanup: deleted={deleted} scanned={scanned} retention_hours={IMAGE_RETENTION_HOURS}")
        except Exception:
            log("cleanup", "Image cleanup error:\n" + traceback.format_exc())

        cleanup_old_logs()

        for _ in range(int(IMAGE_CLEAN_INTERVAL_SEC * 10)):
            if stop_event.is_set():
                break
            time.sleep(0.1)

def log_cleanup_worker(stop_event: threading.Event):
    while not stop_event.is_set():
        cleanup_old_logs()
        for _ in range(int(LOG_CLEAN_INTERVAL_SEC * 10)):
            if stop_event.is_set():
                break
            time.sleep(0.1)

def cleanup_old_files_in_dir(target_dir: Path, retention_hours: float, label: str) -> None:
    try:
        cutoff = time.time() - (retention_hours * 3600)
        deleted = 0
        scanned = 0
        if not target_dir.exists():
            return
        for f in target_dir.iterdir():
            if not f.is_file():
                continue
            scanned += 1
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
                    deleted += 1
            except Exception:
                pass
        if deleted:
            log("cleanup", f"{label} cleanup: deleted={deleted} scanned={scanned} retention_hours={retention_hours}")
    except Exception:
        log("cleanup", f"{label} cleanup error:\n" + traceback.format_exc())

def dir_cleanup_worker(stop_event: threading.Event, target_dir: Path, retention_hours: float, interval_sec: float, label: str):
    ensure_dir(target_dir)
    while not stop_event.is_set():
        cleanup_old_files_in_dir(target_dir, retention_hours, label)
        for _ in range(int(interval_sec * 10)):
            if stop_event.is_set():
                break
            time.sleep(0.1)


app = FastAPI()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()
    client_host = request.client.host if request.client else "??"
    ct = request.headers.get("content-type")
    log("api", f"[REQ] {request.method} {request.url.path} from={client_host} ct={ct} len={len(body)}")

    async def receive():
        return {"type": "http.request", "body": body}
    request._receive = receive
    return await call_next(request)

@app.get("/health")
def health():
    return {"ok": True}

async def _save_ingest(req: Request) -> dict:
    raw = await req.body()
    if not raw:
        return {"ok": False, "error": "Empty body"}
    if len(raw) > MAX_BODY_BYTES:
        return {"ok": False, "error": f"Body too large ({len(raw)} bytes)"}
    ensure_dir(INGEST_JSON_DIR)

    id_transit = None
    plate = None
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
        if isinstance(payload, dict):
            id_transit = payload.get("IdTransit") or payload.get("idTransit") or payload.get("id")
            plate = payload.get("Plate") or payload.get("plate")
        elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
            id_transit = payload[0].get("IdTransit") or payload[0].get("idTransit") or payload[0].get("id")
            plate = payload[0].get("Plate") or payload[0].get("plate")
    except Exception:
        pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = safe_filename(str(id_transit) if id_transit is not None else "no_id")
    plate_s = safe_filename(str(plate)) if plate else "NO_PLATE"
    out = unique_path(INGEST_JSON_DIR / f"{name}_{plate_s}_{ts}.json")
    out.write_bytes(raw)
    return {"ok": True, "saved": str(out)}

@app.post("/ingest/v2/detection/")
async def ingest_v2(req: Request):
    return await _save_ingest(req)

@app.post("/ingest/{path:path}")
async def ingest_any(req: Request, path: str):
    return await _save_ingest(req)

@app.post("/ingest")
async def ingest(req: Request):
    return await _save_ingest(req)

@app.post("/ingest/")
async def ingest_slash(req: Request):
    return await _save_ingest(req)

@app.post("/")
async def ingest_root(req: Request):
    return await _save_ingest(req)

def run_api(stop_event: threading.Event):
    try:
        log("api", f"Starting uvicorn on {HOST}:{PORT}")
        config = uvicorn.Config(
            app=app,
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        server = uvicorn.Server(config)

        def _run():
            try:
                server.run()
            except Exception:
                log("api", "Uvicorn crashed:\n" + traceback.format_exc())

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        while not stop_event.is_set():
            time.sleep(0.2)

        log("api", "Stopping uvicorn...")
        server.should_exit = True
        t.join(timeout=5)
        log("api", "Stopped")
    except Exception:
        log("api", "FATAL:\n" + traceback.format_exc())


class MirrorHandler(FileSystemEventHandler):
    def __init__(self, q: Queue):
        self.q = q
    def on_created(self, event):
        if not event.is_directory:
            self.q.put(event.src_path)
    def on_moved(self, event):
        if not event.is_directory:
            self.q.put(event.dest_path)
    # ✅ NO on_modified: era el motivo de 10-30 eventos extra por archivo


def mirror_worker(stop_event: threading.Event):
    ensure_dir(CLONED_DIR)
    q: Queue[str] = Queue()

    observer = Observer()
    handler = MirrorHandler(q)

    if SRC_DIR.is_dir():
        observer.schedule(handler, str(SRC_DIR), recursive=False)
        observer.start()
        log("mirror", f"Watching {SRC_DIR} -> {CLONED_DIR}")
    else:
        log("mirror", f"[WARN] Source dir not found at start: {SRC_DIR}")

    copied = 0
    skipped = 0
    failed_perm = 0
    failed_other = 0
    last_summary = time.time()

    # Debounce por nombre (evita copiar 20 veces en 1 segundo)
    last_attempt: dict[str, float] = {}

    try:
        while not stop_event.is_set():
            # Procesa cola de eventos
            try:
                for _ in range(400):
                    src = q.get_nowait()
                    src_p = Path(src)
                    name = src_p.name.lower()
                    now = time.time()
                    if now - last_attempt.get(name, 0.0) < 0.25:
                        continue
                    last_attempt[name] = now

                    ok, dst, err = copy_image_exact_name(src_p, CLONED_DIR)
                    if ok:
                        if err == "skip_same":
                            skipped += 1
                        else:
                            copied += 1
                            if LOG_MIRROR_EACH_COPY:
                                log("mirror", f"Copied {src_p.name} -> {dst}")
                    else:
                        if err == "perm":
                            failed_perm += 1
                        elif err not in (None, "missing", "unstable"):
                            failed_other += 1
            except Empty:
                pass

            # Escaneo: copia solo si falta el nombre exacto o si está “incompleto”
            if SRC_DIR.is_dir():
                try:
                    for src_p in SRC_DIR.iterdir():
                        if not src_p.is_file():
                            continue
                        dst = CLONED_DIR / src_p.name
                        try:
                            if dst.exists() and dst.stat().st_size == src_p.stat().st_size:
                                continue
                        except Exception:
                            pass

                        name = src_p.name.lower()
                        now = time.time()
                        if now - last_attempt.get(name, 0.0) < 0.25:
                            continue
                        last_attempt[name] = now

                        ok, _, err = copy_image_exact_name(src_p, CLONED_DIR)
                        if ok:
                            if err == "skip_same":
                                skipped += 1
                            else:
                                copied += 1
                        else:
                            if err == "perm":
                                failed_perm += 1
                            elif err not in (None, "missing", "unstable"):
                                failed_other += 1
                except Exception:
                    failed_other += 1

            now = time.time()
            if now - last_summary >= MIRROR_SUMMARY_EVERY_SEC:
                if copied or skipped or failed_perm or failed_other:
                    log("mirror", f"Summary {MIRROR_SUMMARY_EVERY_SEC}s: copied={copied} skipped={skipped} perm_fail={failed_perm} other_fail={failed_other}")
                copied = 0
                skipped = 0
                failed_perm = 0
                failed_other = 0
                last_summary = now

            time.sleep(SCAN_INTERVAL_SEC)

    finally:
        try:
            observer.stop()
            observer.join(timeout=5)
        except Exception:
            pass


def resolve_image_from_path_value(path_value: str) -> Path | None:
    if not isinstance(path_value, str):
        return None
    pv = path_value.strip().strip('"').strip("'")
    if not pv:
        return None
    if not looks_like_image_ref(pv):
        return None
    filename = basename_from_any_path(pv)
    if not filename:
        return None
    p = find_in_cloned_dir_by_name(filename)
    if p and p.exists():
        return p
    try:
        abs_p = Path(pv)
        if abs_p.exists() and abs_p.is_file():
            return abs_p
    except Exception:
        pass
    return None

def fill_b64_from_path_if_missing(record: dict, path_keys: list[str], target_keys: list[str]) -> list[Path]:
    used_images: list[Path] = []
    path_val = first_nonempty_str(record, path_keys)
    if not path_val:
        return used_images
    if any_base64_present(record, target_keys):
        return used_images
    img_path = resolve_image_from_path_value(path_val)
    if not img_path:
        return used_images
    target_key = get_or_create_target_key(record, target_keys)
    try:
        record[target_key] = file_to_base64(img_path)
        if safe_inside_dir(img_path, CLONED_DIR):
            used_images.append(img_path)
    except Exception:
        return used_images
    return used_images

def record_is_valid_strict(record: dict) -> bool:
    has_ocr_path = bool(first_nonempty_str(record, OCR_PATH_KEYS))
    has_ctx_path = bool(first_nonempty_str(record, CTX_PATH_KEYS))
    has_ocr_b64 = any_base64_present(record, OCR_B64_KEYS)
    has_ctx_b64 = any_base64_present(record, CTX_B64_KEYS)
    paths_ok = has_ocr_path and has_ctx_path
    paths_half = has_ocr_path != has_ctx_path
    b64_ok = has_ocr_b64 and has_ctx_b64
    b64_half = has_ocr_b64 != has_ctx_b64
    if paths_half or b64_half:
        return False
    return paths_ok or b64_ok

def ensure_final_has_both_b64(record: dict) -> bool:
    ocr_ok = any_base64_present(record, OCR_B64_KEYS)
    ctx_ok = any_base64_present(record, CTX_B64_KEYS)
    return ocr_ok and ctx_ok

def process_one_record(record: dict) -> tuple[dict, list[Path], str]:
    if ENABLE_STRICT_FILTERS:
        if not record_is_valid_strict(record):
            return record, [], "strict_pair_invalid"
    used: list[Path] = []
    used += fill_b64_from_path_if_missing(record, OCR_PATH_KEYS, OCR_B64_KEYS)
    used += fill_b64_from_path_if_missing(record, CTX_PATH_KEYS, CTX_B64_KEYS)
    used += fill_b64_from_path_if_missing(record, CROP_PATH_KEYS, CROP_B64_KEYS)
    if ENABLE_STRICT_FILTERS:
        if not ensure_final_has_both_b64(record):
            return record, used, "missing_final_b64"
    return record, used, "ok"

def process_payload(payload: object) -> tuple[object | None, list[Path], str]:
    used: list[Path] = []
    if isinstance(payload, dict):
        rec, imgs, why = process_one_record(payload)
        used += imgs
        return rec, used, why
    if isinstance(payload, list):
        out_list = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            rec, imgs, why = process_one_record(item)
            used += imgs
            out_list.append(rec)
        if not out_list:
            return None, used, "no_dict_items"
        return out_list, used, "ok_list"
    return None, used, "payload_not_dict_or_list"

def process_one_ingest_file(path: Path):
    if not wait_until_stable(path, PROC_STABLE_SEC):
        return
    try:
        payload = load_json_safe(path)
    except Exception as e:
        log("proc", f"[WARN] Cannot load {path.name}: {type(e).__name__}: {e}")
        return

    processed, used_imgs, why = process_payload(payload)
    if processed is None:
        try:
            path.unlink(missing_ok=True)
        except Exception as e:
            log("proc", f"[WARN] Cannot delete ingest json {path.name}: {type(e).__name__}: {e}")
        log("proc", f"DROPPED {path.name} ({why})")
        return

    ensure_dir(SENDER_JSON_DIR)
    out_path = unique_path(SENDER_JSON_DIR / path.name)

    try:
        atomic_write_json(out_path, processed)
    except Exception as e:
        log("proc", f"[ERROR] Cannot write sender {out_path.name}: {type(e).__name__}: {e}")
        return

    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        log("proc", f"[WARN] Cannot delete ingest json {path.name}: {type(e).__name__}: {e}")

    deleted = 0
    for img in set(used_imgs):
        try:
            if img.exists() and safe_inside_dir(img, CLONED_DIR):
                img.unlink()
                deleted += 1
        except Exception:
            pass

    log("proc", f"{path.name} -> {out_path.name} (deleted_images={deleted}, strict={ENABLE_STRICT_FILTERS}, reason={why})")

def processor_worker(stop_event: threading.Event):
    ensure_dir(INGEST_JSON_DIR)
    ensure_dir(SENDER_JSON_DIR)
    log("proc", f"Watching {INGEST_JSON_DIR} -> {SENDER_JSON_DIR}")
    while not stop_event.is_set():
        try:
            files = [p for p in INGEST_JSON_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
            if files:
                files.sort(key=lambda p: p.stat().st_mtime)
                process_one_ingest_file(files[0])
        except Exception:
            log("proc", "ERR:\n" + traceback.format_exc())
        time.sleep(PROC_POLL_SEC)


def http_post_json(url: str, payload: object, headers: dict[str, str], timeout_sec: float) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            status = getattr(resp, "status", resp.getcode())
            body = resp.read(300).decode("utf-8", errors="replace")
            return status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read(300).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"

def payload_to_sendable_dicts(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []

def sender_send_items(url: str, items: list[dict]) -> tuple[bool, str, int]:
    if not items:
        return False, "no_dict_items_to_send", 0
    if len(items) == 1:
        status, body = http_post_json(url, items[0], SEND_HEADERS, SEND_TIMEOUT_SEC)
        if status in SEND_OK_CODES:
            return True, f"status={status}", status
        return False, f"status={status} body={body}", status
    last_status = 0
    for idx, item in enumerate(items, start=1):
        status, body = http_post_json(url, item, SEND_HEADERS, SEND_TIMEOUT_SEC)
        last_status = status
        if status in SEND_OK_CODES:
            continue
        return False, f"item_failed idx={idx}/{len(items)} status={status} body={body}", status
    return True, f"split_ok sent={len(items)}", last_status

def is_permanent_client_error(status: int) -> bool:
    if status <= 0:
        return False
    if 400 <= status <= 499:
        if SEND_FAIL_FAST_EXCEPT_429 and status == 429:
            return False
        return True
    return False

def sender_worker(stop_event: threading.Event):
    ensure_dir(SENDER_JSON_DIR)
    ensure_dir(SENDER_PENDING_DIR)
    ensure_dir(SENDER_FAILED_DIR)

    if not SEND_ENABLED:
        log("send", "Disabled (SEND_ENABLED=False)")
        return
    if not SEND_URL:
        log("send", "[WARN] SEND_URL empty. Sender will do nothing.")
        return

    log("send", f"Target URL: {SEND_URL} ok_codes={sorted(SEND_OK_CODES)} timeout={SEND_TIMEOUT_SEC}s delete_on_success={SEND_DELETE_ON_SUCCESS} fail_fast_4xx={SEND_FAIL_FAST_4XX}")

    ok_count = 0
    fail_count = 0
    moved_failed = 0
    last_summary = time.time()

    while not stop_event.is_set():
        try:
            files = [p for p in SENDER_JSON_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
            if files:
                files.sort(key=lambda p: p.stat().st_mtime)
                src = files[0]

                pending = unique_path(SENDER_PENDING_DIR / src.name)
                try:
                    shutil.move(str(src), str(pending))
                except Exception as e:
                    log("send", f"[WARN] Cannot move to pending {src.name}: {type(e).__name__}: {e}")
                    time.sleep(SEND_BACKOFF_ON_FAIL_SEC)
                    continue

                if not wait_until_stable(pending, 0.3):
                    try:
                        shutil.move(str(pending), str(unique_path(SENDER_JSON_DIR / pending.name)))
                    except Exception:
                        pass
                    continue

                try:
                    payload = load_json_safe(pending)
                except Exception as e:
                    log("send", f"[WARN] Cannot load {pending.name}: {type(e).__name__}: {e} -> moving to failed")
                    try:
                        shutil.move(str(pending), str(unique_path(SENDER_FAILED_DIR / pending.name)))
                        moved_failed += 1
                    except Exception:
                        pass
                    continue

                items = payload_to_sendable_dicts(payload)
                if not items:
                    log("send", f"[WARN] {pending.name} payload not dict/list-of-dict -> moving to failed")
                    try:
                        shutil.move(str(pending), str(unique_path(SENDER_FAILED_DIR / pending.name)))
                        moved_failed += 1
                    except Exception:
                        pass
                    continue

                ok, info, status = sender_send_items(SEND_URL, items)

                if ok:
                    ok_count += 1
                    if SEND_DELETE_ON_SUCCESS:
                        try:
                            pending.unlink(missing_ok=True)
                        except Exception as e:
                            log("send", f"[WARN] Cannot delete {pending.name}: {type(e).__name__}: {e}")
                    else:
                        try:
                            shutil.move(str(pending), str(unique_path(SENDER_JSON_DIR / pending.name)))
                        except Exception:
                            pass
                    log("send", f"OK {pending.name} ({info}, deleted={SEND_DELETE_ON_SUCCESS}, items={len(items)})")
                else:
                    if SEND_FAIL_FAST_4XX and is_permanent_client_error(status):
                        moved_failed += 1
                        log("send", f"[WARN] {pending.name} -> {info} (PERMANENT {status}) -> MOVED_TO_FAILED")
                        try:
                            shutil.move(str(pending), str(unique_path(SENDER_FAILED_DIR / pending.name)))
                        except Exception as e:
                            log("send", f"[WARN] Cannot move to failed {pending.name}: {type(e).__name__}: {e}")
                            try:
                                shutil.move(str(pending), str(unique_path(SENDER_JSON_DIR / pending.name)))
                            except Exception:
                                pass
                        time.sleep(0.05)
                    else:
                        fail_count += 1
                        log("send", f"[WARN] {pending.name} -> {info} (items={len(items)})")
                        try:
                            shutil.move(str(pending), str(unique_path(SENDER_JSON_DIR / pending.name)))
                        except Exception:
                            pass
                        time.sleep(SEND_BACKOFF_ON_FAIL_SEC)

            now = time.time()
            if now - last_summary >= SEND_SUMMARY_EVERY_SEC:
                qn = len([p for p in SENDER_JSON_DIR.iterdir() if p.is_file()])
                pn = len([p for p in SENDER_PENDING_DIR.iterdir() if p.is_file()])
                fn = len([p for p in SENDER_FAILED_DIR.iterdir() if p.is_file()])
                if ok_count or fail_count or moved_failed:
                    log("send", f"Summary {int(SEND_SUMMARY_EVERY_SEC)}s: ok={ok_count} fail={fail_count} moved_failed={moved_failed} queue={qn} pending={pn} failed={fn}")
                ok_count = 0
                fail_count = 0
                moved_failed = 0
                last_summary = now

        except Exception:
            log("send", "ERR:\n" + traceback.format_exc())
            time.sleep(SEND_BACKOFF_ON_FAIL_SEC)

        time.sleep(SEND_POLL_SEC)


class LectorVisionService(win32serviceutil.ServiceFramework):
    _svc_name_ = "LectorVisionIngest"
    _svc_display_name_ = "LectorVision Ingest + Mirror + Processor + Sender"
    _svc_description_ = "Local ingest + clone images + optional strict filters + send JSONs + cleanup/rotation."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        log("service", "Stop requested")
        self.stop_event.set()
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        try:
            servicemanager.LogInfoMsg("LectorVision service starting...")
            log("service", f"Starting... (strict_filters={ENABLE_STRICT_FILTERS})")

            ensure_dir(INGEST_JSON_DIR)
            ensure_dir(SENDER_JSON_DIR)
            ensure_dir(SENDER_PENDING_DIR)
            ensure_dir(SENDER_FAILED_DIR)
            ensure_dir(CLONED_DIR)
            ensure_dir(LOG_DIR)

            t_api = threading.Thread(target=run_api, args=(self.stop_event,), daemon=True)
            t_mirror = threading.Thread(target=mirror_worker, args=(self.stop_event,), daemon=True)
            t_proc = threading.Thread(target=processor_worker, args=(self.stop_event,), daemon=True)
            t_send = threading.Thread(target=sender_worker, args=(self.stop_event,), daemon=True)

            t_img_clean = threading.Thread(target=image_cleanup_worker, args=(self.stop_event,), daemon=True)
            t_log_clean = threading.Thread(target=log_cleanup_worker, args=(self.stop_event,), daemon=True)
            t_failed_clean = threading.Thread(
                target=dir_cleanup_worker,
                args=(self.stop_event, SENDER_FAILED_DIR, FAILED_RETENTION_HOURS, FAILED_CLEAN_INTERVAL_SEC, "failed"),
                daemon=True,
            )
            t_pending_clean = threading.Thread(
                target=dir_cleanup_worker,
                args=(self.stop_event, SENDER_PENDING_DIR, PENDING_RETENTION_HOURS, PENDING_CLEAN_INTERVAL_SEC, "pending"),
                daemon=True,
            )
            t_ingest_clean = threading.Thread(
                target=dir_cleanup_worker,
                args=(self.stop_event, INGEST_JSON_DIR, INGEST_RETENTION_HOURS, INGEST_CLEAN_INTERVAL_SEC, "ingest"),
                daemon=True,
            )

            self.threads = [
                t_api,
                t_mirror,
                t_proc,
                t_send,
                t_img_clean,
                t_log_clean,
                t_failed_clean,
                t_pending_clean,
                t_ingest_clean,
            ]
            for t in self.threads:
                t.start()

            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

            for t in self.threads:
                t.join(timeout=5)

            log("service", "Stopped")
            servicemanager.LogInfoMsg("LectorVision service stopped.")
        except Exception:
            log("service", "FATAL:\n" + traceback.format_exc())


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(LectorVisionService)
