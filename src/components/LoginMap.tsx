import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { CITY_COORDS, type LocationStat } from "@/lib/locations";

export default function LoginMap({ stats }: { stats: LocationStat[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current, { worldCopyJump: true }).setView([20, 60], 3);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 18 }).addTo(map);
    const max = Math.max(1, ...stats.map((s) => s.logins));
    for (const s of stats) {
      const c = CITY_COORDS[s.location];
      if (!c) continue;
      const color = s.unusual > 0 ? "#ef4444" : "#22c55e";
      L.circleMarker(c, { radius: 6 + 18 * Math.sqrt(s.logins / max), color, fillColor: color, fillOpacity: 0.45, weight: 2 })
        .bindPopup(`<b>${s.location}</b><br/>${s.logins} logins<br/>${s.unusual} outside home city<br/><small>${s.users.slice(0, 8).join(", ")}</small>`)
        .addTo(map);
    }
    return () => { map.remove(); };
  }, [stats]);
  return <div ref={ref} className="h-[480px] w-full rounded-sm border border-border" />;
}
