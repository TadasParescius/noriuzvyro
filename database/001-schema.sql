CREATE TABLE IF NOT EXISTS quarries (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name VARCHAR(100) NOT NULL CHECK (length(trim(name)) >= 2),
  city VARCHAR(80) NOT NULL,
  address VARCHAR(200) NOT NULL,
  phone VARCHAR(16) NOT NULL,
  description VARCHAR(1000) NOT NULL,
  latitude NUMERIC(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offers (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  quarry_id INTEGER NOT NULL REFERENCES quarries(id) ON DELETE RESTRICT,
  name VARCHAR(100) NOT NULL,
  material_type VARCHAR(30) NOT NULL CHECK (material_type IN ('gravel', 'sand', 'crushed_stone')),
  fraction VARCHAR(40) NOT NULL,
  description VARCHAR(1000) NOT NULL,
  price_per_tonne_eur NUMERIC(10,2) NOT NULL CHECK (price_per_tonne_eur > 0 AND price_per_tonne_eur <= 999999.99),
  available BOOLEAN NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS offers_quarry_id_idx ON offers(quarry_id);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  offer_id INTEGER NOT NULL REFERENCES offers(id) ON DELETE RESTRICT,
  customer_name VARCHAR(100) NOT NULL,
  email VARCHAR(254) NOT NULL,
  phone VARCHAR(16) NOT NULL,
  delivery_address VARCHAR(200) NOT NULL,
  quantity_tonnes NUMERIC(10,3) NOT NULL CHECK (quantity_tonnes > 0 AND quantity_tonnes <= 1000),
  unit_price_eur NUMERIC(10,2) NOT NULL CHECK (unit_price_eur > 0),
  material_total_eur NUMERIC(12,2) GENERATED ALWAYS AS (round(quantity_tonnes * unit_price_eur, 2)) STORED,
  will_be_home BOOLEAN NOT NULL,
  unloading_instructions VARCHAR(1000) NOT NULL,
  payment_method VARCHAR(10) NOT NULL CHECK (payment_method IN ('card', 'cash')),
  status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'confirmed', 'delivered', 'cancelled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (will_be_home OR length(trim(unloading_instructions)) > 0)
);
CREATE INDEX IF NOT EXISTS orders_offer_id_idx ON orders(offer_id);
