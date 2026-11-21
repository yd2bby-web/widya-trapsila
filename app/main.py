import os
import logging
import secrets
import string
import re
import mimetypes
import uuid
from datetime import datetime
from urllib.parse import quote
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from openpyxl import load_workbook
from sqlalchemy import select, or_, text
from sqlalchemy.orm import Session
from jwt import InvalidTokenError
from .database import Base, engine, get_db, SessionLocal
from .models import Student, User, Officer, Program, DownloadFile, ChatMessage, CounselingMessage
from .schemas import LoginInput, UserOut, OfficerInput, ProgramInput
from .security import create_access_token, decode_access_token, hash_password, verify_password

logger = logging.getLogger("widya_trapsila.storage")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_FILE = BASE_DIR / "student_template.xlsx"
Base.metadata.create_all(bind=engine)

# Additive migration for existing SQLite/Neon databases.
from sqlalchemy import inspect, text
with engine.begin() as conn:
    columns = {col["name"] for col in inspect(engine).get_columns("users")}
    if "password_change_required" not in columns:
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE users ADD COLUMN password_change_required BOOLEAN NOT NULL DEFAULT FALSE"))
        else:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_change_required BOOLEAN NOT NULL DEFAULT 0"))
    officer_columns = {col["name"] for col in inspect(engine).get_columns("officers")}
    if "duties" not in officer_columns:
        conn.execute(text("ALTER TABLE officers ADD COLUMN duties TEXT"))
    if "photo_data" not in officer_columns:
        conn.execute(text("ALTER TABLE officers ADD COLUMN photo_data TEXT"))

# Additive counseling assignment migration. Existing students remain unassigned until admin assigns a counselor.
with engine.begin() as conn:
    student_cols = {col["name"] for col in inspect(engine).get_columns("students")}
    if "counselor_user_id" not in student_cols:
        conn.execute(text("ALTER TABLE students ADD COLUMN counselor_user_id INTEGER REFERENCES users(id)" if engine.dialect.name == "postgresql" else "ALTER TABLE students ADD COLUMN counselor_user_id INTEGER REFERENCES users(id)"))

app = FastAPI(title="WIDYA TRAPSILA | PIK-R SMP Negeri 1 Wonogiri", version="0.8.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
bearer = HTTPBearer(auto_error=False)

@app.on_event("startup")
def create_bootstrap_admin():
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not password:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD wajib dikonfigurasi")
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.username == username)):
            db.add(User(username=username, full_name="Administrator WIDYA TRAPSILA", password_hash=hash_password(password), role="super_admin"))
            db.commit()
        chair = db.scalar(select(Officer).where(
            Officer.position == "Ketua PIK-R",
            Officer.full_name == "KHANSA PUTRI"
        ))
        if not chair:
            db.add(Officer(
                position="Ketua PIK-R",
                full_name="KHANSA PUTRI",
                class_name="8C",
                period="Belum ditetapkan",
                duties="Memimpin organisasi PIK-R WIDYA TRAPSILA dan mengoordinasikan pelaksanaan program kerja.",
                photo_data="/static/media/khansa_putri.jpeg",
                sort_order=1,
                is_active=True
            ))
            db.commit()
    finally:
        db.close()

