"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AnimeNavbarSearch from "@/components/layout/anime_navbar_search";
import MangaNavbarSearch from "@/components/layout/manga_navbar_search";
import NavbarSectionMenu from "@/components/layout/navbar_section_menu";
import {
  getOptionalCurrentUser,
  getSiteSettings,
  logout,
  type CurrentUser,
} from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

const animeLinks = [
  { href: "/", label: "Home" },
  { href: "/continue-watching", label: "Continue Watching" },
  { href: "/ongoing", label: "Ongoing" },
  { href: "/popular", label: "Popular" },
  { href: "/hits", label: "Hits" },
];

const mangaLinks = [
  { href: "/manga", label: "Home" },
  { href: "/manga/bookmarks", label: "Bookmarks" },
  { href: "/manga/ongoing", label: "Ongoing" },
  { href: "/manga/popular", label: "Popular" },
  { href: "/manga/hits", label: "Hits" },
];

function getLinkClassName(isActive: boolean) {
  return `whitespace-nowrap rounded-md px-4 py-2.5 text-base font-medium transition hover:bg-home-surface hover:text-home-text ${
    isActive
      ? "bg-home-surface text-home-accent ring-1 ring-inset ring-home-accent/60"
      : "text-home-muted"
  }`;
}

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loginRequired, setLoginRequired] = useState(true);
  const [isSessionLoading, setIsSessionLoading] = useState(true);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const isAuthPage = pathname === "/login" || pathname === "/register";
  const isMangaSection = pathname === "/manga" || pathname.startsWith("/manga/");
  const currentHome = isMangaSection ? "/manga" : "/";
  const links = isMangaSection ? mangaLinks : animeLinks;
  const adminHref = isMangaSection ? "/manga/admin" : "/admin";

  useEffect(() => {
    if (isAuthPage) {
      return;
    }

    let isActive = true;

    Promise.all([getSiteSettings(), getOptionalCurrentUser()])
      .then(([settings, currentUser]) => {
        if (!isActive) {
          return;
        }

        setLoginRequired(settings.login_required);
        setUser(currentUser);

        if (settings.login_required && !currentUser) {
          router.replace("/login");
        }
      })
      .catch((error) => {
        if (
          isActive &&
          error instanceof ApiError &&
          [401, 403].includes(error.status)
        ) {
          router.replace("/login");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsSessionLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [isAuthPage, router]);

  async function handleLogout() {
    setIsLoggingOut(true);

    try {
      await logout();
      setUser(null);
      router.replace(loginRequired ? "/login" : currentHome);
      router.refresh();
    } finally {
      setIsLoggingOut(false);
    }
  }

  if (isAuthPage) {
    return null;
  }

  return (
    <header className="sticky top-0 z-50 border-b border-home-surface bg-home-background/95 px-4 text-home-text backdrop-blur sm:px-7 lg:px-10 xl:px-12 2xl:px-18">
      <div className="mx-auto grid min-h-16 w-full max-w-[120rem] grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-2 py-2.5 sm:flex sm:flex-nowrap sm:gap-x-4">
        <NavbarSectionMenu isMangaSection={isMangaSection} />

        <Link
          className="col-start-2 row-start-1 flex shrink-0 items-center gap-2"
          href={currentHome}
          aria-label={`HitoriBocchi ${isMangaSection ? "manga" : "anime"} home`}
        >
          <Image
            src="/bocchi_slug.png"
            alt=""
            width={44}
            height={44}
            preload
            className="size-11 object-contain"
          />
          <span className="hidden text-lg font-semibold md:inline">
            HitoriBocchi
          </span>
          <span className="hidden rounded-sm border border-home-accent/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-home-accent xl:inline-flex">
            {isMangaSection ? "Manga" : "Anime"}
          </span>
        </Link>

        <nav
          aria-label={`${isMangaSection ? "Manga" : "Anime"} navigation`}
          className="col-span-4 col-start-1 row-start-2 flex w-full min-w-0 items-center gap-2 overflow-x-auto sm:w-auto sm:flex-1 sm:gap-3"
        >
          {links.map((link) => (
            <Link
              aria-current={pathname === link.href ? "page" : undefined}
              className={getLinkClassName(pathname === link.href)}
              href={link.href}
              key={link.label}
            >
              {link.label}
            </Link>
          ))}

          {user?.is_admin === 1 && (
            <Link
              aria-current={pathname === adminHref ? "page" : undefined}
              className={getLinkClassName(pathname === adminHref)}
              href={adminHref}
            >
              Admin
            </Link>
          )}
        </nav>

        {isMangaSection ? (
          <MangaNavbarSearch key="manga-search" />
        ) : (
          <AnimeNavbarSearch key="anime-search" />
        )}

        {isSessionLoading ? (
          <span
            aria-label="Loading account"
            className="col-start-4 row-start-1 size-10 shrink-0 animate-pulse rounded-md bg-home-surface sm:w-20"
          />
        ) : (
          user ? (
            <button
              type="button"
              disabled={isLoggingOut}
              onClick={handleLogout}
              aria-label={isLoggingOut ? "Logging out" : "Log out"}
              className="col-start-4 row-start-1 flex size-10 shrink-0 items-center justify-center rounded-md bg-home-text text-sm font-semibold text-home-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 sm:h-auto sm:w-auto sm:px-4 sm:py-2.5 sm:text-base"
            >
              <svg
                aria-hidden="true"
                className="size-5 sm:hidden"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
              >
                <path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10" />
              </svg>
              <span className="hidden sm:inline">
                {isLoggingOut ? "Logging out..." : "Logout"}
              </span>
            </button>
          ) : (
            <Link
              aria-label="Sign in"
              className="col-start-4 row-start-1 flex size-10 shrink-0 items-center justify-center rounded-md bg-home-text text-sm font-semibold text-home-background transition hover:opacity-90 sm:h-auto sm:w-auto sm:px-4 sm:py-2.5 sm:text-base"
              href={`/login?next=${encodeURIComponent(pathname)}`}
            >
              <svg
                aria-hidden="true"
                className="size-5 sm:hidden"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
              >
                <circle cx="12" cy="8" r="3" />
                <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
              </svg>
              <span className="hidden sm:inline">Sign in</span>
            </Link>
          )
        )}
      </div>
    </header>
  );
}
