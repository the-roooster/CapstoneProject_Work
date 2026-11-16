-- Run manually in the SQL editor after verifying these legacy tables exist.
-- This does not drop tables, data, or roles.
BEGIN;

DO $$
DECLARE
    policy_row record;
BEGIN
    FOR policy_row IN
        SELECT schemaname, tablename, policyname
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN ('employees', 'events', 'risk_scores')
    LOOP
        EXECUTE format('DROP POLICY %I ON %I.%I',
                       policy_row.policyname, policy_row.schemaname, policy_row.tablename);
    END LOOP;
END $$;

REVOKE ALL PRIVILEGES ON TABLE public.employees, public.events, public.risk_scores
    FROM anon, authenticated;

ALTER TABLE public.employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employees FORCE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.risk_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_scores FORCE ROW LEVEL SECURITY;

COMMIT;
