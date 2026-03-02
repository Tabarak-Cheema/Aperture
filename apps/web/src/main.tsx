import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import AskPage from "./pages/AskPage";
import ProjectsPage from "./pages/ProjectsPage";
import FilesPage from "./pages/FilesPage";
import SchemaPage from "./pages/SchemaPage";
import SettingsPage from "./pages/SettingsPage";
import HistoryPage from "./pages/HistoryPage";
import CommandPalette from "./components/CommandPalette";
import { ThemeProvider } from "./lib/theme";
import "./styles.css";

const client = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <BrowserRouter>
          <Routes>
            <Route element={<App />}>
              <Route index element={<Navigate to="/ask" replace />} />
              <Route path="ask" element={<AskPage />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="files" element={<FilesPage />} />
              <Route path="schema" element={<SchemaPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
          <CommandPalette />
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>
);
