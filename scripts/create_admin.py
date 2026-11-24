"""Create or promote an administrator explicitly, without default passwords."""
import getpass
import psycopg
from app.db import DATABASE_URL
from app.auth import passwords


def main():
    email = input('Administrator email: ').strip().lower()
    name = input('Name: ').strip()
    password = getpass.getpass('Password (at least 10 characters): ')
    if '@' not in email or not name or len(password) < 10:
        raise SystemExit('Invalid email, name or password.')
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute('''INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,'admin')
            ON CONFLICT(email) DO UPDATE SET role='admin',password_hash=EXCLUDED.password_hash
            RETURNING id''', (name,email,passwords.hash(password))).fetchone()
        conn.execute('UPDATE auth_sessions SET revoked=true WHERE user_id=%s', (row[0],))
    print('Administrator ready.')


if __name__ == '__main__':
    main()
