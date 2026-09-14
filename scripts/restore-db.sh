#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
    printf '%s\n' "Usage: RESTORE_CONFIRM=REPLACE_MERBAG_DATABASE sh scripts/restore-db.sh BACKUP.dump" >&2
    exit 2
fi

if [ "${RESTORE_CONFIRM:-}" != "REPLACE_MERBAG_DATABASE" ]; then
    printf '%s\n' "Restore refused: this operation replaces the current database." >&2
    printf '%s\n' "Set RESTORE_CONFIRM=REPLACE_MERBAG_DATABASE after verifying the backup path." >&2
    exit 2
fi

merbag_restore_file=$1
merbag_archive_list=$(mktemp)
merbag_validation_db="merbag_restore_check_$$"
merbag_validation_created=0

merbag_cleanup() {
    if [ "$merbag_validation_created" -eq 1 ]; then
        docker compose exec -T postgres sh -ec \
            'dropdb --username="$POSTGRES_USER" --if-exists "$1"' sh "$merbag_validation_db" \
            >/dev/null 2>&1 || true
    fi
    rm -f -- "$merbag_archive_list"
}
trap merbag_cleanup EXIT HUP INT TERM

printf '%s\n' "Validating ${merbag_restore_file} before stopping the application..."
if ! docker compose exec -T postgres pg_restore --list < "$merbag_restore_file" > "$merbag_archive_list"; then
    printf '%s\n' "Restore refused: the selected file is not a readable PostgreSQL archive." >&2
    exit 1
fi

for merbag_required_table in alembic_version users prefixes subnets ip_addresses devices customers allocations audit_logs routers; do
    if ! grep -Eq "TABLE( DATA)? public ${merbag_required_table}([[:space:]]|$)" "$merbag_archive_list"; then
        printf '%s\n' "Restore refused: archive is missing merbag IPAM table ${merbag_required_table}." >&2
        exit 1
    fi
done

printf '%s\n' 'Restoring once into an isolated validation database...'
docker compose exec -T postgres sh -ec \
    'createdb --username="$POSTGRES_USER" "$1"' sh "$merbag_validation_db"
merbag_validation_created=1
if ! docker compose exec -T postgres sh -ec \
    'pg_restore --username="$POSTGRES_USER" --dbname="$1" --exit-on-error --no-owner --no-acl' \
    sh "$merbag_validation_db" < "$merbag_restore_file"; then
    printf '%s\n' 'Restore refused: archive failed the isolated test restore.' >&2
    exit 1
fi
docker compose exec -T postgres sh -ec \
    'dropdb --username="$POSTGRES_USER" "$1"' sh "$merbag_validation_db"
merbag_validation_created=0

printf '%s\n' "Stopping application traffic before restore..."
docker compose stop nginx backend

printf '%s\n' "Recreating the public schema..."
docker compose exec -T postgres sh -ec \
    'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --set=ON_ERROR_STOP=1 --command="DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION CURRENT_USER;"'

printf '%s\n' "Restoring ${merbag_restore_file}..."
docker compose exec -T postgres sh -ec \
    'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --exit-on-error --no-owner --no-acl' \
    < "$merbag_restore_file"

docker compose run --rm backend alembic upgrade head
docker compose up -d backend nginx
trap - EXIT HUP INT TERM
merbag_cleanup
printf '%s\n' "Restore completed and application services restarted."
