"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, CalendarDays, MapPin, Tag } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { getEvent } from "@/lib/api/events";
import {
  formatAvailability,
  formatEventDate,
  formatPrice,
} from "@/lib/format";

function DetailSkeleton() {
  return (
    <div className="page-shell">
      <Skeleton className="h-4 w-24" />
      <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          <Skeleton className="h-5 w-24 rounded-full" />
          <Skeleton className="mt-4 h-9 w-3/4" />
          <Skeleton className="mt-3 h-4 w-40" />
          <div className="mt-8 border-y py-6">
            <Skeleton className="h-4 w-full" />
          </div>
          <Skeleton className="mt-8 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-2/3" />
        </div>
        <div>
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-3 h-8 w-40" />
          <Skeleton className="mt-6 h-10 w-full" />
        </div>
      </div>
    </div>
  );
}

export function EventDetail() {
  const params = useParams<{ id: string }>();
  const eventId = params.id;

  const query = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId),
    enabled: Boolean(eventId),
    retry: false,
  });

  if (query.isLoading) {
    return <DetailSkeleton />;
  }

  if (query.isError || !query.data) {
    const notFound =
      query.error instanceof ApiError && query.error.status === 404;

    return (
      <div className="page-shell">
        <Button variant="ghost" size="sm" asChild className="-ml-3">
          <Link href="/events">
            <ArrowLeft className="h-4 w-4" />
            All events
          </Link>
        </Button>
        <Alert variant="destructive" className="mt-8 max-w-xl">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>
            {notFound ? "Event not found" : "Could not load this event"}
          </AlertTitle>
          <AlertDescription>
            {notFound
              ? "This event may have been removed or is no longer published."
              : "Please try again in a moment."}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const event = query.data;
  const soldOut = event.tickets_available <= 0;

  return (
    <div className="page-shell">
      <Button variant="ghost" size="sm" asChild className="-ml-3">
        <Link href="/events">
          <ArrowLeft className="h-4 w-4" />
          All events
        </Link>
      </Button>

      <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-16">
        <article>
          <div className="flex flex-wrap items-center gap-2">
            {event.category ? (
              <Badge>{event.category.name}</Badge>
            ) : (
              <Badge>Event</Badge>
            )}
            {event.tags?.map((tag) => (
              <Badge key={tag.id}>
                <Tag className="mr-1 h-3 w-3" aria-hidden="true" />
                {tag.name}
              </Badge>
            ))}
          </div>

          <h1 className="mt-4 text-[2rem] font-semibold leading-tight tracking-tight">
            {event.title}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Hosted by {event.organizer.full_name}
          </p>

          <dl className="mt-8 grid gap-x-8 gap-y-5 border-y py-6 sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted-foreground">Date</dt>
              <dd className="mt-1 flex items-start gap-2 text-sm">
                <CalendarDays
                  className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                {formatEventDate(event.starts_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Venue</dt>
              <dd className="mt-1 flex items-start gap-2 text-sm">
                <MapPin
                  className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                {event.venue}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Price</dt>
              <dd className="mt-1 text-sm">
                {formatPrice(event.price)}
                <span className="ml-1 text-muted-foreground">per ticket</span>
              </dd>
            </div>
          </dl>

          <section className="mt-8">
            <h2 className="text-section-title tracking-tight">
              About this event
            </h2>
            <p className="mt-3 max-w-2xl whitespace-pre-line text-[15px] leading-7 text-muted-foreground">
              {event.description}
            </p>
          </section>
        </article>

        <aside className="lg:pt-24">
          <div className="border-t pt-6 lg:border-t-0 lg:pt-0">
            <p className="text-xs text-muted-foreground">Availability</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight">
              {formatAvailability(
                event.tickets_available,
                event.total_tickets,
              )}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {event.tickets_available > 0
                ? "Tickets are released when booking opens."
                : "This event has no tickets remaining."}
            </p>

            <Separator className="my-6" />

            <Button type="button" className="w-full" disabled>
              {soldOut ? "Sold out" : "Book tickets"}
            </Button>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              {soldOut
                ? "Find another event in the catalogue."
                : "Ticket booking for this event is not open yet."}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
