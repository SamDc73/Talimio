import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# Load environment variables from .env file
load_dotenv()

# Get the DATABASE_URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    msg = "DATABASE_URL is not set in the environment variables"
    raise ValueError(msg)

# Create an asynchronous engine with the asyncpg driver
engine = create_async_engine(DATABASE_URL, echo=True)

# Create an asynchronous sessionmaker
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Create a declarative base for ORM models
Base = declarative_base()

