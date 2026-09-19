-- Local test databases only; Supabase supplies these objects in production.
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE TABLE auth.users (id UUID PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS UUID
LANGUAGE sql STABLE
AS $$
    SELECT COALESCE(
        NULLIF(current_setting('request.jwt.claim.sub', TRUE), ''),
        NULLIF(current_setting('request.jwt.claims', TRUE), '')::jsonb ->> 'sub'
    )::uuid
$$;
CREATE FUNCTION auth.jwt() RETURNS JSONB
LANGUAGE sql STABLE
AS $$
    SELECT COALESCE(
        NULLIF(current_setting('request.jwt.claims', TRUE), '')::jsonb,
        '{}'::jsonb
    )
$$;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION auth.uid(), auth.jwt()
TO anon, authenticated, service_role;
