import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { AppShell } from "./app/AppShell";
import { AuthGate } from "./app/AuthGate";
import { Toaster } from "./components/ui";
import { InboxScreen } from "./screens/Inbox";
import { ProjectScreen } from "./screens/Project";
import { ProjectsScreen } from "./screens/Projects";
import { SearchScreen } from "./screens/Search";

/** One set of URLs for both layouts. `:itemId?` is optional: with it, the phone shows
 *  the item full screen and the desktop shows it beside the list. */
export function App() {
  return (
    <BrowserRouter>
      <AuthGate>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/inbox" replace />} />
            <Route path="inbox/:itemId?" element={<InboxScreen />} />
            <Route path="projects" element={<ProjectsScreen />} />
            <Route path="p/:projectId/:itemId?" element={<ProjectScreen />} />
            <Route path="search/:itemId?" element={<SearchScreen />} />
            <Route path="*" element={<Navigate to="/inbox" replace />} />
          </Route>
        </Routes>
      </AuthGate>
      <Toaster />
    </BrowserRouter>
  );
}
