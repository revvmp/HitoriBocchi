"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";

type NavbarSectionMenuProps = {
  isMangaSection: boolean;
};

type SectionOption = {
  description: string;
  href: string;
  icon: ReactNode;
  isManga: boolean;
  label: string;
};

const sectionOptions: SectionOption[] = [
  {
    description: "Watch episodes",
    href: "/",
    icon: (
      <svg
        aria-hidden="true"
        className="size-5"
        fill="none"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <rect height="14" rx="2" width="18" x="3" y="5" />
        <path d="m10 9 5 3-5 3z" />
      </svg>
    ),
    isManga: false,
    label: "Anime",
  },
  {
    description: "Read chapters",
    href: "/manga",
    icon: (
      <svg
        aria-hidden="true"
        className="size-5"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z" />
        <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z" />
      </svg>
    ),
    isManga: true,
    label: "Manga",
  },
];

// The switcher to the left of the logo changes between the anime and manga catalogs.
export default function NavbarSectionMenu({
  isMangaSection,
}: NavbarSectionMenuProps) {
  const sectionMenuRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (
        sectionMenuRef.current &&
        !sectionMenuRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <div
      className="relative col-start-1 row-start-1 shrink-0"
      ref={sectionMenuRef}
    >
      <button
        aria-controls="media-section-menu"
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-label="Switch between Anime and Manga"
        className={`flex size-10 items-center justify-center rounded-md border transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent ${
          isOpen
            ? "border-home-accent bg-home-surface text-home-accent"
            : "border-home-surface text-home-muted hover:border-home-accent hover:bg-home-surface hover:text-home-text"
        }`}
        onClick={() => setIsOpen((currentIsOpen) => !currentIsOpen)}
        type="button"
      >
        <svg
          aria-hidden="true"
          className="size-5"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
          viewBox="0 0 24 24"
        >
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>

      {isOpen && (
        <div
          aria-label="Choose website section"
          className="absolute top-[calc(100%+0.5rem)] left-0 z-[70] w-64 overflow-hidden rounded-lg border border-home-surface bg-home-background p-2 shadow-2xl"
          id="media-section-menu"
          role="menu"
        >
          <p className="px-2 pt-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-home-muted">
            Browse HitoriBocchi
          </p>
          {sectionOptions.map((option, index) => {
            const isSelected = option.isManga === isMangaSection;

            return (
              <Link
                aria-current={isSelected ? "page" : undefined}
                className={`${index > 0 ? "mt-1 " : ""}flex items-center gap-3 rounded-md px-3 py-2.5 outline-none transition focus-visible:ring-2 focus-visible:ring-home-accent ${
                  isSelected
                    ? "bg-home-surface text-home-accent"
                    : "text-home-muted hover:bg-home-surface/60 hover:text-home-text"
                }`}
                href={option.href}
                key={option.href}
                onClick={() => setIsOpen(false)}
                role="menuitem"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-home-surface">
                  {option.icon}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">{option.label}</span>
                  <span className="block text-xs text-home-muted">
                    {option.description}
                  </span>
                </span>
                {isSelected && (
                  <span aria-label="Selected" className="text-home-accent">✓</span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
