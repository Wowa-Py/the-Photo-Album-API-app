from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, create_engine
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.ext.declarative import declarative_base
import shutil
from datetime import timedelta
from pydantic import BaseModel
from fastapi import FastAPI, Depends
from datetime import datetime, timedelta

# создание новой базы данных PostgreSQL

SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# определение моделий SQLAlchemy
class User(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    hashed_password: str
    is_active: bool
    is_admin: bool
    is_superuser: bool
    phone: int = None
    birth_date: datetime = None

class Album(BaseModel):
    id: int
    title: str
    description: str
    owner_id: int
    created_at: datetime
    updated_at: datetime

class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    file = Column(String)
    caption = Column(String)
    album_id = Column(Integer, ForeignKey("albums.id"))
    album = relationship("Album", back_populates="photos")

# приложение FastAPI + статические файлы
app = FastAPI(
    title="Photo Album"

)

app.mount("/static", StaticFiles(directory="static"), name="static")


# функции для работы с базой данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# функции для работы с аутентификацией
def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# маршруты app
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/users/", response_model=User)
def create_user(user: User, db: Session = Depends(get_db)):
    db_user = get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users/{user_id}")
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/albums/", response_model=Album)
def create_album(album: Album, db: Session = Depends(get_db)):
    db_album = get_album(db, album_id=album.id)
    if db_album:
        raise HTTPException(status_code=400, detail="Album already exists")
    db_album = Album(title=album.title, description=album.description, owner_id=album.owner_id)
    db.add(db_album)
    db.commit()
    db.refresh(db_album)
    return db_album

@app.get("/albums/{album_id}")
def read_album(album_id: int, db: Session = Depends(get_db)):
    album = db.query(Album).filter(Album.id == album_id).first()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")
    return album


@app.post("/photos/")
async def upload_photo(photo: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        file_location = f"static/images/{photo.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(photo.file, file_object)

        db_photo = Photo(file=file_location)
        db.add(db_photo)
        db.commit()
        db.refresh(db_photo)

        return {"info": f"photo '{photo.filename}' is saved at '{file_location}'"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Photo not saved")
