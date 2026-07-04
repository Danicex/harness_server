#init data base and startconnection on app start
from typing import Annotated
from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine
import os
from dotenv import load_dotenv
from app import model

load_dotenv()
POSTGRES_URL= os.getenv("POSTGRES_URL")


connect_args = {"check_same_thread": False}
engine = create_engine(POSTGRES_URL,echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

if __name__ == "__main__":
    create_db_and_tables()
