import { createMemoryHistory } from "@tanstack/react-router";
import { render } from "@testing-library/react";

import { App } from "@/app/App";

import { createTestQueryClient } from "./render";

/** renderRoute mounts the whole app at a URL, with a fresh query client and memory history. */
export function renderRoute(path: string) {
  const client = createTestQueryClient();
  const history = createMemoryHistory({ initialEntries: [path] });
  return { ...render(<App queryClient={client} history={history} />), client, history };
}
