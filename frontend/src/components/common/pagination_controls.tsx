"use client";

type PaginationControlsProps = {
  disabled?: boolean;
  hasMore: boolean;
  onPageChange: (page: number) => void;
  page: number;
};

export default function PaginationControls({
  disabled = false,
  hasMore,
  onPageChange,
  page,
}: PaginationControlsProps) {
  if (page === 1 && !hasMore) {
    return null;
  }

  return (
    <nav
      aria-label="Pagination"
      className="mt-8 flex items-center justify-center gap-4"
    >
      <button
        className="min-w-24 rounded-md border border-home-surface bg-home-surface/30 px-4 py-2 text-sm font-semibold text-home-text transition hover:border-home-accent hover:bg-home-surface disabled:cursor-not-allowed disabled:opacity-50"
        disabled={disabled || page === 1}
        onClick={() => onPageChange(page - 1)}
        type="button"
      >
        Previous
      </button>

      <span
        aria-live="polite"
        className="min-w-16 text-center text-sm font-medium text-home-muted"
      >
        Page {page}
      </span>

      <button
        className="min-w-24 rounded-md border border-home-surface bg-home-surface/30 px-4 py-2 text-sm font-semibold text-home-text transition hover:border-home-accent hover:bg-home-surface disabled:cursor-not-allowed disabled:opacity-50"
        disabled={disabled || !hasMore}
        onClick={() => onPageChange(page + 1)}
        type="button"
      >
        Next
      </button>
    </nav>
  );
}
