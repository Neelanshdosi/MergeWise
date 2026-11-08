const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname),
};

module.exports = nextConfig;
