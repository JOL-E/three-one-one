import "./styles.css";

import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ensureCsrfCookie } from "./api/client";
import { App } from "./App";
import { toast } from "./lib/toast";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 15_000 } },
  // A refused write shows the server's message (a broken rule reads like a sentence).
  mutationCache: new MutationCache({
    onError: (error) => toast(error.message),
  }),
});

const root = document.getElementById("root");
if (!root) throw new Error("#root missing");

void ensureCsrfCookie().finally(() => {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
});
