#!/bin/sh
set -eu

current_uid=$(id -u)
if [ "$current_uid" -eq 0 ]; then
    printf '%s\n' "Run this setup as the local account, not root." >&2
    exit 1
fi

repo_root=$(realpath "$(git rev-parse --show-toplevel)")
state_home=$(realpath -m "${XDG_STATE_HOME:-"$HOME/.local/state"}")
simulation_dir=$state_home/reading-hub/production-simulation
case "$simulation_dir" in
    "$repo_root"|"$repo_root"/*)
        printf '%s\n' "Simulation state must be outside the repository." >&2
        exit 1
        ;;
esac

for path in "$simulation_dir" "$simulation_dir/data" "$simulation_dir/tls"; do
    if [ -L "$path" ]; then
        printf '%s\n' "Simulation paths must not be symlinks." >&2
        exit 1
    fi
done
mkdir -p "$simulation_dir/data" "$simulation_dir/tls"
for path in "$simulation_dir" "$simulation_dir/data" "$simulation_dir/tls"; do
    if [ -L "$path" ]; then
        printf '%s\n' "Simulation paths must not be symlinks." >&2
        exit 1
    fi
    chmod 700 "$path"
done

certificate=$simulation_dir/tls/server.crt
private_key=$simulation_dir/tls/server.key
if [ -L "$certificate" ] || [ -L "$private_key" ]; then
    printf '%s\n' "TLS files must not be symlinks." >&2
    exit 1
fi
if [ -e "$certificate" ] || [ -e "$private_key" ] || [ -L "$certificate" ] || [ -L "$private_key" ]; then
    if [ ! -f "$certificate" ] || [ ! -f "$private_key" ]; then
        printf '%s\n' "An incomplete TLS key pair exists; refusing to replace it." >&2
        exit 1
    fi
    openssl x509 -in "$certificate" -noout -checkhost localhost >/dev/null
    openssl x509 -in "$certificate" -noout -checkhost read.shabang.ch >/dev/null
else
    umask 077
    openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 365 \
        -keyout "$private_key" \
        -out "$certificate" \
        -subj "/CN=read.shabang.ch" \
        -addext "subjectAltName=DNS:read.shabang.ch,DNS:localhost,IP:127.0.0.1"
fi
chmod 600 "$private_key"
chmod 644 "$certificate"

environment_file=$simulation_dir/compose.env
if [ -L "$environment_file" ]; then
    printf '%s\n' "The Compose environment file must not be a symlink." >&2
    exit 1
fi
if [ -e "$environment_file" ] && [ ! -f "$environment_file" ]; then
    printf '%s\n' "The Compose environment path must be a regular file." >&2
    exit 1
fi
if [ ! -e "$environment_file" ]; then
    umask 077
    {
        printf 'READING_HUB_SIMULATION_DIR="%s"\n' "$simulation_dir"
        printf 'READING_HUB_SIMULATION_UID=%s\n' "$current_uid"
        printf 'READING_HUB_SIMULATION_GID=%s\n' "$(id -g)"
        printf 'READING_HUB_SIMULATION_HTTPS_PORT=8444\n'
    } > "$environment_file"
fi
chmod 600 "$environment_file"

printf 'Simulation state: %s\n' "$simulation_dir"
printf 'Compose settings: %s\n' "$environment_file"
