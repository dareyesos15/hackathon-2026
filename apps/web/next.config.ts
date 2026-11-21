import type { NextConfig } from "next";

// Frontend puro (constitución, principio X): exportación estática servida por Nginx.
// Sin servidor Next.js, sin Route Handlers ni Server Actions.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
