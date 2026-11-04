CREATE TABLE public.employees (
  id text PRIMARY KEY,
  full_name text NOT NULL,
  department text NOT NULL,
  role text NOT NULL,
  normal_login_start int NOT NULL DEFAULT 9,
  normal_login_end int NOT NULL DEFAULT 18,
  normal_download_count int NOT NULL DEFAULT 10,
  home_location text NOT NULL DEFAULT 'Bengaluru',
  primary_device text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.employees TO authenticated;
GRANT ALL ON public.employees TO service_role;
ALTER TABLE public.employees ENABLE ROW LEVEL SECURITY;
CREATE POLICY "analysts read employees" ON public.employees FOR SELECT TO authenticated USING (true);

CREATE TABLE public.events (
  id bigserial PRIMARY KEY,
  employee_id text NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
  ts timestamptz NOT NULL,
  activity text NOT NULL,
  device text NOT NULL,
  ip text NOT NULL,
  location text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX events_emp_ts ON public.events(employee_id, ts);
CREATE INDEX events_ts ON public.events(ts);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.events TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.events_id_seq TO authenticated;
GRANT ALL ON public.events TO service_role;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "analysts read events" ON public.events FOR SELECT TO authenticated USING (true);

CREATE TABLE public.risk_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id text NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
  date date NOT NULL,
  anomaly_score double precision NOT NULL,
  risk_score int NOT NULL,
  risk_level text NOT NULL,
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  features jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'open',
  scored_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (employee_id, date)
);
CREATE INDEX risk_scores_level ON public.risk_scores(risk_level, date DESC);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.risk_scores TO authenticated;
GRANT ALL ON public.risk_scores TO service_role;
ALTER TABLE public.risk_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "analysts read scores" ON public.risk_scores FOR SELECT TO authenticated USING (true);
CREATE POLICY "analysts insert scores" ON public.risk_scores FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "analysts update scores" ON public.risk_scores FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

-- Seed employees
INSERT INTO public.employees (id, full_name, department, role, normal_login_start, normal_login_end, normal_download_count, home_location, primary_device) VALUES
('EMP001','Priya Sharma','Finance','Accountant',9,18,8,'Bengaluru','WS-FIN-001'),
('EMP002','Rahul Verma','Engineering','Backend Engineer',10,19,15,'Bengaluru','WS-ENG-002'),
('EMP003','Ananya Iyer','HR','HR Manager',9,17,6,'Mumbai','WS-HR-003'),
('EMP004','Vikram Rao','Sales','Account Executive',9,18,12,'Delhi','WS-SAL-004'),
('EMP005','Sneha Kapoor','Engineering','Frontend Engineer',10,19,14,'Bengaluru','WS-ENG-005'),
('EMP006','Arjun Mehta','IT','Sysadmin',8,17,20,'Bengaluru','WS-IT-006'),
('EMP007','Kavya Nair','Finance','Finance Analyst',9,18,10,'Bengaluru','WS-FIN-007'),
('EMP008','Rohan Gupta','Marketing','Content Lead',10,18,9,'Mumbai','WS-MKT-008'),
('EMP009','Meera Joshi','Legal','Counsel',9,18,7,'Delhi','WS-LEG-009'),
('EMP010','Aditya Singh','Engineering','DevOps Engineer',9,19,18,'Hyderabad','WS-ENG-010'),
('EMP011','Ishita Das','Sales','Sales Manager',9,18,11,'Kolkata','WS-SAL-011'),
('EMP012','Karan Malhotra','IT','Security Engineer',9,18,16,'Bengaluru','WS-IT-012'),
('EMP013','Neha Reddy','HR','Recruiter',9,17,5,'Hyderabad','WS-HR-013'),
('EMP014','Siddharth Jain','Finance','Controller',9,18,9,'Mumbai','WS-FIN-014'),
('EMP015','Pooja Pillai','Marketing','Designer',10,19,13,'Bengaluru','WS-MKT-015'),
('EMP016','Manish Kumar','Engineering','Data Engineer',10,19,22,'Pune','WS-ENG-016'),
('EMP017','Divya Menon','Legal','Paralegal',9,17,6,'Chennai','WS-LEG-017'),
('EMP018','Harsh Agarwal','Engineering','Tech Lead',10,19,17,'Bengaluru','WS-ENG-018'),
('EMP019','Riya Bose','Sales','SDR',9,18,8,'Kolkata','WS-SAL-019'),
('EMP020','Nikhil Patil','IT','Helpdesk',8,17,10,'Pune','WS-IT-020');

-- Baseline synthetic activity: 30 weekdays-ish of normal behaviour
SELECT setseed(0.42);
WITH days AS (
  SELECT (current_date - g)::date AS d FROM generate_series(1, 30) g
  WHERE extract(isodow FROM current_date - g) < 6
), base AS (
  SELECT e.*, d.d, ('10.0.' || substr(e.id,4)::int || '.' || (10 + substr(e.id,4)::int)) AS ip_addr
  FROM public.employees e CROSS JOIN days d
)
INSERT INTO public.events (employee_id, ts, activity, device, ip, location, metadata)
SELECT id, d + make_interval(hours => normal_login_start, mins => floor(random()*50)::int), 'login', primary_device, ip_addr, home_location, '{"success":true}'::jsonb FROM base
UNION ALL
SELECT id, d + make_interval(hours => normal_login_start, mins => floor(random()*20)::int), 'login_failed', primary_device, ip_addr, home_location, '{"success":false}'::jsonb FROM base WHERE random() < 0.15
UNION ALL
SELECT b.id, b.d + make_interval(hours => b.normal_login_start + 1 + floor(random()*(b.normal_login_end - b.normal_login_start - 2))::int, mins => floor(random()*59)::int),
  'file_download', b.primary_device, b.ip_addr, b.home_location,
  jsonb_build_object('file', 'doc_' || floor(random()*900+100)::int || '.pdf', 'size_kb', floor(random()*4000+20)::int)
FROM base b CROSS JOIN LATERAL generate_series(1, greatest(1, b.normal_download_count + floor((random()-0.5)*b.normal_download_count*0.6)::int)) s
UNION ALL
SELECT b.id, b.d + make_interval(hours => b.normal_login_start + 2 + floor(random()*5)::int, mins => floor(random()*59)::int),
  'file_upload', b.primary_device, b.ip_addr, b.home_location, jsonb_build_object('file','report_' || floor(random()*90+10)::int || '.xlsx')
FROM base b CROSS JOIN LATERAL generate_series(1, 1 + floor(random()*3)::int) s
UNION ALL
SELECT id, d + make_interval(hours => normal_end_h, mins => floor(random()*50)::int), 'logout', primary_device, ip_addr, home_location, '{}'::jsonb
FROM (SELECT *, normal_login_end AS normal_end_h FROM base) x
UNION ALL
SELECT id, d + make_interval(hours => normal_login_start + 3), 'usb_connect', primary_device, ip_addr, home_location, '{"serial":"KINGSTON-IT-STD"}'::jsonb FROM base WHERE department = 'IT' AND random() < 0.25;

-- Today: normal activity for everyone except the anomalous scenarios
WITH base AS (
  SELECT e.*, ('10.0.' || substr(e.id,4)::int || '.' || (10 + substr(e.id,4)::int)) AS ip_addr FROM public.employees e
  WHERE e.id NOT IN ('EMP007','EMP013','EMP018')
)
INSERT INTO public.events (employee_id, ts, activity, device, ip, location, metadata)
SELECT id, current_date + make_interval(hours => normal_login_start, mins => floor(random()*50)::int), 'login', primary_device, ip_addr, home_location, '{"success":true}'::jsonb FROM base
UNION ALL
SELECT b.id, current_date + make_interval(hours => b.normal_login_start + 1 + floor(random()*4)::int, mins => floor(random()*59)::int), 'file_download', b.primary_device, b.ip_addr, b.home_location,
  jsonb_build_object('file','doc_' || floor(random()*900+100)::int || '.pdf','size_kb', floor(random()*4000+20)::int)
FROM base b CROSS JOIN LATERAL generate_series(1, CASE WHEN b.id = 'EMP004' THEN b.normal_download_count * 4 ELSE b.normal_download_count END) s;

-- Scenario 1: EMP007 Kavya — 2 AM login, new device, mass download, USB
INSERT INTO public.events (employee_id, ts, activity, device, ip, location, metadata)
SELECT 'EMP007', current_date + interval '2 hours 7 minutes', 'login', 'LAPTOP-UNKNOWN-77', '10.0.7.17', 'Bengaluru', '{"success":true}'::jsonb
UNION ALL
SELECT 'EMP007', current_date + interval '2 hours 15 minutes' + (s || ' seconds')::interval * 20, 'file_download', 'LAPTOP-UNKNOWN-77', '10.0.7.17', 'Bengaluru',
  jsonb_build_object('file', 'finance/payroll_q' || (s % 4 + 1) || '_' || s || '.xlsx', 'size_kb', 900 + s)
FROM generate_series(1, 160) s
UNION ALL
SELECT 'EMP007', current_date + interval '3 hours 20 minutes', 'usb_connect', 'LAPTOP-UNKNOWN-77', '10.0.7.17', 'Bengaluru', '{"serial":"SANDISK-ULTRA-9F3A"}'::jsonb
UNION ALL
SELECT 'EMP007', current_date + interval '3 hours 48 minutes', 'usb_remove', 'LAPTOP-UNKNOWN-77', '10.0.7.17', 'Bengaluru', '{"serial":"SANDISK-ULTRA-9F3A"}'::jsonb;

-- Scenario 2: EMP013 Neha — brute-force-like failed logins from a new location
INSERT INTO public.events (employee_id, ts, activity, device, ip, location, metadata)
SELECT 'EMP013', current_date + interval '23 hours' + (s || ' minutes')::interval, 'login_failed', 'WS-HR-013', '185.220.101.' || (30+s), 'Frankfurt', '{"success":false}'::jsonb
FROM generate_series(1, 8) s
UNION ALL
SELECT 'EMP013', current_date + interval '23 hours 12 minutes', 'login', 'WS-HR-013', '185.220.101.44', 'Frankfurt', '{"success":true}'::jsonb
UNION ALL
SELECT 'EMP013', current_date + interval '23 hours 20 minutes' + (s || ' minutes')::interval, 'file_download', 'WS-HR-013', '185.220.101.44', 'Frankfurt',
  jsonb_build_object('file','hr/candidates_' || s || '.csv','size_kb', 300)
FROM generate_series(1, 12) s;

-- Scenario 3: EMP018 Harsh — mass deletions + USB exfil during normal hours
INSERT INTO public.events (employee_id, ts, activity, device, ip, location, metadata)
SELECT 'EMP018', current_date + interval '10 hours 5 minutes', 'login', 'WS-ENG-018', '10.0.18.28', 'Bengaluru', '{"success":true}'::jsonb
UNION ALL
SELECT 'EMP018', current_date + interval '11 hours' + (s || ' minutes')::interval, 'file_download', 'WS-ENG-018', '10.0.18.28', 'Bengaluru',
  jsonb_build_object('file','repo/source_' || s || '.zip','size_kb', 25000)
FROM generate_series(1, 45) s
UNION ALL
SELECT 'EMP018', current_date + interval '12 hours 10 minutes', 'usb_connect', 'WS-ENG-018', '10.0.18.28', 'Bengaluru', '{"serial":"WD-PASSPORT-2TB"}'::jsonb
UNION ALL
SELECT 'EMP018', current_date + interval '13 hours' + (s || ' seconds')::interval * 30, 'file_delete', 'WS-ENG-018', '10.0.18.28', 'Bengaluru',
  jsonb_build_object('file','shared/design_docs/spec_' || s || '.md')
FROM generate_series(1, 70) s;