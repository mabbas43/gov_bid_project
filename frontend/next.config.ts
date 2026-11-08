import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false, // the badge covers the demo toggle in the sidebar
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
