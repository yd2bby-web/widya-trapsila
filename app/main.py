import os
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from openpyxl import load_workbook
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from jwt import InvalidTokenError
from .database import Base, engine, get_db, SessionLocal
from .models import Student, User, Officer, Program
from .schemas import LoginInput, UserOut, OfficerInput, ProgramInput
from .security import create_access_token, decode_access_token, hash_password, verify_password

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_FILE = BASE_DIR / "student_template.xlsx"
Base.metadata.create_all(bind=engine)
app = FastAPI(title="WIDYA TRAPSILA | PIK-R SMP Negeri 1 Wonogiri", version="0.3.0")
bearer = HTTPBearer(auto_error=False)

@app.on_event("startup")
def create_bootstrap_admin():
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "ChangeThis-Immediately-123!")
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.username == username)):
            db.add(User(username=username, full_name="Administrator WIDYA TRAPSILA", password_hash=hash_password(password), role="super_admin"))
            db.commit()
    finally:
        db.close()

@app.get("/api/health")
def health():
    return {"status":"ok", "app":"WIDYA TRAPSILA | PIK-R SMP Negeri 1 Wonogiri", "version":"0.3.0"}

@app.post("/api/auth/login")
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))

    print("LOGIN CHECK:", {
        "username": payload.username,
        "user_found": user is not None,
        "is_active": user.is_active if user else None,
        "password_match": verify_password(payload.password, user.password_hash) if user else False
    })

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username atau password tidak sesuai")

    return {
        "access_token": create_access_token(str(user.id), user.role),
        "token_type": "bearer",
        "user": UserOut.model_validate(user)
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

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)): return UserOut.model_validate(user)

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

@app.get("/api/admin/officers")
def list_officers(user: User=Depends(require_admin), db: Session=Depends(get_db)):
    rows=db.scalars(select(Officer).where(Officer.is_active.is_(True)).order_by(Officer.sort_order,Officer.id)).all()
    return [{"id":x.id,"position":x.position,"full_name":x.full_name,"class_name":x.class_name,"period":x.period} for x in rows]

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

@app.get("/")
def home(): return FileResponse(str(STATIC_DIR/"index.html"))
