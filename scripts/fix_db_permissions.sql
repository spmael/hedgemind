-- Fix PostgreSQL permissions for hedgemind_user
-- Run this as a PostgreSQL superuser (usually 'postgres')

-- Connect to the database
\c hedgeminddb_dev;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO hedgemind_user;

-- Grant create privileges on the public schema
GRANT CREATE ON SCHEMA public TO hedgemind_user;

-- Grant all privileges on all existing tables in public schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hedgemind_user;

-- Grant all privileges on all existing sequences in public schema
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hedgemind_user;

-- Set default privileges for future tables and sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hedgemind_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hedgemind_user;

-- If the user doesn't exist, create it first:
-- CREATE USER hedgemind_user WITH PASSWORD 'risk_platform';
-- GRANT ALL PRIVILEGES ON DATABASE hedgeminddb_dev TO hedgemind_user;

