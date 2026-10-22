import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  redirect,
  type RouterHistory,
} from "@tanstack/react-router";
import { z } from "zod";

import { EvalPage, InboxPage, MessagePage, QueuesPage, SchedulePage } from "@/app/lazyPages";
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

// ?replay=M006&dataset=sample pre-fills the form with a graded message, to run it again live.
const liveSearch = z.object({
  replay: z.string().trim().min(1).max(32).optional().catch(undefined),
  dataset: datasetIdSchema.optional().catch(undefined),
});

const liveRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (raw) => liveSearch.parse(raw),
  component: function LiveRoute() {
    const { replay, dataset } = liveRoute.useSearch();
    return <LivePage replay={replay ? { id: replay, dataset: dataset ?? "sample" } : undefined} />;
  },
});

const inboxSearch = z.object({
  dataset: datasetIdSchema.catch("sample"),
  filter: z.enum(["all", "attention", "emergency"]).catch("all"),
});

// ?id= is the old single-page link (bookmarks, earlier reports); it now opens the message page.
const legacyId = z.object({ id: z.string().trim().min(1).max(32).optional().catch(undefined) });

const inboxRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inbox",
  validateSearch: (raw) => inboxSearch.parse(raw),
  beforeLoad: ({ location, search }) => {
    const { id } = legacyId.parse(location.search);
    if (id) redirect({ to: "/inbox/$messageId", params: { messageId: id }, search, throw: true });
  },
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

const messageRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inbox/$messageId",
  validateSearch: (raw) => inboxSearch.parse(raw),
  component: function MessageRoute() {
    const { messageId } = messageRoute.useParams();
    const { dataset, filter } = messageRoute.useSearch();
    return <MessagePage messageId={messageId} dataset={dataset} filter={filter} />;
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
  messageRoute,
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
