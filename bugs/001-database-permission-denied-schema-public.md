# Bug #001: Database Permission Denied for Schema Public

## Status
✅ **RESOLVED**

## Date
2025-12-30

## Severity
🔴 **HIGH** - Blocks database migrations and prevents application setup

## Description
When running `python manage.py migrate`, Django fails with a PostgreSQL permission error:
```
django.db.migrations.exceptions.MigrationSchemaMissing: Unable to create the django_migrations table (permission denied for schema public)
```

## Error Details
```
psycopg.errors.InsufficientPrivilege: permission denied for schema public
LINE 1: CREATE TABLE "django_migrations" ("id" bigint NOT NULL PRIMA...
```

## Root Cause
The PostgreSQL database user (`hedgemind_user`) does not have the necessary privileges to:
- Create tables in the `public` schema
- Create sequences in the `public` schema
- Use the `public` schema

This is a common issue when:
- The database user was created without proper permissions
- The database was created by a different user
- PostgreSQL security policies restrict schema access

## Environment
- **Database**: PostgreSQL
- **Database Name**: `hedgeminddb_dev` (default from settings)
- **Database User**: `hedgemind_user` (default from settings)
- **Django Version**: 5.2
- **Python Version**: 3.11

## Steps to Reproduce
1. Set up a new PostgreSQL database
2. Create a database user without granting schema permissions
3. Configure Django settings to use this user
4. Run `python manage.py migrate`
5. Error occurs when Django tries to create the `django_migrations` table

## Solution

### Quick Fix
Run the following SQL commands as a PostgreSQL superuser (usually `postgres`):

```sql
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
```

### Using the Fix Script
A SQL script has been created at `scripts/fix_db_permissions.sql` that contains all necessary commands.

Run it with:
```bash
psql -U postgres -d hedgeminddb_dev -f scripts/fix_db_permissions.sql
```

### Alternative Solutions

#### Option 1: Use postgres superuser (temporary)
If you can't modify permissions immediately, temporarily use the `postgres` superuser in your `.env`:
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
```

#### Option 2: Create user with proper permissions from the start
When creating a new database user, grant permissions immediately:
```sql
CREATE USER hedgemind_user WITH PASSWORD 'risk_platform';
GRANT ALL PRIVILEGES ON DATABASE hedgeminddb_dev TO hedgemind_user;
\c hedgeminddb_dev;
GRANT ALL ON SCHEMA public TO hedgemind_user;
```

## Prevention
1. **Documentation**: Add database setup instructions to README.md
2. **Docker Compose**: If using Docker, ensure proper permissions in initialization scripts
3. **CI/CD**: Include permission grants in deployment scripts
4. **Environment Setup**: Create a setup script that checks and fixes permissions automatically

## Related Files
- `config/settings/base.py` - Database configuration
- `scripts/fix_db_permissions.sql` - Fix script
- `.env.example` - Environment variable template

## Notes
- This is a common PostgreSQL setup issue, not a Django bug
- The error message is clear and points directly to the permission problem
- The fix is straightforward but requires database admin access
- Consider adding this to the project's setup documentation

## Resolution Date
2025-12-30

## Fixed By
- Created `scripts/fix_db_permissions.sql` with all necessary SQL commands
- Documented the issue and solution in this bug report

