const dateFormatter = new Intl.DateTimeFormat("en", {
  weekday: "short",
  month: "short",
  day: "numeric",
  year: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat("en", {
  hour: "numeric",
  minute: "2-digit",
});

const shortDateFormatter = new Intl.DateTimeFormat("en", {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

const priceFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatEventDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Date to be announced";
  }

  return `${dateFormatter.format(date)} · ${timeFormatter.format(date)}`;
}

export function formatShortEventDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Date to be announced";
  }

  return shortDateFormatter.format(date);
}

export function formatPrice(value: string): string {
  const amount = Number(value);

  if (Number.isNaN(amount)) {
    return value;
  }

  return priceFormatter.format(amount);
}

export function formatAvailability(available: number, total: number): string {
  if (available <= 0) {
    return "Sold out";
  }

  if (available <= 10) {
    return `${available} ${available === 1 ? "ticket" : "tickets"} left`;
  }

  return `${available} of ${total} available`;
}

export function formatRole(role: string): string {
  return role.charAt(0).toUpperCase() + role.slice(1);
}

export function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}
