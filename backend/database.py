import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Your Tiger Data connection string
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://tsdbadmin:p4d86pi5ijnurb04@axlri9m9b8.obi5rjrxue.tsdb.cloud.timescale.com:33323/tsdb",
)

# Fix prefix if necessary
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Add connect_timeout so it fails in 5 seconds instead of hanging forever
engine = create_engine(
    DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 5}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
