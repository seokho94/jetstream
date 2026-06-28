/** @type {import('next').NextConfig} */
const nextConfig = {
  // shared/ is TS source consumed directly; let Next transpile it.
  transpilePackages: ["@meridian/shared"],
  reactStrictMode: true,
};

export default nextConfig;
