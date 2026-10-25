import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { health, type Health } from "../lib/api";

export function Nav() {
  const [status, setStatus] = useState<Health>({});

  useEffect(() => {
    health().then(setStatus).catch(() => setStatus({}));
  }, []);

  const link = ({ isActive }: { isActive: boolean }) =>
    `text-[14px] ${isActive ? "text-[#f3efe6]" : "text-[#8d867a] hover:text-[#f3efe6]"}`;

  const night = status.nightshift
    ? "Nightshift live"
    : status.nightshift_unauthorized
      ? "Nightshift needs a token"
      : "Nightshift off";

  return (
    <header className="sticky top-0 z-20 border-b border-[#2a2722] bg-[#12110e]/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="font-serif text-[22px] tracking-tight">
          Handoff
        </Link>
        <nav className="flex items-center gap-6">
          <NavLink to="/" end className={link}>
            Product
          </NavLink>
          <NavLink to="/desk" className={link}>
            Desk
          </NavLink>
          <span className="hidden font-mono text-[11px] text-[#8d867a] sm:inline">
            {status.zetaris ? "Zetaris live" : "Zetaris down"} · {night}
          </span>
          <Link to="/desk?sample=coding" className="bg-[#f3efe6] px-3 py-1.5 text-[13px] font-semibold text-[#12110e]">
            Build a task
          </Link>
        </nav>
      </div>
    </header>
  );
}
