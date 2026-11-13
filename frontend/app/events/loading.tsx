import { EventCardSkeleton } from "@/components/events/event-card";

export default function EventsLoading() {
  return (
    <div className="page-shell">
      <div className="h-8 w-32 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-4 w-80 max-w-full animate-pulse rounded bg-muted" />
      <div className="mt-8 h-10 w-full animate-pulse rounded-md bg-muted" />
      <div className="mt-8 h-4 w-24 animate-pulse rounded bg-muted" />
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <EventCardSkeleton key={index} />
        ))}
      </div>
    </div>
  );
}
