import { AlertCircle, Inbox } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";

/** Pending placeholder for a query region. */
export function Pending({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

/** Error state with a retry. A 404 reads as "nothing yet" with the command that creates it. */
export function QueryError({
  error,
  onRetry,
  notFound,
}: {
  error: unknown;
  onRetry: () => void;
  notFound?: ReactNode;
}) {
  if (error instanceof ApiError && error.status === 404 && notFound) {
    return <Empty title="Nothing here yet">{notFound}</Empty>;
  }
  return (
    <Alert variant="destructive">
      <AlertCircle aria-hidden />
      <AlertTitle>Could not load this view</AlertTitle>
      <AlertDescription>
        <p>{error instanceof Error ? error.message : "Unknown error"}</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

/** Empty state: what is missing and how to get it. */
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center">
      <Inbox aria-hidden className="size-8 text-muted-foreground" />
      <p className="font-medium">{title}</p>
      {children && <div className="text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}
