#!/usr/bin/env bash
#
# Pull whatever CI last built, migrate, restart — and do nothing at all when
# nothing has changed.
#
# **Why the server pulls instead of GitHub pushing.** The firewall denies
# inbound except 80, 443 and the tailnet, and GitHub's runners are on none of
# those. The alternatives are opening SSH to the internet or joining every CI
# run to the tailnet with a long-lived key; both hand a deploy credential to a
# third party to save a couple of minutes. This needs no inbound access, no
# secret in GitHub, and it heals itself: a box that was down for a day catches
# up on its next tick without anyone re-running a pipeline.
#
#   sudo install -m 755 update.sh /usr/local/bin/va-platform-update
#
# Idempotent, safe to run as often as you like, and quiet when there is
# nothing to do — which matters, because it runs every few minutes forever.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/srv/va-platform}"
cd "$PROJECT_DIR"

log() { printf '%s va-platform-update: %s\n' "$(date -Is)" "$*"; }

# The digests we are running right now. Compared against what a pull brings
# down, because "did anything change" is the only question worth asking before
# restarting a browser someone is signed into.
current_digests() {
    docker compose config --images 2>/dev/null | sort -u | while read -r image; do
        docker image inspect --format '{{.Id}}' "$image" 2>/dev/null || echo "absent:$image"
    done
}

before="$(current_digests)"
before_ref="$(git rev-parse HEAD 2>/dev/null || true)"

# The repository, not only the images. Everything that decides *how* the app
# runs lives here rather than inside the container: which services exist, their
# memory limits, which environment variables reach them. Pulling images alone
# means a push that adds a service deploys perfectly and changes nothing, and
# the reason is invisible from every log you would think to check.
if [ -d .git ]; then
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        log "working tree has local changes — not pulling the repository"
    elif ! git pull --quiet --ff-only 2>&1; then
        log "GIT PULL FAILED — compose files are NOT being updated"
    fi
fi

if ! docker compose pull --quiet 2>/dev/null; then
    log "pull failed — leaving the running version alone"
    exit 1
fi

after="$(current_digests)"
after_ref="$(git rev-parse HEAD 2>/dev/null || true)"

if [ "$before" = "$after" ] && [ "$before_ref" = "$after_ref" ]; then
    exit 0
fi

log "new images, deploying"

# No migration step here, deliberately. This app creates its own schema on
# startup (`Base.metadata.create_all` in app/core/database.py) rather than
# using Alembic, so there is nothing to run first. If it ever gains proper
# migrations, they belong here — in a one-off container built from the *new*
# image, before anything serving restarts.

# --no-build because the images came from the registry; without it compose
# would notice the build: stanza and start compiling on the VPS.
docker compose up -d --no-build --remove-orphans

# Only images no container refers to. Left alone, a fortnight of daily builds
# is a full disk, and a full disk on this box stops Postgres before it stops
# anything you would notice.
docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true

log "deployed"
docker compose ps --format '  {{.Service}}\t{{.Status}}'
