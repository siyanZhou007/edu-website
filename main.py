from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import hashlib
import secrets
from jose import jwt
import os

app = FastAPI(title="智慧教育学院官网")

# 数据库配置
DATABASE_URL = "sqlite:///./edu_website.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# JWT配置
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"

# 静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 数据库模型
class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    description = Column(Text)
    category = Column(String(50))
    price = Column(Float)
    is_featured = Column(Boolean, default=False)
    status = Column(String(20), default="active")

class News(Base):
    __tablename__ = "news"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    content = Column(Text)
    summary = Column(String(200))
    is_published = Column(Boolean, default=False)

# 创建数据库表
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, hashed = hashed_password.split('$')
        return hashlib.sha256((plain_password + salt).encode()).hexdigest() == hashed
    except:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def init_admin():
    db = SessionLocal()
    admin = db.query(Admin).filter(Admin.username == "admin").first()
    if not admin:
        admin = Admin(username="admin", password=get_password_hash("admin123"))
        db.add(admin)
        db.commit()
    db.close()

def init_sample_data():
    db = SessionLocal()
    if db.query(Course).count() == 0:
        courses = [
            Course(title="Python编程基础", description="从零开始学习Python", category="编程", price=199.0, is_featured=True),
            Course(title="Web前端开发", description="HTML/CSS/JavaScript实战", category="编程", price=299.0),
            Course(title="数据分析入门", description="Excel+Python数据分析", category="数据", price=249.0),
        ]
        db.add_all(courses)
    if db.query(News).count() == 0:
        news = [
            News(title="学院成立五周年", content="智慧教育学院成立五周年", summary="庆祝成立五周年", is_published=True),
            News(title="新增AI课程", content="人工智能课程上线", summary="AI课程上线", is_published=True),
        ]
        db.add_all(news)
    db.commit()
    db.close()

# 启动时初始化
init_admin()
init_sample_data()

# ========== 路由 ==========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = SessionLocal()
    courses = db.query(Course).filter(Course.status == "active", Course.is_featured == True).limit(3).all()
    news = db.query(News).filter(News.is_published == True).limit(3).all()
    return templates.TemplateResponse("index.html", {"request": request, "courses": courses, "news": news})

@app.get("/courses", response_class=HTMLResponse)
async def courses(request: Request):
    db = SessionLocal()
    courses = db.query(Course).filter(Course.status == "active").all()
    return templates.TemplateResponse("courses.html", {"request": request, "courses": courses})

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/user/login", response_class=HTMLResponse)
async def user_login(request: Request):
    return templates.TemplateResponse("user/login.html", {"request": request})

@app.get("/user/register", response_class=HTMLResponse)
async def user_register(request: Request):
    return templates.TemplateResponse("user/register.html", {"request": request})

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})

@app.post("/api/user/register")
async def user_register(username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=username, email=email, password=get_password_hash(password))
    db.add(user)
    db.commit()
    return {"message": "注册成功"}

@app.post("/api/user/login")
async def user_login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    access_token = create_access_token(data={"sub": f"user:{username}", "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/admin/login")
async def admin_login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not verify_password(password, admin.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    access_token = create_access_token(data={"sub": username})
    return {"access_token": access_token, "token_type": "bearer"}

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("   智慧教育学院官网")
    print("="*50)
    print("\n🌐 网站地址: http://localhost:8000")
    print("\n🔐 默认管理员账号:")
    print("   用户名: admin")
    print("   密码:   admin123")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
