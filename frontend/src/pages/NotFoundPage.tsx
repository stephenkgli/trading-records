import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <svg
        width="48"
        height="48"
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--color-text-muted)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="opacity-50"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <p className="text-[--color-text-primary] text-lg font-medium">
        404 &mdash; Page not found
      </p>
      <p className="text-[--color-text-muted] text-sm">
        The page you are looking for does not exist.
      </p>
      <Link
        to="/"
        className="text-sm text-accent hover:text-accent-hover transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none rounded"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
