#!/usr/bin/env bash

set -euo pipefail

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: apply.sh [--check] [--source PATH]

Validate and apply the ordered Nexus 6P platform patch series to a clean,
freshly synced official LineageOS 22.2 checkout. --check performs the complete
validation in temporary clones and does not modify the source tree.
EOF
}

mode=apply
source_root=$PWD

while [ "$#" -gt 0 ]; do
    case "$1" in
        --check)
            mode=check
            shift
            ;;
        --source)
            [ "$#" -ge 2 ] || die '--source requires a path'
            source_root=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

source_root=$(cd "$source_root" 2>/dev/null && pwd -P) ||
    die "source directory does not exist: $source_root"
kit_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
lock_file=$kit_root/projects.tsv

[ -d "$source_root/.repo" ] || die "not an Android repo checkout: $source_root"
[ -f "$lock_file" ] || die "missing lock file: $lock_file"

build_id_file=$source_root/build/make/core/build_id.mk
[ -f "$build_id_file" ] || die "missing build ID file: $build_id_file"
build_id=$(sed -n 's/^[[:space:]]*BUILD_ID[[:space:]]*=[[:space:]]*//p' \
    "$build_id_file" | tail -n 1)
[ "$build_id" = BP1A.250505.005 ] ||
    die "unsupported BUILD_ID: ${build_id:-unknown}; expected BP1A.250505.005"

declare -a project_paths=()
declare -a patch_directories=()

