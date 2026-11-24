import os
from pathlib import Path

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://noriuzvyro:local_lab1_password@127.0.0.1:5433/noriuzvyro')
pool = ConnectionPool(DATABASE_URL, min_size=0, max_size=10, timeout=5, open=False,
                      kwargs={'row_factory': dict_row, 'connect_timeout': 5,
                              'options': '-c statement_timeout=5000'})


def query(sql, params=()):
    """Every query is committed or rolled back before its connection is reused."""
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()
