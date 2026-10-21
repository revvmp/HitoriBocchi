import type { Metadata } from "next";
import Link from "next/link";

import AuthPage from "@/components/auth/auth_page";
import RegisterForm from "@/components/auth/register_form";

export const metadata: Metadata = {
    title: "Register - HitoriBocchi",
    description: "Create a HitoriBocchi account.",
};

export default function RegisterPage() {
    return (
        <AuthPage
            title="Create account"
            subtitle="Register"
            footer={
                <>
                    Already have an account?{" "}
                    <Link
                        className="font-medium text-auth-text underline underline-offset-2"
                        href="/login"
                    >
                        Sign in
                    </Link>
                </>
            }
        >
            <RegisterForm />
        </AuthPage>
    );
}