@app.post("/api/admin/counselors")
def create_counselor(payload: dict, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    full_name = str(payload.get("full_name", "")).strip()
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not full_name or not username or len(password) < 10:
        raise HTTPException(status_code=400, detail="Nama, username, dan password minimal 10 karakter wajib diisi.")
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Username sudah digunakan.")
    counselor = User(username=username, full_name=full_name, password_hash=hash_password(password), role="counselor", is_active=True, password_change_required=True)
    db.add(counselor); db.commit(); db.refresh(counselor)
    return {"id": counselor.id, "username": counselor.username, "full_name": counselor.full_name, "message": "Akun konselor berhasil dibuat."}

@app.get("/api/admin/counselors")
def list_counselors(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(User.role == "counselor", User.is_active.is_(True)).order_by(User.full_name)).all()
    return [{"id": c.id, "username": c.username, "full_name": c.full_name, "assigned_students": db.query(Student).filter(Student.counselor_user_id == c.id).count()} for c in rows]

@app.post("/api/admin/counselors/assign")
def assign_counselor(payload: dict, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    student = db.get(Student, int(payload.get("student_id", 0)))
    counselor = db.get(User, int(payload.get("counselor_user_id", 0)))
    if not student or not student.is_active: raise HTTPException(status_code=404, detail="Siswa tidak ditemukan atau tidak aktif.")
    if not counselor or counselor.role != "counselor" or not counselor.is_active: raise HTTPException(status_code=404, detail="Akun konselor tidak ditemukan atau tidak aktif.")
    student.counselor_user_id = counselor.id; db.commit()
    return {"message": f"Konselor {counselor.full_name} ditugaskan kepada {student.full_name}."}

@app.get("/api/counseling/me")
def counseling_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "student" or not user.student_id: raise HTTPException(status_code=403, detail="Akses khusus siswa.")
    student = db.get(Student, user.student_id)
    if not student or not student.counselor_user_id: raise HTTPException(status_code=404, detail="Belum ada konselor yang ditugaskan. Hubungi administrator.")
    counselor = db.get(User, student.counselor_user_id)
    if not counselor or not counselor.is_active: raise HTTPException(status_code=404, detail="Konselor belum tersedia.")
    return {"student_id": student.id, "counselor_name": counselor.full_name}

@app.get("/api/counseling/students")
def counselor_students(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "counselor": raise HTTPException(status_code=403, detail="Akses khusus konselor.")
    rows = db.scalars(select(Student).where(Student.counselor_user_id == user.id, Student.is_active.is_(True)).order_by(Student.class_name, Student.full_name)).all()
    return [{"id": s.id, "name": s.full_name, "class_name": s.class_name, "nis": s.nis} for s in rows]

def _counseling_access(student_id: int, user: User, db: Session):
    student = db.get(Student, student_id)
    if not student or not student.is_active: raise HTTPException(status_code=404, detail="Siswa tidak ditemukan.")
    if user.role == "student" and user.student_id == student.id and student.counselor_user_id:
        counselor_id = student.counselor_user_id
    elif user.role == "counselor" and student.counselor_user_id == user.id:
        counselor_id = user.id
    else:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke percakapan konseling ini.")
    return student, counselor_id

@app.get("/api/counseling/{student_id}/messages")
def counseling_messages(student_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    student, counselor_id = _counseling_access(student_id, user, db)
    rows = db.scalars(select(CounselingMessage).where(CounselingMessage.student_id == student.id, CounselingMessage.counselor_user_id == counselor_id).order_by(CounselingMessage.id).limit(200)).all()
    return [{"id": m.id, "sender": "Saya" if m.sender_user_id == user.id else (db.get(User, counselor_id).full_name if user.role == "student" else student.full_name), "message": m.message, "created_at": m.created_at.isoformat() if m.created_at else None, "mine": m.sender_user_id == user.id} for m in rows]

@app.post("/api/counseling/{student_id}/messages")
def send_counseling_message(student_id: int, payload: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    student, counselor_id = _counseling_access(student_id, user, db)
    message = str(payload.get("message", "")).strip()
    if not message: raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    if len(message) > 2000: raise HTTPException(status_code=400, detail="Pesan maksimal 2.000 karakter.")
    row = CounselingMessage(student_id=student.id, counselor_user_id=counselor_id, sender_user_id=user.id, message=message)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "message": "Pesan konseling terkirim."}

@app.get("/api/health")
def health():
    return {"status":"ok", "app":"WIDYA TRAPSILA | PIK-R SMP Negeri 1 Wonogiri", "version":"0.7.2"}


@app.post("/api/auth/login")
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))


    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username atau password tidak sesuai")

    return {
        "access_token": create_access_token(str(user.id), user.role),
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
        "password_change_required": user.password_change_required
    }


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials: raise HTTPException(status_code=401, detail="Silakan login")
    try:
        data = decode_access_token(credentials.credentials); user_id = int(data["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Sesi login tidak valid atau kedaluwarsa")
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="Akun tidak aktif")
    return user

def require_admin(user: User = Depends(current_user)) -> User:
    if user.role not in {"super_admin", "admin"}: raise HTTPException(status_code=403, detail="Akses khusus administrator")
    return user

@app.get("/api/chat/messages")
def list_chat_messages(before_id: int | None = Query(default=None, ge=1),
                       limit: int = Query(default=100, ge=1, le=100),
                       user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(ChatMessage).order_by(ChatMessage.id.desc()).limit(limit)
    if before_id:
        stmt = stmt.where(ChatMessage.id < before_id)
    rows = list(db.scalars(stmt).all())
    rows.reverse()
    return [{"id": m.id, "sender_name": m.sender_name, "sender_class": m.sender_class,
             "sender_role": m.sender_role, "message": m.message,
             "created_at": m.created_at.isoformat() if m.created_at else None,
             "mine": m.user_id == user.id} for m in rows]

@app.post("/api/chat/messages")
def send_chat_message(payload: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    if len(message) > 1000:
        raise HTTPException(status_code=400, detail="Pesan maksimal 1.000 karakter.")
    student = user.student
    sender_name = student.full_name if student else user.full_name
    sender_class = student.class_name if student else None
    row = ChatMessage(user_id=user.id, sender_name=sender_name, sender_class=sender_class,
                      sender_role=user.role, message=message, created_at=datetime.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "sender_name": row.sender_name, "sender_class": row.sender_class,
            "sender_role": row.sender_role, "message": row.message,
            "created_at": row.created_at.isoformat(), "mine": True}

@app.delete("/api/admin/chat/messages/{message_id}")
def delete_chat_message(message_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(ChatMessage, message_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pesan tidak ditemukan.")
    db.delete(row)
    db.commit()
    return {"message": "Pesan berhasil dihapus."}

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)): return UserOut.model_validate(user)


@app.post("/api/auth/change-password")
def change_password(payload: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    old_password = str(payload.get("old_password", ""))
    new_password = str(payload.get("new_password", ""))
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password lama tidak sesuai")
    if len(new_password) < 10:
        raise HTTPException(status_code=400, detail="Password baru minimal 10 karakter")
    if new_password == old_password:
        raise HTTPException(status_code=400, detail="Password baru harus berbeda")
    user.password_hash = hash_password(new_password)
    user.password_change_required = False
    db.commit()
    return {"message": "Password berhasil diperbarui"}


@app.get("/api/admin/student-accounts")
def list_student_accounts(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Student, User)
        .outerjoin(User, User.student_id == Student.id)
        .where(Student.is_active.is_(True))
        .order_by(Student.class_name, Student.full_name)
    ).all()
    return [{
        "student_id": student.id,
        "nis": student.nis,
        "full_name": student.full_name,
        "class_name": student.class_name,
        "has_account": account is not None,
        "account_active": account.is_active if account else False,
        "password_change_required": account.password_change_required if account else None
    } for student, account in rows]


@app.post("/api/admin/student-accounts/create")
def create_student_accounts(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    alphabet = string.ascii_letters + string.digits
    students = db.scalars(
        select(Student)
        .where(Student.is_active.is_(True))
        .order_by(Student.class_name, Student.full_name)
    ).all()
    created = []
    for student in students:
        existing = db.scalar(select(User).where(
            or_(User.student_id == student.id, User.username == student.nis)
        ))
        if existing:
            continue
        # Random one-time initial password; never use NIS as password.
        initial_password = ''.join(secrets.choice(alphabet) for _ in range(14))
        account = User(
            username=student.nis,
            full_name=student.full_name,
            password_hash=hash_password(initial_password),
            role="student",
            is_active=True,
            student_id=student.id,
            password_change_required=True
        )
        db.add(account)
        created.append({
            "nis": student.nis,
            "nama": student.full_name,
            "kelas": student.class_name,
            "password_awal": initial_password
        })
    db.commit()
    return {
        "dibuat": len(created),
        "dilewati": len(students) - len(created),
        "akun": created,
        "catatan": "Simpan/unduh daftar ini sekarang. Password awal hanya ditampilkan satu kali."
    }


@app.get("/api/student/me")
def student_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "student" or not user.student_id:
        raise HTTPException(status_code=403, detail="Akses khusus akun siswa")
    student = db.get(Student, user.student_id)
    if not student or not student.is_active:
        raise HTTPException(status_code=403, detail="Data siswa tidak aktif")
    return {
        "nis": student.nis,
        "nama": student.full_name,
        "kelas": student.class_name,
        "password_change_required": user.password_change_required
    }

@app.get("/api/admin/students/template")
@app.get("/api/students/template")
def student_template(user: User = Depends(require_admin)):
    if not TEMPLATE_FILE.exists(): raise HTTPException(status_code=404, detail="Template Excel tidak ditemukan")
    return FileResponse(str(TEMPLATE_FILE), filename="Template_Data_Siswa_Widya_Trapsila.xlsx")

@app.post("/api/admin/students/import")
async def import_students(file: UploadFile = File(...), user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".xlsx"): raise HTTPException(status_code=400, detail="Gunakan file Excel .xlsx")
    content = await file.read()
    if len(content) > 5*1024*1024: raise HTTPException(status_code=400, detail="Ukuran file maksimal 5 MB")
    try:
        wb=load_workbook(BytesIO(content), read_only=True, data_only=True); rows=list(wb.active.iter_rows(values_only=True)); wb.close()
    except Exception: raise HTTPException(status_code=400, detail="File Excel tidak dapat dibaca")
    if not rows or [str(x).strip().lower() for x in rows[0][:3]] != ["nis","nama siswa","kelas"]:
        raise HTTPException(status_code=400, detail="Header wajib: NIS | Nama Siswa | Kelas")
    inserted=skipped=0; errors=[]; seen=set()
    for line,row in enumerate(rows[1:], start=2):
        if not row or not any(v is not None and str(v).strip() for v in row[:4]): continue
        nis=str(row[0]).strip() if row[0] is not None else ""
        name=str(row[1]).strip() if len(row)>1 and row[1] is not None else ""
        cls=str(row[2]).strip() if len(row)>2 and row[2] is not None else ""
        nisn=str(row[3]).strip() if len(row)>3 and row[3] is not None else None
        if nis.lower() in {"isi_nis","contoh","example"} or name.lower() in {"isi_nama_lengkap","nama contoh","contoh nama"} or cls.lower().startswith("contoh"):
            skipped += 1; continue
        if not nis or not name or not cls: errors.append({"baris":line,"pesan":"NIS, Nama Siswa, dan Kelas wajib diisi"}); continue
        if nis in seen: errors.append({"baris":line,"pesan":"NIS duplikat dalam file"}); continue
        seen.add(nis)
        if db.scalar(select(Student).where(Student.nis==nis)): skipped+=1; continue
        db.add(Student(nis=nis,nisn=nisn,full_name=name,class_name=cls)); inserted+=1
    db.commit()
    return {"berhasil_ditambahkan":inserted,"dilewati_karena_sudah_ada_atau_contoh":skipped,"kesalahan":errors}

@app.get("/api/admin/students")
def list_students(q: str=Query(default="",max_length=100), class_name: str=Query(default="",max_length=30), limit: int=Query(default=100,ge=1,le=500), offset: int=Query(default=0,ge=0), user: User=Depends(require_admin), db: Session=Depends(get_db)):
    stmt=select(Student).where(Student.is_active.is_(True))
    if q.strip():
        term=f"%{q.strip()}%"; stmt=stmt.where(or_(Student.nis.ilike(term),Student.full_name.ilike(term)))
    if class_name.strip(): stmt=stmt.where(Student.class_name==class_name.strip())
    total=db.query(Student).filter(Student.is_active.is_(True)).count()
    items=db.scalars(stmt.order_by(Student.class_name,Student.full_name).offset(offset).limit(limit)).all()
    return {"total":total,"ditampilkan":len(items),"data":[{"nis":s.nis,"nama":s.full_name,"kelas":s.class_name,"nisn":s.nisn} for s in items]}

@app.get("/api/admin/students/count")
def student_count(user: User=Depends(require_admin), db: Session=Depends(get_db)):
    return {"total_siswa":db.query(Student).filter(Student.is_active.is_(True)).count()}

@app.get("/api/public/officers")
def public_officers(db: Session = Depends(get_db)):
    rows = db.scalars(select(Officer).where(Officer.is_active.is_(True)).order_by(Officer.sort_order, Officer.id)).all()
    return [{"id": x.id, "position": x.position, "full_name": x.full_name,
             "class_name": x.class_name, "period": x.period,
             "duties": x.duties, "photo_data": x.photo_data} for x in rows]


@app.get("/api/admin/officers")
def list_officers(user: User=Depends(require_admin), db: Session=Depends(get_db)):
    rows=db.scalars(select(Officer).where(Officer.is_active.is_(True)).order_by(Officer.sort_order,Officer.id)).all()
    return [{"id":x.id,"position":x.position,"full_name":x.full_name,"class_name":x.class_name,"period":x.period,"duties":x.duties,"photo_data":x.photo_data} for x in rows]

@app.post("/api/admin/officers")
def add_officer(payload: OfficerInput, user: User=Depends(require_admin), db: Session=Depends(get_db)):
    item=Officer(**payload.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return {"id":item.id,"message":"Pengurus berhasil ditambahkan"}

@app.delete("/api/admin/officers/{officer_id}")
def delete_officer(officer_id:int,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    item=db.get(Officer,officer_id)
    if not item: raise HTTPException(status_code=404,detail="Pengurus tidak ditemukan")
    item.is_active=False; db.commit(); return {"message":"Pengurus dinonaktifkan"}

@app.get("/api/admin/programs")
def list_programs(user:User=Depends(require_admin),db:Session=Depends(get_db)):
    rows=db.scalars(select(Program).order_by(Program.event_date,Program.id)).all()
    return [{"id":x.id,"title":x.title,"description":x.description,"event_date":x.event_date,"status":x.status} for x in rows]

@app.post("/api/admin/programs")
def add_program(payload:ProgramInput,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    item=Program(**payload.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return {"id":item.id,"message":"Program kerja berhasil ditambahkan"}

@app.delete("/api/admin/programs/{program_id}")
def delete_program(program_id:int,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    item=db.get(Program,program_id)
    if not item: raise HTTPException(status_code=404,detail="Program tidak ditemukan")
    db.delete(item); db.commit(); return {"message":"Program kerja dihapus"}


# PUSAT DOWNLOAD — private Cloudflare R2 bucket, authenticated temporary download URLs.
DOWNLOAD_MAX_BYTES = 25 * 1024 * 1024
DOWNLOAD_ALLOWED = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp",
    ".txt": "text/plain",
}

def r2_client():
    required = ["R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]
    values = {name: (os.getenv(name) or "").strip() for name in required}
    missing = [name for name, value in values.items() if not value]
    if missing:
        logger.error("R2 configuration missing variables: %s", ", ".join(missing))
        raise HTTPException(status_code=503, detail="Konfigurasi R2 belum lengkap: " + ", ".join(missing))
    endpoint = values["R2_ENDPOINT_URL"].rstrip("/")
    if not endpoint.startswith("https://"):
        logger.error("R2_ENDPOINT_URL harus menggunakan HTTPS")
        raise HTTPException(status_code=503, detail="R2_ENDPOINT_URL harus diawali https://")
    try:
        import boto3
        from botocore.config import Config
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=values["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=values["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(signature_version="s3v4", connect_timeout=8, read_timeout=20,
                          retries={"max_attempts": 2, "mode": "standard"}),
        )
    except Exception:
        logger.exception("Gagal menginisialisasi client Cloudflare R2")
        raise HTTPException(status_code=503, detail="Client R2 gagal diinisialisasi. Periksa log Render untuk detail teknis.")

def download_item_json(item: DownloadFile):
    return {
        "id": item.id, "title": item.title, "category": item.category,
        "description": item.description, "original_name": item.original_name,
        "content_type": item.content_type, "file_size": item.file_size,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }

@app.get("/api/downloads")
def list_downloads(category: str = Query(default="", max_length=80),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(DownloadFile).order_by(DownloadFile.created_at.desc(), DownloadFile.id.desc())
    if category.strip():
        stmt = stmt.where(DownloadFile.category == category.strip())
    rows = db.scalars(stmt).all()
    return [download_item_json(item) for item in rows]

@app.post("/api/admin/downloads")
async def upload_download_file(
    title: str = Query(..., min_length=2, max_length=180),
    category: str = Query(..., min_length=2, max_length=80),
    description: str = Query(default="", max_length=1000),
    file: UploadFile = File(...),
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    original = Path(file.filename or "").name
    ext = Path(original).suffix.lower()
    if ext not in DOWNLOAD_ALLOWED:
        raise HTTPException(status_code=400, detail="Format file belum didukung.")
    content = await file.read(DOWNLOAD_MAX_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="File kosong.")
    if len(content) > DOWNLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 25 MB.")
    content_type = DOWNLOAD_ALLOWED[ext]
    supplied_type = (file.content_type or "").split(";")[0].lower()
    if supplied_type and supplied_type not in {content_type, "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Tipe file tidak sesuai dengan ekstensinya.")
    safe_category = re.sub(r"[^\w -]", "", category.strip(), flags=re.UNICODE)[:80]
    safe_title = title.strip()
    if not safe_category or len(safe_category) < 2:
        raise HTTPException(status_code=400, detail="Kategori wajib diisi.")
    object_key = f"widya-trapsila/downloads/{uuid.uuid4().hex}{ext}"
    client = r2_client()
    try:
        client.put_object(Bucket=os.environ["R2_BUCKET_NAME"], Key=object_key, Body=content,
                          ContentType=content_type, Metadata={"original-name": quote(original[:200])})
    except Exception:
        raise HTTPException(status_code=502, detail="Gagal menyimpan file ke penyimpanan cloud.")
    item = DownloadFile(title=safe_title, category=safe_category,
                        description=description.strip() or None, original_name=original[:255],
                        object_key=object_key, content_type=content_type, file_size=len(content),
                        uploaded_by=user.id)
    try:
        db.add(item); db.commit(); db.refresh(item)
    except Exception:
        db.rollback()
        try: client.delete_object(Bucket=os.environ["R2_BUCKET_NAME"], Key=object_key)
        except Exception: pass
        raise HTTPException(status_code=500, detail="Metadata file gagal disimpan.")
    return {"message": "Dokumen berhasil diunggah.", "file": download_item_json(item)}

@app.get("/api/downloads/{file_id}/url")
def get_download_url(file_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(DownloadFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    client = r2_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.environ["R2_BUCKET_NAME"], "Key": item.object_key,
                    "ResponseContentDisposition": f"attachment; filename*=UTF-8''{quote(item.original_name)}",
                    "ResponseContentType": item.content_type},
            ExpiresIn=600,
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Link unduhan belum dapat dibuat.")
    return {"url": url, "expires_in": 600}

@app.patch("/api/admin/downloads/{file_id}")
def update_download_file(file_id: int, payload: dict, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.get(DownloadFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    title = str(payload.get("title", item.title)).strip()
    category = str(payload.get("category", item.category)).strip()
    description = str(payload.get("description", item.description or "")).strip()
    if len(title) < 2 or len(title) > 180 or len(category) < 2 or len(category) > 80 or len(description) > 1000:
        raise HTTPException(status_code=400, detail="Judul/kategori tidak valid atau keterangan terlalu panjang.")
    item.title = title
    item.category = re.sub(r"[^\w -]", "", category, flags=re.UNICODE)[:80]
    item.description = description or None
    db.commit()
    return {"message": "Informasi dokumen berhasil diperbarui.", "file": download_item_json(item)}

@app.delete("/api/admin/downloads/{file_id}")
def delete_download_file(file_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.get(DownloadFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    client = r2_client()
    try:
        client.delete_object(Bucket=os.environ["R2_BUCKET_NAME"], Key=item.object_key)
    except Exception:
        raise HTTPException(status_code=502, detail="File cloud gagal dihapus; data tetap dipertahankan.")
    db.delete(item); db.commit()
    return {"message": "Dokumen berhasil dihapus."}

@app.get("/")
def home(): return FileResponse(str(STATIC_DIR/"index.html"))
