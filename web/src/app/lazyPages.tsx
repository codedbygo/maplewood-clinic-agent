import { lazy } from "react";

// The live console loads first; the other pages are split into their own chunks.
// RootLayout's Suspense boundary shows while a chunk loads.
export const InboxPage = lazy(() =>
  import("@/features/inbox/components/InboxPage").then((m) => ({ default: m.InboxPage })),
);
export const MessagePage = lazy(() =>
  import("@/features/inbox/components/MessagePage").then((m) => ({ default: m.MessagePage })),
);
export const QueuesPage = lazy(() =>
  import("@/features/queues/components/QueuesPage").then((m) => ({ default: m.QueuesPage })),
);
export const SchedulePage = lazy(() =>
  import("@/features/schedule/components/SchedulePage").then((m) => ({ default: m.SchedulePage })),
);
export const EvalPage = lazy(() =>
  import("@/features/eval/components/EvalPage").then((m) => ({ default: m.EvalPage })),
);
