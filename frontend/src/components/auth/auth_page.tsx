import Image from "next/image";
import type { ReactNode } from "react";

type AuthPageProps = {
  children: ReactNode;
  footer: ReactNode;
  subtitle: string;
  title: string;
};

export default function AuthPage({
  children,
  footer,
  subtitle,
  title,
}: AuthPageProps) {
  return (
    <main className="relative isolate flex min-h-svh flex-col overflow-y-auto bg-auth-background px-4 py-4 font-sans sm:px-6">
      <Image
        src="/bocchi_wallpaper.webp"
        alt=""
        fill
        priority
        sizes="100vw"
        className="-z-20 object-cover object-center"
      />

      <div
        aria-hidden="true"
        className="auth-page-overlay absolute inset-0 -z-10"
      />

      <section className="m-auto w-full max-w-sm rounded-2xl border border-auth-border bg-auth-surface p-5 shadow-2xl backdrop-blur-xl sm:p-6">
        <div className="mb-5 flex flex-col items-center text-center">
          <div className="mb-3 rounded-full border border-auth-border bg-auth-border p-1 shadow-lg">
            <Image
              src="/bocchi_slug.png"
              alt="Bocchi slug"
              width={96}
              height={96}
              priority
              className="size-16 rounded-full object-cover sm:size-20"
            />
          </div>

          <p className="mb-1 text-xs font-bold uppercase tracking-[0.2em] text-auth-text">
            HitoriBocchi
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-auth-text sm:text-3xl">
            {title}
          </h1>
          <p className="mt-1 text-sm leading-5 text-auth-muted">{subtitle}</p>
        </div>

        {children}

        <div className="mt-4 text-center text-xs leading-4 text-auth-muted">
          {footer}
        </div>
      </section>
    </main>
  );
}
