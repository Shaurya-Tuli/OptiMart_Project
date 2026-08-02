-- OptiMart Database Initialization Script

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------- Stores ----------
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(500),
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Batches ----------
CREATE TABLE IF NOT EXISTS batches (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'General',
    quantity INTEGER NOT NULL DEFAULT 0,
    cost_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    original_selling_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    current_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    expiration_date DATE NOT NULL,
    discount_percentage DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Indexes ----------
CREATE INDEX IF NOT EXISTS idx_stores_name ON stores(name);
CREATE INDEX IF NOT EXISTS idx_batches_store_id ON batches(store_id);
CREATE INDEX IF NOT EXISTS idx_batches_sku ON batches(sku);
CREATE INDEX IF NOT EXISTS idx_batches_product_name ON batches(product_name);
CREATE INDEX IF NOT EXISTS idx_batches_category ON batches(category);
CREATE INDEX IF NOT EXISTS idx_batches_expiration_date ON batches(expiration_date);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
