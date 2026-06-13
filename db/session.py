from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from config import settings

# Engine pool configuration.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    }
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys and IMMEDIATE isolation per connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    dbapi_connection.isolation_level = "IMMEDIATE"
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)