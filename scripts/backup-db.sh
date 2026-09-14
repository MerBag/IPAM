#!/usr/bin/env sh
set -eu

merbag_backup_dir=${1:-./backups}
merbag_timestamp=$(date -u +%Y%m%dT%H%M%SZ)
merbag_backup_file="${merbag_backup_dir}/merbag-${merbag_timestamp}.dump"

mkdir -p -- "$merbag_backup_dir"
umask 077
merbag_temp_file=$(mktemp "${merbag_backup_file}.tmp.XXXXXX")

merbag_cleanup() {
    rm -f -- "$merbag_temp_file"
}
trap merbag_cleanup EXIT HUP INT TERM

docker compose exec -T postgres sh -ec \
    'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom --no-owner --no-acl' \
    > "$merbag_temp_file"

if [ ! -s "$merbag_temp_file" ]; then
    printf '%s\n' "Backup failed: pg_dump produced an empty file." >&2
    exit 1
fi

mv -- "$merbag_temp_file" "$merbag_backup_file"
trap - EXIT HUP INT TERM
printf '%s\n' "Database backup created at ${merbag_backup_file}"
