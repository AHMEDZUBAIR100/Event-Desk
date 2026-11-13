"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { useMemo, useState } from "react";

import {
  CatalogueFilterBar,
  countActiveFilters,
  emptyFilters,
  type CatalogueFilters,
} from "@/components/events/catalogue-filters";
import { EventCard, EventCardSkeleton } from "@/components/events/event-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { getCategories, getEvents, getTags } from "@/lib/api/events";
import type { EventQuery } from "@/lib/api/types";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

const PAGE_SIZE = 12;

function toIsoStart(value: string): string | undefined {
  return value ? new Date(`${value}T00:00:00`).toISOString() : undefined;
}

function toIsoEnd(value: string): string | undefined {
  return value ? new Date(`${value}T23:59:59.999`).toISOString() : undefined;
}

function parsePrice(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const amount = Number(value);
  return Number.isFinite(amount) && amount >= 0 ? amount : undefined;
}

export function EventsCatalogue() {
  const [filters, setFilters] = useState<CatalogueFilters>(emptyFilters);
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(filters.search, 300);

  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: getCategories,
    staleTime: 5 * 60_000,
  });

  const tagsQuery = useQuery({
    queryKey: ["tags"],
    queryFn: getTags,
    staleTime: 5 * 60_000,
  });

  const query = useMemo<EventQuery>(
    () => ({
      page,
      size: PAGE_SIZE,
      search: debouncedSearch.trim() || undefined,
      category: filters.category === "all" ? undefined : filters.category,
      tag: filters.tags.length > 0 ? filters.tags : undefined,
      date_from: toIsoStart(filters.dateFrom),
      date_to: toIsoEnd(filters.dateTo),
      price_min: parsePrice(filters.priceMin),
      price_max: parsePrice(filters.priceMax),
      sort: filters.sort,
      order: filters.order,
    }),
    [
      page,
      debouncedSearch,
      filters.category,
      filters.tags,
      filters.dateFrom,
      filters.dateTo,
      filters.priceMin,
      filters.priceMax,
      filters.sort,
      filters.order,
    ],
  );

  const eventsQuery = useQuery({
    queryKey: ["events", query],
    queryFn: () => getEvents(query),
    placeholderData: keepPreviousData,
  });

  const activeCount = countActiveFilters(filters);
  const hasFilters = activeCount > 0 || filters.search.trim().length > 0;
  const total = eventsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const errorMessage =
    eventsQuery.error instanceof ApiError
      ? eventsQuery.error.message
      : "The event catalogue could not be loaded.";

  function updateFilters(patch: Partial<CatalogueFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  }

  function resetFilters() {
    setFilters(emptyFilters);
    setPage(1);
  }

  return (
    <div className="page-shell">
      <div className="max-w-2xl">
        <h1 className="text-page-title tracking-tight">Events</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground sm:text-base">
          Browse what is happening, compare the details, and find your next
          evening out.
        </p>
      </div>

      <div className="mt-8">
        <CatalogueFilterBar
          filters={filters}
          categories={categoriesQuery.data ?? []}
          tags={tagsQuery.data ?? []}
          onChange={updateFilters}
          onReset={resetFilters}
          activeCount={activeCount}
        />
      </div>

      <div className="mt-8 flex items-baseline justify-between gap-4 border-b pb-4">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {eventsQuery.isLoading
            ? "Loading events…"
            : `${total} ${total === 1 ? "event" : "events"}`}
          {eventsQuery.isFetching && !eventsQuery.isLoading
            ? " · Updating"
            : null}
        </p>
        {hasFilters ? (
          <button
            type="button"
            onClick={resetFilters}
            className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Reset
          </button>
        ) : null}
      </div>

      {eventsQuery.isError ? (
        <Alert variant="destructive" className="mt-6">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Could not load events</AlertTitle>
          <AlertDescription>
            <p>{errorMessage}</p>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-3"
              onClick={() => void eventsQuery.refetch()}
            >
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {eventsQuery.isLoading ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <EventCardSkeleton key={index} />
          ))}
        </div>
      ) : null}

      {!eventsQuery.isLoading && !eventsQuery.isError && total === 0 ? (
        <div className="mt-16 rounded-lg border border-dashed px-6 py-20 text-center">
          <p className="text-sm font-medium">No events found</p>
          <p className="mx-auto mt-1 max-w-sm text-sm leading-relaxed text-muted-foreground">
            {hasFilters
              ? "Try a different search or clear the filters to see everything that is on."
              : "New events will appear here as soon as organizers publish them."}
          </p>
          {hasFilters ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-4"
              onClick={resetFilters}
            >
              Clear filters
            </Button>
          ) : null}
        </div>
      ) : null}

      {!eventsQuery.isLoading && !eventsQuery.isError && total > 0 ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {eventsQuery.data?.items.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      ) : null}

      {!eventsQuery.isError && total > PAGE_SIZE ? (
        <nav
          className="mt-10 flex items-center justify-between border-t pt-5"
          aria-label="Pagination"
        >
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            Previous
          </Button>
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onClick={() =>
              setPage((current) => Math.min(totalPages, current + 1))
            }
          >
            Next
          </Button>
        </nav>
      ) : null}
    </div>
  );
}
