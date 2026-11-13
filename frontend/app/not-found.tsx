import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="page-shell flex flex-col items-start py-24">
      <p className="text-xs text-muted-foreground">404</p>
      <h1 className="mt-2 text-page-title tracking-tight">Page not found</h1>
      <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
        The page you were looking for does not exist or has moved.
      </p>
      <Button asChild className="mt-6">
        <Link href="/events">Browse events</Link>
      </Button>
    </div>
  );
}
