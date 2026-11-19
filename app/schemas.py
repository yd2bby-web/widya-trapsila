from pydantic import BaseModel, ConfigDict

class LoginInput(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool

class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nis: str
    nisn: str | None
    full_name: str
    class_name: str
    is_active: bool

class OfficerInput(BaseModel):
    position: str
    full_name: str
    class_name: str | None = None
    period: str = "2026/2027"
    sort_order: int = 0

class ProgramInput(BaseModel):
    title: str
    description: str | None = None
    event_date: str | None = None
    status: str = "Direncanakan"
