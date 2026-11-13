"use client";

import { Search, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  CategoryRead,
  EventSortField,
  SortOrder,
  TagRead,
} from "@/lib/api/types";

export type CatalogueFilters = {
  search: string;
  category: string;
  tags: string[];
  dateFrom: string;
  dateTo: string;
  priceMin: string;
  priceMax: string;
  sort: EventSortField;
  order: SortOrder;
};

export const emptyFilters: CatalogueFilters = {
  search: "",
  category: "all",
  tags: [],
  dateFrom: "",
  dateTo: "",
  priceMin: "",
  priceMax: "",
  sort: "date",
  order: "asc",
};

const sortOptions = [
  { value: "date:asc", label: "Date · soonest" },
  { value: "date:desc", label: "Date · latest" },
  { value: "price:asc", label: "Price · low to high" },
  { value: "price:desc", label: "Price · high to low" },
];

export function countActiveFilters(filters: CatalogueFilters): number {
  let count = 0;
  if (filters.category !== "all") count += 1;
  if (filters.tags.length > 0) count += filters.tags.length;
  if (filters.dateFrom) count += 1;
  if (filters.dateTo) count += 1;
  if (filters.priceMin) count += 1;
  if (filters.priceMax) count += 1;
  return count;
}

type CatalogueFiltersProps = {
  filters: CatalogueFilters;
  categories: CategoryRead[];
  tags: TagRead[];
  onChange: (patch: Partial<CatalogueFilters>) => void;
  onReset: () => void;
  activeCount: number;
};

export function CatalogueFilterBar({
  filters,
  categories,
  tags,
  onChange,
  onReset,
  activeCount,
}: CatalogueFiltersProps) {
  const [expanded, setExpanded] = useState(false);

  function toggleTag(slug: string, checked: boolean) {
    const nextTags = checked
      ? [...filters.tags, slug]
      : filters.tags.filter((tag) => tag !== slug);
    onChange({ tags: nextTags });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            value={filters.search}
            onChange={(event) => onChange({ search: event.target.value })}
            placeholder="Search events by title"
            aria-label="Search events by title"
            className="pl-9"
          />
        </div>

        <div className="grid grid-cols-2 gap-3 md:flex">
          <Select
            value={filters.category}
            onValueChange={(value) => onChange({ category: value })}
          >
            <SelectTrigger className="md:w-[180px]" aria-label="Category">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((category) => (
                <SelectItem key={category.id} value={category.slug}>
                  {category.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={`${filters.sort}:${filters.order}`}
            onValueChange={(value) => {
              const [sort, order] = value.split(":") as [
                EventSortField,
                SortOrder,
              ];
              onChange({ sort, order });
            }}
          >
            <SelectTrigger className="md:w-[190px]" aria-label="Sort events">
              <SelectValue placeholder="Sort" />
            </SelectTrigger>
            <SelectContent>
              {sortOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          type="button"
          variant="secondary"
          onClick={() => setExpanded((current) => !current)}
          aria-expanded={expanded}
          className="justify-center md:w-auto"
        >
          <SlidersHorizontal className="h-4 w-4" />
          Filters
          {activeCount > 0 ? (
            <Badge variant="default" className="ml-1 px-1.5 py-0">
              {activeCount}
            </Badge>
          ) : null}
        </Button>
      </div>

      {expanded ? (
        <div className="rounded-md border p-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <Label htmlFor="date-from">From</Label>
              <Input
                id="date-from"
                type="date"
                value={filters.dateFrom}
                onChange={(event) => onChange({ dateFrom: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="date-to">To</Label>
              <Input
                id="date-to"
                type="date"
                value={filters.dateTo}
                onChange={(event) => onChange({ dateTo: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="price-min">Minimum price</Label>
              <Input
                id="price-min"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                placeholder="0"
                value={filters.priceMin}
                onChange={(event) =>
                  onChange({ priceMin: event.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="price-max">Maximum price</Label>
              <Input
                id="price-max"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                placeholder="Any"
                value={filters.priceMax}
                onChange={(event) =>
                  onChange({ priceMax: event.target.value })
                }
              />
            </div>
          </div>

          {tags.length > 0 ? (
            <div className="mt-5 border-t pt-4">
              <p className="text-sm font-medium">Tags</p>
              <div className="mt-3 flex max-h-32 flex-wrap gap-x-6 gap-y-3 overflow-y-auto">
                {tags.map((tag) => (
                  <label
                    key={tag.id}
                    htmlFor={`tag-${tag.slug}`}
                    className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground"
                  >
                    <Checkbox
                      id={`tag-${tag.slug}`}
                      checked={filters.tags.includes(tag.slug)}
                      onCheckedChange={(checked) =>
                        toggleTag(tag.slug, checked === true)
                      }
                    />
                    {tag.name}
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          {activeCount > 0 ? (
            <div className="mt-4 flex justify-end">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onReset}
              >
                <X className="h-3.5 w-3.5" />
                Clear filters
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
