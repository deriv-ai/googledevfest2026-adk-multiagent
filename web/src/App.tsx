import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { ApiError } from "@/api/client";
import { Skeleton } from "@/components/ui";
import { NotFoundPage } from "@/pages/NotFoundPage";

const OverviewPage = lazy(() => import("@/pages/overview/OverviewPage"));
const ChatPage = lazy(() => import("@/pages/chat/ChatPage"));
const ToolsPage = lazy(() => import("@/pages/tools/ToolsPage"));
const ToolDetailPage = lazy(() => import("@/pages/tools/ToolDetailPage"));
const ToolEditorPage = lazy(() => import("@/pages/tools/ToolEditorPage"));
const SchemaPage = lazy(() => import("@/pages/schema/SchemaPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

function PageFallback() {
  return (
    <div className="mx-auto max-w-6xl space-y-4 p-8" aria-busy="true">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-4 w-96" />
      <Skeleton className="mt-6 h-64 w-full" />
    </div>
  );
}

const s = (el: React.ReactNode) => <Suspense fallback={<PageFallback />}>{el}</Suspense>;

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: s(<OverviewPage />) },
      { path: "/chat", element: s(<ChatPage />) },
      { path: "/tools", element: s(<ToolsPage />) },
      { path: "/tools/new", element: s(<ToolEditorPage />) },
      { path: "/tools/:name", element: s(<ToolDetailPage />) },
      { path: "/tools/:name/edit", element: s(<ToolEditorPage />) },
      { path: "/schema", element: s(<SchemaPage />) },
      { path: "/schema/:schema", element: s(<SchemaPage />) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

export function mount(el: HTMLElement) {
  createRoot(el).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  );
}
