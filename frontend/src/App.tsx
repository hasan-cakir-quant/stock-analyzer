import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { Toaster } from "@/components/Toaster";
import { queryClient } from "@/lib/queryClient";
import DataAvailability from "@/pages/DataAvailability";
import Dev from "@/pages/Dev";
import Home from "@/pages/Home";
import Settings from "@/pages/Settings";
import Snapshots from "@/pages/Snapshots";
import Stock from "@/pages/Stock";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="stocks/:symbol" element={<Stock />} />
            <Route path="snapshots" element={<Snapshots />} />
            <Route path="data" element={<DataAvailability />} />
            <Route path="settings" element={<Settings />} />
            <Route path="dev" element={<Dev />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
