import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { health } from "../lib/api";

export function Nav() {
  const [live, setLive] = useState<string>("…");

  useEffect(() => {
    health()
      .then((h) => setLive(h.zetaris ? "Zetaris live" : "Zetaris down"))
      .catch(() => setLive("API down"));
  }, []);

  const link = ({ isActive }: { isActive: boolean }) =>
    `text-[13px] tracking-wide uppercase ${isActive ? "text-white" : "text-zinc-400 hover:text-white"}`;

  return (
    <header className="sticky top-0 z-20 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
        <Link to="/" className="text-[15px] font-medium tracking-tight">
          Handoff
        </Link>
        <nav className="flex items-center gap-6">
          <NavLink to="/" end className={link}>
            Product
          </NavLink>
          <NavLink to="/desk" className={link}>
            Desk
          </NavLink>
          <a
            href="https://github.com/N-45div/Handoff"
            className="text-[13px] uppercase tracking-wide text-zinc-400 hover:text-white"
          >
            GitHub
          </a>
          <span className="hidden font-mono text-[11px] text-zinc-500 sm:inline">{live}</span>
        </nav>
      </div>
    </header>
  );
}
