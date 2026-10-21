import type { Metadata } from "next";

import AdminAnimeManagement from "@/components/admin/admin_anime_management";
import AdminLoginSetting from "@/components/admin/admin_login_setting";
import AdminUsersTable from "@/components/admin/admin_users_table";

export const metadata: Metadata = {
    title: "Admin - HitoriBocchi",
};

export default function AdminPage() {
    return (
        <main className="min-h-svh bg-home-background px-4 pt-5 pb-24 text-home-text sm:px-7 sm:pt-7 sm:pb-32 lg:px-10 xl:px-12 2xl:px-18">
            <div className="mx-auto w-full max-w-[120rem]">
                <header className="mb-6 border-b border-home-surface pb-3">
                    <h1 className="text-[1.375rem] font-semibold tracking-tight sm:text-[1.625rem]">
                        Admin Dashboard
                    </h1>
                    <p className="mt-1 text-sm text-home-muted">
                        Manage Users and Animes.
                    </p>
                </header>

                <AdminLoginSetting />
                <AdminAnimeManagement />
                <AdminUsersTable />
            </div>
        </main>
    );
}
