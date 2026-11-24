CREATE TABLE IF NOT EXISTS users (
 id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name VARCHAR(100) NOT NULL,
 email VARCHAR(254) NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 role VARCHAR(20) NOT NULL DEFAULT 'buyer' CHECK(role IN ('buyer','quarry','driver','admin')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS auth_sessions (
 id UUID PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TIMESTAMPTZ NOT NULL,
 revoked BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
 token_hash CHAR(64) PRIMARY KEY,
 session_id UUID NOT NULL REFERENCES auth_sessions(id) ON DELETE CASCADE,
 used BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS auth_sessions_user_idx ON auth_sessions(user_id);
ALTER TABLE quarries ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS driver_id INTEGER REFERENCES users(id);
CREATE INDEX IF NOT EXISTS orders_owner_idx ON orders(owner_id);
CREATE INDEX IF NOT EXISTS quarries_owner_idx ON quarries(owner_id);
