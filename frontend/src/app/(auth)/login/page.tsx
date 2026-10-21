import type { Metadata } from "next";
import Link from "next/link";

import AuthPage from "@/components/auth/auth_page";
import LoginForm from "@/components/auth/login_form";
import PublicHomeLink from "@/components/auth/public_home_link";

export const metadata: Metadata = {
    title: "Login - HitoriBocchi",
    description: "We are literally bocchi.",
};

export default function LoginPage() {
    return (
        <AuthPage
            title="Welcome back"
            subtitle="Sign in"
            footer={
                <>
                    New here?{" "}
                    <Link
                        className="font-medium text-auth-text underline underline-offset-2"
                        href="/register"
                    >
                        Create an account
                    </Link>
                </>
            }
        >
            <LoginForm />
            <PublicHomeLink />
        </AuthPage>
    );
}
