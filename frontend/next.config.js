const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
module.exports = {
  compress: false, // keep streamed answers unbuffered
  experimental: { proxyTimeout: 180000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/:path*` }];
  },
};
