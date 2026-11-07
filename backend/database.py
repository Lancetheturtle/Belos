import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Connects directly to Tiger Data (reads from environment variable or falls back to your URI)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg://tsdbadmin:tsdbadmin@gcuogs8n40.obi5rjrxue.tsdb.cloud.timescale.com:5432/tsdb"
)

# Fix for any Heroku/Vercel-style postgres:// prefixes
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create SQLAlchemy Engine for PostgreSQL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Automatically reconnects if the cloud connection drops
    pool_size=10,            # Max persistent connections
    max_overflow=20          # Extra temporary burst connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()