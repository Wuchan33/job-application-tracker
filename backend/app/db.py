import os
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, create_engine

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

engine = create_engine(os.environ["DATABASE_URL"])


def get_session():
    with Session(engine) as session:
        yield session
