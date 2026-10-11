#!/usr/bin/env bash

set -euo pipefail

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

source_root=
while [ "$#" -gt 0 ]; do
    case "$1" in
        --source)
            [ "$#" -ge 2 ] || die '--source requires a path'
            source_root=$2
            shift 2
            ;;
        -h|--help)
            printf 'Usage: verify.sh --source ANDROID_BUILD_TOP\n'
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

[ -n "$source_root" ] || die '--source is required'
source_root=$(cd "$source_root" 2>/dev/null && pwd -P) ||
    die "source directory does not exist: $source_root"
[ -d "$source_root/.repo" ] || die "not an Android repo checkout: $source_root"

root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
export ANDROID_BUILD_TOP=$source_root

bash -n "$root/apply.sh" "$root/verify.sh"
python3 -m unittest discover -v -s "$root/tests"
"$root/apply.sh" --source "$source_root" --check
git -C "$root" diff --check

printf 'Nexus 6P patch-kit verification passed\n'
