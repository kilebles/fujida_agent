import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "src")))

from dotenv import load_dotenv
load_dotenv()

from settings import config as settings
from db.base import Base
from db import models

config_file = context.config
fileConfig(config_file.config_file_name)

target_metadata = Base.metadata

def get_url():
    return os.getenv("DATABASE_URL")

def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from sqlalchemy.ext.asyncio import create_async_engine

    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    async def do_run_migrations():
        async with connectable.connect() as async_conn:
            def run_migrations(sync_conn):
                context.configure(
                    connection=sync_conn,
                    target_metadata=target_metadata,
                    compare_type=True,
                )
                with context.begin_transaction():
                    context.run_migrations()

            await async_conn.run_sync(run_migrations)

    asyncio.run(do_run_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
