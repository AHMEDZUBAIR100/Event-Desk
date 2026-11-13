import type { Metadata } from "next";

import { EventsCatalogue } from "@/components/events/events-catalogue";

export const metadata: Metadata = {
  title: "Events",
  description: "Browse published events on EventDesk.",
};

export default function EventsPage() {
  return <EventsCatalogue />;
}
