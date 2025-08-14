#!/bin/sh
set -eu

PORT="${PORT:-80}"

# Simple default page (you can replace with your own)
printf '%s\n' "OK $(date -u)" > /usr/share/nginx/html/index.html

# Write a tiny nginx config that listens on the correct port
cat >/etc/nginx/conf.d/default.conf <<EOF
server {
    listen ${PORT};
    server_name _;
    root /usr/share/nginx/html;
    location / {
        try_files \$uri /index.html;
    }
}
EOF

echo "[entrypoint] starting nginx on :${PORT}"
exec nginx -g 'daemon off;'
