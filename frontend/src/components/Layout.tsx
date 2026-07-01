import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/Sidebar";

/**
 * App shell — left sidebar + scrollable main content.
 * Routes render into the <Outlet /> via React Router.
 */
export function Layout() {
  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-3 py-2">
        <Outlet />
      </main>
    </div>
  );
}
