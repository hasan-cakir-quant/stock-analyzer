import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  Database,
  History,
  PanelLeftClose,
  PanelLeftOpen,
  Settings as SettingsIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Briefcase;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Portfolio", icon: Briefcase, end: true },
  { to: "/snapshots", label: "Snapshots", icon: History },
  { to: "/data", label: "Data", icon: Database },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

const STORAGE_KEY = "sidebar-collapsed";

export function Sidebar() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  });

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-border bg-card transition-[width] duration-150",
        collapsed ? "w-11" : "w-44",
      )}
    >
      <div
        className={cn(
          "flex items-center gap-1.5 px-2 py-2",
          collapsed && "justify-center px-1",
        )}
      >
        <BarChart3 className="h-4 w-4 shrink-0 text-primary" />
        {!collapsed && (
          <span className="flex-1 truncate text-xs font-semibold tracking-tight">
            Stock Analyzer
          </span>
        )}
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand" : "Collapse"}
          className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          {collapsed ? (
            <PanelLeftOpen className="h-3.5 w-3.5" />
          ) : (
            <PanelLeftClose className="h-3.5 w-3.5" />
          )}
        </button>
      </div>
      <nav className={cn("flex flex-col gap-0.5", collapsed ? "px-1" : "px-1.5")}>
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors",
                collapsed && "justify-center px-1",
                isActive
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <Icon className="h-3.5 w-3.5 shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
