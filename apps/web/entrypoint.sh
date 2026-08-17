#!/bin/sh
# Force Next.js standalone server to bind on all interfaces.
# App Runner overrides the HOSTNAME environment variable with the container's
# internal hostname (e.g. ip-10-0-x-x.us-west-2.compute.internal), which causes
# server.js to bind to that specific IP only. The App Runner health-check probe
# then connects to 127.0.0.1 and gets ECONNREFUSED.
# Explicitly setting HOSTNAME=0.0.0.0 here wins over the runtime injection.
export HOSTNAME="0.0.0.0"
exec node server.js
