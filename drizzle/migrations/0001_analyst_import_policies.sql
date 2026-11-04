CREATE POLICY "analysts insert employees" ON public.employees FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "analysts update employees" ON public.employees FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "analysts insert events" ON public.events FOR INSERT TO authenticated WITH CHECK (true);