while IFS=$'\t' read -r project_path patch_directory extra; do
    case "$project_path" in
        ''|'#'*) continue ;;
    esac
    [ -z "${extra:-}" ] || die "invalid extra field in projects.tsv: $project_path"
    [ -n "$patch_directory" ] ||
        die "incomplete projects.tsv entry: $project_path"
    case "$project_path" in
        /*|*'..'*) die "unsafe project path: $project_path" ;;
    esac
    case "$patch_directory" in
        /*|*'..'*) die "unsafe patch path: $patch_directory" ;;
    esac
    project_paths+=("$project_path")
    patch_directories+=("$patch_directory")
done < "$lock_file"

[ "${#project_paths[@]}" -gt 0 ] || die 'projects.tsv contains no projects'

declare -a states=()
declare -a original_heads=()
declare -a validated_trees=()

series_is_at_head() {
    local project_directory=$1
    shift
    local patches=("$@")
    local patch_count=${#patches[@]}
    local commits=()
    local patch_index commit_index patch_id commit_id

    mapfile -t commits < <(
        git -C "$project_directory" rev-list --max-count="$patch_count" HEAD
    )
    [ "${#commits[@]}" -eq "$patch_count" ] || return 1

    for patch_index in "${!patches[@]}"; do
        commit_index=$((patch_count - patch_index - 1))
        patch_id=$(git patch-id --stable < "${patches[$patch_index]}" |
            awk 'NR == 1 { print $1 }')
        commit_id=$(git -C "$project_directory" show --pretty=format: --no-ext-diff \
            "${commits[$commit_index]}" | git patch-id --stable |
            awk 'NR == 1 { print $1 }')
        [ -n "$patch_id" ] && [ "$patch_id" = "$commit_id" ] || return 1
    done
}

series_matches_worktree() {
    local project_directory=$1
    shift
    local patches=("$@")
    local temporary_clone patch_index

    temporary_clone=$(mktemp -d)
    if ! git -c advice.detachedHead=false clone --quiet --shared \
            "$project_directory" "$temporary_clone/project"; then
        rm -rf "$temporary_clone"
        return 1
    fi

    for ((patch_index=${#patches[@]} - 1; patch_index >= 0; patch_index--)); do
        if ! git -C "$temporary_clone/project" apply --reverse --check \
                "${patches[$patch_index]}" >/dev/null 2>&1 ||
                ! git -C "$temporary_clone/project" apply --reverse \
                "${patches[$patch_index]}" >/dev/null 2>&1; then
            rm -rf "$temporary_clone"
            return 1
        fi
    done
    for patch_index in "${!patches[@]}"; do
        if ! git -C "$temporary_clone/project" apply --check \
                "${patches[$patch_index]}" >/dev/null 2>&1 ||
                ! git -C "$temporary_clone/project" apply \
                "${patches[$patch_index]}" >/dev/null 2>&1; then
            rm -rf "$temporary_clone"
            return 1
        fi
    done

    if ! git -C "$temporary_clone/project" diff --quiet --exit-code; then
        rm -rf "$temporary_clone"
        return 1
    fi
    rm -rf "$temporary_clone"
}

for index in "${!project_paths[@]}"; do
    project_path=${project_paths[$index]}
    patch_directory=${patch_directories[$index]}
    project_directory=$source_root/$project_path
    series_directory=$kit_root/$patch_directory

    [ -d "$project_directory/.git" ] || [ -f "$project_directory/.git" ] ||
        die "missing Git project: $project_path"
    [ -d "$series_directory" ] || die "missing patch directory: $patch_directory"

    if [ -n "$(git -C "$project_directory" status --porcelain=v1 --untracked-files=normal)" ]; then
        die "dirty repository: $project_path"
    fi
    [ ! -d "$(git -C "$project_directory" rev-parse --git-path rebase-apply)" ] ||
        die "unfinished git am operation: $project_path"

    shopt -s nullglob
    patches=("$series_directory"/*.patch)
    shopt -u nullglob
    [ "${#patches[@]}" -gt 0 ] || die "empty patch series: $patch_directory"

    current_head=$(git -C "$project_directory" rev-parse HEAD)
    current_tree=$(git -C "$project_directory" rev-parse 'HEAD^{tree}')
    original_heads+=("$current_head")
    if series_is_at_head "$project_directory" "${patches[@]}" ||
            series_matches_worktree "$project_directory" "${patches[@]}"; then
        states+=(applied)
        validated_trees+=("$current_tree")
        continue
    fi

    temporary_clone=$(mktemp -d)
    if ! git -c advice.detachedHead=false clone --quiet --shared \
            "$project_directory" "$temporary_clone/project"; then
        rm -rf "$temporary_clone"
        die "cannot create validation clone: $project_path"
    fi
    git -C "$temporary_clone/project" config user.name 'Nexus 6P Patch Kit'
    git -C "$temporary_clone/project" config user.email 'nexus6p-patches@localhost'
    git -C "$temporary_clone/project" config advice.detachedHead false
    git -C "$temporary_clone/project" checkout --quiet --detach "$current_head"
    if ! git -C "$temporary_clone/project" am --quiet --3way "${patches[@]}"; then
        rm -rf "$temporary_clone"
        die "patch preflight failed: $project_path"
    fi
    if ! git -C "$temporary_clone/project" diff --check "$current_head"..HEAD; then
        rm -rf "$temporary_clone"
        die "patch introduces whitespace errors: $project_path"
    fi
    validated_tree=$(git -C "$temporary_clone/project" rev-parse 'HEAD^{tree}')
    rm -rf "$temporary_clone"
    states+=(applicable)
    validated_trees+=("$validated_tree")
done

if [ "$mode" = check ]; then
    for index in "${!project_paths[@]}"; do
        if [ "${states[$index]}" = applied ]; then
            printf 'already applied: %s\n' "${project_paths[$index]}"
        else
            printf 'applicable: %s\n' "${project_paths[$index]}"
        fi
    done
    exit 0
fi

for index in "${!project_paths[@]}"; do
    project_path=${project_paths[$index]}
    if [ "${states[$index]}" = applied ]; then
        printf 'already applied: %s\n' "$project_path"
        continue
    fi
    project_directory=$source_root/$project_path
    current_head=$(git -C "$project_directory" rev-parse HEAD)
    [ "$current_head" = "${original_heads[$index]}" ] ||
        die "repository changed after preflight: $project_path"
    series_directory=$kit_root/${patch_directories[$index]}
    shopt -s nullglob
    patches=("$series_directory"/*.patch)
    shopt -u nullglob
    if ! git -C "$project_directory" am --quiet --3way "${patches[@]}"; then
        git -C "$project_directory" am --abort >/dev/null 2>&1 || true
        die "patch application failed and was rolled back: $project_path"
    fi
    applied_tree=$(git -C "$project_directory" rev-parse 'HEAD^{tree}')
    [ "$applied_tree" = "${validated_trees[$index]}" ] ||
        die "unexpected result tree after apply: $project_path"
    printf 'applied: %s\n' "$project_path"
done
