import type { NextConfig } from "next";

  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:5000";

  const nextConfig: NextConfig = {
    reactCompiler: true,
    images: {
      qualities: [75, 90, 95, 100],
      remotePatterns: [
        {
          protocol: "https",
          hostname: "cdn.myanimelist.net",
          pathname: "/images/**",
        },
      ],
    },

    async rewrites() {
      return [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/:path*`,
        },
      ];
    },
  };

  export default nextConfig;
