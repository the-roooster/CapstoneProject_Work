import { createFileRoute, Link, Outlet, redirect, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { LayoutDashboard, Siren, LogOut, ShieldHalf, MapPin, Upload } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async () => {
    const { data } = await supabase.auth.getUser();
    if (!data.user) throw redirect({ to: "/auth" });
    return { user: data.user };
  },
  component: Shell,
});

function Shell() {
  const { user } = Route.useRouteContext();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  async function signOut() {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    navigate({ to: "/auth", replace: true });
  }
  const link = "flex items-center gap-2 rounded-sm px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground";
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-sidebar">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link to="/dashboard" className="flex items-center gap-2 font-mono text-sm font-bold tracking-widest text-primary">
            <ShieldHalf className="size-5" /> SENTINEL<span className="text-foreground">AI</span>
          </Link>
          <nav className="flex gap-1">
            <Link to="/dashboard" className={link} activeProps={{ className: "bg-accent text-foreground" }}><LayoutDashboard className="size-4" />Dashboard</Link>
            <Link to="/alerts" className={link} activeProps={{ className: "bg-accent text-foreground" }}><Siren className="size-4" />Alerts</Link>
            <Link to="/map" className={link} activeProps={{ className: "bg-accent text-foreground" }}><MapPin className="size-4" />Login map</Link>
            <Link to="/import" className={link} activeProps={{ className: "bg-accent text-foreground" }}><Upload className="size-4" />Import</Link>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden font-mono text-xs text-muted-foreground sm:inline">{user.email}</span>
            <button onClick={signOut} className={link}><LogOut className="size-4" />Sign out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6"><Outlet /></main>
    </div>
  );
}
