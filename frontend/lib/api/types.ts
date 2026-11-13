import type { components } from "@/types/api";

export type AuthResponse = components["schemas"]["AuthResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type UserRead = components["schemas"]["UserRead"];
export type UserRole = components["schemas"]["UserRole"];

export type AuthSession = {
  access_token: string;
  expires_in: number;
  user: UserRead;
};

export type EventRead = components["schemas"]["EventRead"];
export type EventDetailRead = components["schemas"]["EventDetailRead"];
export type EventListResponse = components["schemas"]["EventListResponse"];
export type EventSortField = components["schemas"]["EventSortField"];
export type SortOrder = components["schemas"]["SortOrder"];
export type CategoryRead = components["schemas"]["CategoryRead"];
export type TagRead = components["schemas"]["TagRead"];

export type EventQuery = {
  page?: number;
  size?: number;
  search?: string;
  category?: string;
  tag?: string[];
  date_from?: string;
  date_to?: string;
  price_min?: number;
  price_max?: number;
  sort?: EventSortField;
  order?: SortOrder;
};
