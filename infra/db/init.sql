-- Local-dev roles (dev passwords only).
-- owner: runs migrations. app: runtime role, no BYPASSRLS, no DDL.
-- admin: BYPASSRLS, used only by /admin routes.
CREATE ROLE app LOGIN PASSWORD 'app' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE admin LOGIN PASSWORD 'admin' NOSUPERUSER BYPASSRLS;
GRANT CONNECT ON DATABASE revops TO app, admin;
GRANT USAGE ON SCHEMA public TO app, admin;
ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app, admin;
ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app, admin;
