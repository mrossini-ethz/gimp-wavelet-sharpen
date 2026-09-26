#!/bin/sh
# Builds the plug-in into tests/output and runs tests/cases.py inside GIMP
# without a window. GIMP uses a throwaway profile in tests/output/profile
# (GIMP3_DIRECTORY) whose plug-in path adds the freshly built plug-in, so
# the installed plug-ins and the user's settings are not touched.
#
# With gimp-plugin-devtools next to this repo, the Flatpak GIMP is used if
# it is installed (the build runs in its SDK). Otherwise meson, ninja and
# gimp-console come from the system; set GIMP_CONSOLE to use another
# gimp-console, e.g. GIMP_CONSOLE=gimp-console-3.2.
#
# Extra meson options can be given, e.g. for a sanitizer build:
#   tests/run.sh -Db_sanitize=address,undefined
# WT_ONLY=<text> runs only the cases whose name contains the text.
#
# Prints PASS or FAIL for each case and exits non-zero on any failure.
set -e
here=$(cd "$(dirname "$0")" && pwd)
top=$(dirname "$here")
out="$here/output"
devtools="$top/../gimp-plugin-devtools"
if [ -f "$devtools/gimp-env.sh" ]; then
  . "$devtools/gimp-env.sh"
else
  GIMP_FLATPAK=0
fi

# runs a build command in the source folder
build () {
  if [ "$GIMP_FLATPAK" = 1 ]; then
    "$devtools/gimp-build.sh" "$top" "$@"
  else
    (cd "$top" && "$@")
  fi
}

rm -rf "$out"; mkdir -p "$out/profile"
build meson setup "$out/build" -Dplugindir="$out/plug-ins" "$@" > "$out/build.log" 2>&1 \
  || { cat "$out/build.log"; exit 1; }
build ninja -C "$out/build" install >> "$out/build.log" 2>&1 \
  || { cat "$out/build.log"; exit 1; }
printf '(plug-in-path "${gimp_dir}/plug-ins:${gimp_plug_in_dir}/plug-ins:%s")\n' "$out/plug-ins" > "$out/profile/gimprc"

# the environment of GIMP; the cases check the Polish translation
env="GIMP3_DIRECTORY=$out/profile WT_ONLY=$WT_ONLY LANGUAGE=pl"
# a sanitizer build writes the reports of the plug-in to
# tests/output/sanitizer.<pid>; with the Flatpak it needs the SDK at run
# time (libasan, libubsan)
devel= sanitize=
case "$*" in
  *b_sanitize=*)
    sanitize=1 devel=--devel
    env="$env ASAN_OPTIONS=log_path=$out/sanitizer:detect_leaks=1"
    env="$env UBSAN_OPTIONS=log_path=$out/sanitizer:print_stacktrace=1" ;;
esac
if [ "$GIMP_FLATPAK" = 1 ]; then
  set -- flatpak run $devel --filesystem="$top" \
    $(for e in $env; do echo "--env=$e"; done) \
    --command=gimp-console-$GIMP_SERIES org.gimp.GIMP
else
  set -- env $env "${GIMP_CONSOLE:-gimp-console}"
fi
set +e
"$@" --no-interface --no-data \
  --batch-interpreter python-fu-eval -b "exec(open('$here/cases.py').read())" --quit \
  > "$out/gimp.log" 2>&1
set -e
grep -E '^(PASS|FAIL|SKIP|RESULT)|Traceback|Error' "$out/gimp.log"
result=0
grep -q '^RESULT [0-9]* passed, 0 failed' "$out/gimp.log" || result=1
if [ -n "$sanitize" ]; then
  python3 "$here/sanitizer.py" "$out" || result=1
fi
exit $result
