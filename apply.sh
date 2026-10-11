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
official LineageOS 22.2 checkout. --check performs the complete validation in
temporary clones and does not modify the source tree.
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
declare -a baseline_commits=()
declare -a result_trees=()
declare -a patch_directories=()

while IFS=$'\t' read -r project_path baseline_commit result_tree patch_directory extra; do
    case "$project_path" in
        ''|'#'*) continue ;;
    esac
    [ -z "${extra:-}" ] || die "invalid extra field in projects.tsv: $project_path"
    [ -n "$baseline_commit" ] && [ -n "$result_tree" ] && [ -n "$patch_directory" ] ||
        die "incomplete projects.tsv entry: $project_path"
    case "$project_path" in
        /*|*'..'*) die "unsafe project path: $project_path" ;;
    esac
    case "$patch_directory" in
        /*|*'..'*) die "unsafe patch path: $patch_directory" ;;
    esac
    project_paths+=("$project_path")
    baseline_commits+=("$baseline_commit")
    result_trees+=("$result_tree")
    patch_directories+=("$patch_directory")
done < "$lock_file"

[ "${#project_paths[@]}" -gt 0 ] || die 'projects.tsv contains no projects'

declare -a states=()

for index in "${!project_paths[@]}"; do
    project_path=${project_paths[$index]}
    baseline_commit=${baseline_commits[$index]}
    result_tree=${result_trees[$index]}
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

    current_head=$(git -C "$project_directory" rev-parse HEAD)
    current_tree=$(git -C "$project_directory" rev-parse 'HEAD^{tree}')
    if [ "$current_tree" = "$result_tree" ]; then
        states+=(applied)
        continue
    fi
    [ "$current_head" = "$baseline_commit" ] ||
        die "baseline mismatch: $project_path (have $current_head, expected $baseline_commit)"

    shopt -s nullglob
    patches=("$series_directory"/*.patch)
    shopt -u nullglob
    [ "${#patches[@]}" -gt 0 ] || die "empty patch series: $patch_directory"

    temporary_clone=$(mktemp -d)
    if ! git clone --quiet --shared "$project_directory" "$temporary_clone/project"; then
        rm -rf "$temporary_clone"
        die "cannot create validation clone: $project_path"
    fi
    git -C "$temporary_clone/project" config user.name 'Nexus 6P Patch Kit'
    git -C "$temporary_clone/project" config user.email 'nexus6p-patches@localhost'
    git -C "$temporary_clone/project" checkout --quiet --detach "$baseline_commit"
    if ! git -C "$temporary_clone/project" am --quiet --3way "${patches[@]}"; then
        rm -rf "$temporary_clone"
        die "patch preflight failed: $project_path"
    fi
    if ! git -C "$temporary_clone/project" diff --check "$baseline_commit"..HEAD; then
        rm -rf "$temporary_clone"
        die "patch introduces whitespace errors: $project_path"
    fi
    validated_tree=$(git -C "$temporary_clone/project" rev-parse 'HEAD^{tree}')
    rm -rf "$temporary_clone"
    [ "$validated_tree" = "$result_tree" ] ||
        die "result tree mismatch after preflight: $project_path"
    states+=(applicable)
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
    series_directory=$kit_root/${patch_directories[$index]}
    shopt -s nullglob
    patches=("$series_directory"/*.patch)
    shopt -u nullglob
    if ! git -C "$project_directory" am --quiet --3way "${patches[@]}"; then
        git -C "$project_directory" am --abort >/dev/null 2>&1 || true
        die "patch application failed and was rolled back: $project_path"
    fi
    applied_tree=$(git -C "$project_directory" rev-parse 'HEAD^{tree}')
    [ "$applied_tree" = "${result_trees[$index]}" ] ||
        die "unexpected result tree after apply: $project_path"
    printf 'applied: %s\n' "$project_path"
done
