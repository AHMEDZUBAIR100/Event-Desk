import { CalendarDays, MapPin } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { EventRead } from "@/lib/api/types";
import {
  formatPrice,
  formatShortEventDate,
} from "@/lib/format";
import { cn } from "@/lib/utils";

export function EventCard({ event }: { event: EventRead }) {
  const soldOut = event.tickets_available <= 0;

  return (
    <article
      className={cn(
        "group relative flex h-full flex-col rounded-lg border bg-card p-5 transition-colors",
        "hover:border-foreground/30 focus-within:border-foreground/30",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <Badge>{event.category?.name ?? "Event"}</Badge>
        <span className="text-xs text-muted-foreground">
          {soldOut ? "Sold out" : `${event.tickets_available} left`}
        </span>
      </div>

      <h3 className="mt-4 text-[17px] font-medium leading-snug tracking-tight">
        <Link
          href={`/events/${event.id}`}
          className="after:absolute after:inset-0 focus:outline-none"
        >
          {event.title}
        </Link>
      </h3>

      <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
        {event.description}
      </p>

      <dl className="mt-5 space-y-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <dt className="sr-only">Date</dt>
          <dd>{formatShortEventDate(event.starts_at)}</dd>
        </div>
        <div className="flex items-center gap-2">
          <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <dt className="sr-only">Venue</dt>
          <dd className="truncate">{event.venue}</dd>
        </div>
      </dl>

      <div className="mt-auto flex items-end justify-between gap-3 border-t pt-4">
        <p>
          <span className="text-sm font-medium">{formatPrice(event.price)}</span>
          <span className="ml-1.5 text-xs text-muted-foreground">
            per ticket
          </span>
        </p>
        <span className="text-xs text-muted-foreground">
          {soldOut ? "Unavailable" : "View details"}
        </span>
      </div>
    </article>
  );
}

export function EventCardSkeleton() {
  return (
    <div className="flex h-full flex-col rounded-lg border p-5">
      <div className="flex items-center justify-between">
        <div className="h-5 w-20 animate-pulse rounded-full bg-muted" />
        <div className="h-3 w-14 animate-pulse rounded bg-muted" />
      </div>
      <div className="mt-4 h-5 w-4/5 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-4 w-full animate-pulse rounded bg-muted" />
      <div className="mt-2 h-4 w-2/3 animate-pulse rounded bg-muted" />
      <div className="mt-5 space-y-2">
        <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
        <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
      </div>
      <div className="mt-6 flex items-center justify-between border-t pt-4">
        <div className="h-4 w-20 animate-pulse rounded bg-muted" />
        <div className="h-3 w-16 animate-pulse rounded bg-muted" />
      </div>
    </div>
  );
}
