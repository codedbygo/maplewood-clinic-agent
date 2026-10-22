import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  type RouterHistory,
} from "@tanstack/react-router";
import { z } from "zod";

import { EvalPage, InboxPage, QueuesPage, SchedulePage } from "@/app/lazyPages";
import { NotFound } from "@/app/NotFound";
import { RootLayout } from "@/app/RootLayout";
import { RouteError } from "@/app/RouteError";
import { datasetIdSchema } from "@/features/inbox/schemas";
import { LivePage } from "@/features/live/components/LivePage";
import { stateSourceSchema } from "@/features/state/schemas";

// Code-based routes. Each search param parses on its own (.catch), so one bad
// value in a pasted URL falls back to its default instead of failing the page.
interface RouterContext {
  queryClient: QueryClient;
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  errorComponent: RouteError,
  notFoundComponent: NotFound,
});

const liveRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: LivePage });

const inboxSearch = z.object({
  dataset: datasetIdSchema.catch("sample"),
  id: z.string().trim().min(1).max(32).optional().catch(undefined),
  filter: z.enum(["all", "attention", "emergency"]).catch("all"),
});

const inboxRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inbox",
  validateSearch: (raw) => inboxSearch.parse(raw),
  component: function InboxRoute() {
    const search = inboxRoute.useSearch();
    const navigate = inboxRoute.useNavigate();
    return (
      <InboxPage
        search={search}
        onSearch={(next) =>
          void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true })
        }
      />
    );
  },
});

const sourceSearch = z.object({ source: stateSourceSchema.catch("live") });

const queuesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/queues",
  validateSearch: (raw) => sourceSearch.parse(raw),
  component: function QueuesRoute() {
    const { source } = queuesRoute.useSearch();
    const navigate = queuesRoute.useNavigate();
    return (
      <QueuesPage
        source={source}
        onSource={(next) => void navigate({ search: { source: next }, replace: true })}
      />
    );
  },
});

const scheduleSearch = sourceSearch.extend({
  date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .optional()
    .catch(undefined),
});

const scheduleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/schedule",
  validateSearch: (raw) => scheduleSearch.parse(raw),
  component: function ScheduleRoute() {
    const search = scheduleRoute.useSearch();
    const navigate = scheduleRoute.useNavigate();
    return (
      <SchedulePage
        search={search}
        onSearch={(next) =>
          void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true })
        }
      />
    );
  },
});

const evalSearch = z.object({ dataset: datasetIdSchema.catch("sample") });

const evalRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/eval",
  validateSearch: (raw) => evalSearch.parse(raw),
  component: function EvalRoute() {
    const { dataset } = evalRoute.useSearch();
    const navigate = evalRoute.useNavigate();
    return (
      <EvalPage
        dataset={dataset}
        onDataset={(next) => void navigate({ search: { dataset: next }, replace: true })}
      />
    );
  },
});

export const routeTree = rootRoute.addChildren([
  liveRoute,
  inboxRoute,
  queuesRoute,
  scheduleRoute,
  evalRoute,
]);

interface AppRouterOptions {
  queryClient: QueryClient;
  /** Memory history for tests; browser history by default. */
  history?: RouterHistory;
}

export function createAppRouter({ queryClient, history }: AppRouterOptions) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: "intent",
    defaultErrorComponent: RouteError,
    scrollRestoration: true,
    ...(history ? { history } : {}),
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
