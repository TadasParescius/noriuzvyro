import psycopg
from app.db import DATABASE_URL, ROOT


def main():
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute('SELECT pg_advisory_xact_lock(76012026)')
        conn.execute((ROOT / 'database/001-schema.sql').read_text(encoding='utf-8'))
        conn.execute((ROOT / 'database/003-auth.sql').read_text(encoding='utf-8'))
        counts = [conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                  for table in ('quarries', 'offers', 'orders')]
        if counts == [0, 0, 0]:
            conn.execute((ROOT / 'database/002-seed.sql').read_text(encoding='utf-8'))
            print('Seeded 5 quarries, 6 offers and 6 orders.')
        else:
            print('Existing records preserved; seed skipped:', counts)
    print('Database ready.')


if __name__ == '__main__':
    main()
