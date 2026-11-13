import { apiFetch } from "@/lib/api/client";
import type {
  CategoryRead,
  EventDetailRead,
  EventListResponse,
  EventQuery,
  TagRead,
} from "@/lib/api/types";

function toSearchParams(query: EventQuery): string {
  const params = new URLSearchParams();

  if (query.page) params.set("page", String(query.page));
  if (query.size) params.set("size", String(query.size));
  if (query.search) params.set("search", query.search);
  if (query.category) params.set("category", query.category);
  if (query.date_from) params.set("date_from", query.date_from);
  if (query.date_to) params.set("date_to", query.date_to);
  if (query.price_min !== undefined) {
    params.set("price_min", String(query.price_min));
  }
  if (query.price_max !== undefined) {
    params.set("price_max", String(query.price_max));
  }
  if (query.sort) params.set("sort", query.sort);
  if (query.order) params.set("order", query.order);

  for (const tag of query.tag ?? []) {
    params.append("tag", tag);
  }

  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}

export function getEvents(query: EventQuery = {}): Promise<EventListResponse> {
  return apiFetch<EventListResponse>(`/events${toSearchParams(query)}`);
}

export function getEvent(eventId: string): Promise<EventDetailRead> {
  return apiFetch<EventDetailRead>(`/events/${eventId}`);
}

export function getCategories(): Promise<CategoryRead[]> {
  return apiFetch<CategoryRead[]>("/categories");
}

export function getTags(): Promise<TagRead[]> {
  return apiFetch<TagRead[]>("/tags");
}
