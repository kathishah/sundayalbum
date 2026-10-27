

const nextConfig = {
  output: 'standalone',
  images: {
    // Interim mitigation: the app uses no next/image (all <img> tags use their
    // src directly), so switch the /_next/image optimiser off. Remove this once
    // Next is on a patched 15.5.x and the image advisories no longer apply.
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.s3.us-west-2.amazonaws.com',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 's3.us-west-2.amazonaws.com',
        port: '',
        pathname: '/**',
      },
    ],
  },
}

export default nextConfig
