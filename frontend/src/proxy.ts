import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:5000";

async function getLoginRequired() {
    try {
        const response = await fetch(new URL("/site-settings", backendUrl), {
            cache: "no-store",
        });

        if (!response.ok) {
            return true;
        }

        const settings = await response.json() as { login_required?: boolean };
        return settings.login_required !== false;
    } catch {
        return true;
    }
}

export async function proxy(request: NextRequest) {
    const hasSession = request.cookies.has("csrf_refresh_token");
    const isAuthPage =
        request.nextUrl.pathname === "/login" ||
        request.nextUrl.pathname === "/register";
    const isAdminPage =
        request.nextUrl.pathname.startsWith("/admin") ||
        request.nextUrl.pathname.startsWith("/manga/admin");

    if (isAdminPage && !hasSession) {
        const loginUrl = new URL("/login", request.url);
        loginUrl.searchParams.set("next", request.nextUrl.pathname);
        return NextResponse.redirect(loginUrl);
    }

    if (isAdminPage) {
        return NextResponse.next();
    }

    if (isAuthPage) {
        return NextResponse.next();
    }

    const loginRequired = await getLoginRequired();

    if (!hasSession && loginRequired) {
        return NextResponse.redirect(new URL("/login", request.url));
    }

    return NextResponse.next();
}

export const config = {
    matcher: [
        "/",
        "/admin/:path*",
        "/anime/:path*",
        "/continue-watching/:path*",
        "/hits/:path*",
        "/login",
        "/manga/:path*",
        "/ongoing/:path*",
        "/popular/:path*",
        "/register",
        "/search/:path*",
        "/watch/:path*",
    ],
};
