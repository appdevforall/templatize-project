#!/usr/bin/env python3
"""
templatize_project.py

Converts an Android Studio project into a Code On the Go (.cgt) template
by applying the changes described in "Template Creation and Installation":

  - Substitutes concrete values (versions, package name, app name, sdk
    levels, java compat levels) in the affected files with Pebble tokens
    (${{ TOKEN }}).
  - Saves each modified file with a .peb suffix and removes the original.
  - Removes build/ directories.
  - Deletes common keystore files and flags other files that may contain
    personal information for manual review.

IMPORTANT Pebble quirk handled throughout: a line/segment that ends with
a Pebble token must be followed by at least one space, or the parser will
eat the next character (often a newline, quote, semicolon, or dot). This
script inserts a single "sacrificial" space after every inserted token
(two spaces for the rootProject.name line, per the explicit note in the
source document) so the character that follows survives rendering.

Usage:
    python templatize_project.py <path-to-android-project> [--module app] [--dry-run]
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

TOKEN = "{name} "  # placeholder, formatted per-use as ${{{{{name}}}}}


def token(name: str) -> str:
    return "${{" + name + "}}"


class Report:
    def __init__(self):
        self.changed = []
        self.skipped = []
        self.removed = []
        self.flagged = []

    def ok(self, msg):
        self.changed.append(msg)
        print(f"  [OK]      {msg}")

    def skip(self, msg):
        self.skipped.append(msg)
        print(f"  [SKIP]    {msg}")

    def remove(self, msg):
        self.removed.append(msg)
        print(f"  [REMOVED] {msg}")

    def flag(self, msg):
        self.flagged.append(msg)
        print(f"  [REVIEW]  {msg}")


def write_peb(path: Path, new_text: str, report: Report, dry_run: bool):
    peb_path = path.with_name(path.name + ".peb")
    report.ok(f"{path} -> {peb_path.name}")
    if dry_run:
        return
    with open(peb_path, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    path.unlink()


def sub_line_end_token(text: str, pattern: str, repl_token_name: str,
                        trailing_spaces: int = 1):
    """
    Replace the value in group 2 of `pattern` with a Pebble token,
    inserting `trailing_spaces` sacrificial spaces right after the token
    (before whatever originally followed it on that line). `pattern` must
    have exactly three capturing groups: (prefix)(value-to-replace)(suffix).
    Always applied with re.MULTILINE so ^/$ anchors in patterns match
    per-line rather than only at the start/end of the whole file.
    """
    tok = token(repl_token_name)

    def _repl(m):
        return m.group(1) + tok + (" " * trailing_spaces) + m.group(3)

    new_text, n = re.subn(pattern, _repl, text, flags=re.MULTILINE)
    return new_text, n


def process_gradle_wrapper(project_dir: Path, report: Report, dry_run: bool):
    path = project_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not path.exists():
        report.skip(f"{path} not found")
        return
    text = path.read_text(encoding="utf-8")
    new_text, n = sub_line_end_token(
        text,
        r"(distributionUrl=https\\://services\.gradle\.org/distributions/gradle-)([^-\s]+)(-bin\.zip)",
        "GRADLE_VERSION",
    )
    if n == 0:
        report.skip(f"{path}: distributionUrl pattern not found, no changes made")
        return
    write_peb(path, new_text, report, dry_run)


def process_settings_gradle(project_dir: Path, report: Report, dry_run: bool):
    path = project_dir / "settings.gradle.kts"
    if not path.exists():
        report.skip(f"{path} not found")
        return
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    n = 0
    for i, line in enumerate(lines):
        m = re.match(r'^([ \t]*rootProject\.name[ \t]*=[ \t]*")([^"]*)("[ \t]*)(\r?\n)?$', line)
        if m:
            newline = m.group(4) or ""
            lines[i] = f'{m.group(1)}{token("APP_NAME")}"  {newline}'
            n += 1
    if n == 0:
        report.skip(f"{path}: rootProject.name pattern not found, no changes made")
        return
    write_peb(path, "".join(lines), report, dry_run)


def process_root_build_gradle(project_dir: Path, report: Report, dry_run: bool):
    path = project_dir / "build.gradle.kts"
    if not path.exists():
        report.skip(f"{path} not found")
        return
    text = path.read_text(encoding="utf-8")
    new_text, n = sub_line_end_token(
        text,
        r'(id\("com\.android\.(?:application|library)"\)\s+apply\s+false\s+version\s+")([^"]+)(")',
        "AGP_VERSION",
    )
    if n == 0:
        report.skip(f"{path}: no 'apply false version' plugin lines found, no changes made")
        return
    report.ok(f"{path}: replaced {n} AGP version occurrence(s)")
    write_peb(path, new_text, report, dry_run)


def process_app_build_gradle(project_dir: Path, module: str, report: Report, dry_run: bool):
    path = project_dir / module / "build.gradle.kts"
    if not path.exists():
        report.skip(f"{path} not found")
        return
    text = path.read_text(encoding="utf-8")
    total = 0

    # com.android.application plugin version
    text, n = sub_line_end_token(
        text,
        r'(id\("com\.android\.application"\)\s+version\s+")([^"]+)(")',
        "AGP_VERSION",
    )
    total += n

    # kotlin("android") plugin version, wrapped in a Pebble LANGUAGE conditional
    kotlin_pattern = re.compile(
        r'^([ \t]*)kotlin\("android"\)\s+version\s+"([^"]+)"[ \t]*\r?\n?',
        re.MULTILINE,
    )
    m = kotlin_pattern.search(text)
    if m:
        indent = m.group(1)
        replacement = (
            f'{indent}${{% if LANGUAGE == \'kotlin\' %}} \n'
            f'{indent}kotlin("android") version "{token("KOTLIN_VERSION")} "\n'
            f'{indent}${{% endif %}} \n'
        )
        text = text[:m.start()] + replacement + text[m.end():]
        total += 1
        report.ok(f"{path}: wrapped kotlin(\"android\") plugin in LANGUAGE conditional")
    else:
        report.skip(f"{path}: kotlin(\"android\") plugin line not found (ok for Java-only projects)")

    text, n = sub_line_end_token(text, r'(namespace\s*=\s*")([^"]+)(")', "PACKAGE_NAME")
    total += n
    text, n = sub_line_end_token(text, r'(compileSdk\s*=\s*)(\d+)()', "COMPILE_SDK")
    total += n
    text, n = sub_line_end_token(text, r'(applicationId\s*=\s*")([^"]+)(")', "PACKAGE_NAME")
    total += n
    text, n = sub_line_end_token(text, r'(minSdk\s*=\s*)(\d+)()', "MIN_SDK")
    total += n
    text, n = sub_line_end_token(text, r'(targetSdk\s*=\s*)(\d+)()', "TARGET_SDK")
    total += n
    text, n = sub_line_end_token(
        text, r'(sourceCompatibility\s*=\s*)(JavaVersion\.\w+|[\d.]+)()', "JAVA_SOURCE_COMPAT"
    )
    total += n
    text, n = sub_line_end_token(
        text, r'(targetCompatibility\s*=\s*)(JavaVersion\.\w+|[\d.]+)()', "JAVA_TARGET_COMPAT"
    )
    total += n

    if total == 0:
        report.skip(f"{path}: no recognized patterns found, no changes made")
        return
    report.ok(f"{path}: made {total} substitution(s)")
    write_peb(path, text, report, dry_run)


def process_strings_xml(project_dir: Path, module: str, report: Report, dry_run: bool):
    path = project_dir / module / "src" / "main" / "res" / "values" / "strings.xml"
    if not path.exists():
        report.skip(f"{path} not found")
        return
    text = path.read_text(encoding="utf-8")
    new_text, n = sub_line_end_token(
        text,
        r'(<string name="app_name">)([^<]*)(</string>)',
        "APP_NAME",
    )
    if n == 0:
        report.skip(f"{path}: app_name string not found, no changes made")
        return
    write_peb(path, new_text, report, dry_run)


def process_main_activity_kt(project_dir: Path, module: str, report: Report, dry_run: bool):
    path = project_dir / module / "src" / "main" / "java" / "MainActivity.kt"
    if not path.exists():
        report.skip(f"{path} not found (ok if this project is Java-only)")
        return
    text = path.read_text(encoding="utf-8")
    pkg_match = re.search(r'^package\s+([\w.]+)\s*$', text, re.MULTILINE)
    if not pkg_match:
        report.skip(f"{path}: package declaration not found, no changes made")
        return
    package_name = pkg_match.group(1)

    text, n = sub_line_end_token(text, r'^(package\s+)([\w.]+)([ \t]*)$', "PACKAGE_NAME")
    total = n

    # Optional: import <package>.databinding.XxxBinding
    import_pattern = re.compile(
        rf'^(import\s+){re.escape(package_name)}(\.databinding\.\w+)([ \t]*)$',
        re.MULTILINE,
    )
    text, n2 = import_pattern.subn(
        lambda m: f'{m.group(1)}{token("PACKAGE_NAME")} {m.group(2)}{m.group(3)}',
        text,
    )
    total += n2

    if total == 0:
        report.skip(f"{path}: no substitutions made")
        return
    report.ok(f"{path}: made {total} substitution(s)")
    write_peb(path, text, report, dry_run)


def process_main_activity_java(project_dir: Path, module: str, report: Report, dry_run: bool):
    path = project_dir / module / "src" / "main" / "java" / "MainActivity.java"
    if not path.exists():
        report.skip(f"{path} not found (ok if this project is Kotlin-only)")
        return
    text = path.read_text(encoding="utf-8")
    pkg_match = re.search(r'^package[ \t]+([\w.]+)[ \t]*;[ \t]*$', text, re.MULTILINE)
    if not pkg_match:
        report.skip(f"{path}: package declaration not found, no changes made")
        return
    package_name = pkg_match.group(1)

    # package <pkg>; -> package ${{PACKAGE_NAME}} ;
    # (space before the semicolon protects it from being eaten)
    text, n = re.subn(
        r'^(package[ \t]+)([\w.]+)([ \t]*;[ \t]*)$',
        lambda m: f'{m.group(1)}{token("PACKAGE_NAME")} ;',
        text,
        flags=re.MULTILINE,
    )
    total = n

    import_pattern = re.compile(
        rf'^(import[ \t]+){re.escape(package_name)}(\.databinding\.\w+)([ \t]*;[ \t]*)$',
        re.MULTILINE,
    )
    text, n2 = import_pattern.subn(
        lambda m: f'{m.group(1)}{token("PACKAGE_NAME")} {m.group(2)};',
        text,
    )
    total += n2

    if total == 0:
        report.skip(f"{path}: no substitutions made")
        return
    report.ok(f"{path}: made {total} substitution(s)")
    write_peb(path, text, report, dry_run)


def cleanup_build_dirs(project_dir: Path, report: Report, dry_run: bool):
    # Match both the original files and any already-renamed .peb versions,
    # since this runs after the file substitution steps.
    module_roots = set()
    for pattern in ("build.gradle.kts", "build.gradle",
                    "build.gradle.kts.peb", "build.gradle.peb"):
        module_roots |= {p.parent for p in project_dir.rglob(pattern)}
    module_roots.add(project_dir)
    for mod in sorted(module_roots):
        build_dir = mod / "build"
        if build_dir.is_dir():
            report.remove(str(build_dir))
            if not dry_run:
                shutil.rmtree(build_dir)


def cleanup_keystores(project_dir: Path, report: Report, dry_run: bool):
    patterns = ["*.jks", "*.keystore", "*.p12"]
    for pattern in patterns:
        for f in project_dir.rglob(pattern):
            report.remove(str(f))
            if not dry_run:
                f.unlink()


def flag_personal_info_files(project_dir: Path, report: Report):
    candidates = ["local.properties", "google-services.json", "key.properties",
                  "GoogleService-Info.plist"]
    for name in candidates:
        for f in project_dir.rglob(name):
            report.flag(f"{f} may contain machine-specific or personal information; review/delete manually")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project_dir", type=Path, help="Path to the Android Studio project root")
    parser.add_argument("--module", default="app", help="App module directory name (default: app)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing/deleting anything")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip build/ and keystore removal")
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    report = Report()

    print(f"\n=== Templatizing {project_dir} ===\n")
    if args.dry_run:
        print("(dry run: no files will be modified)\n")

    print("-- gradle/wrapper/gradle-wrapper.properties --")
    process_gradle_wrapper(project_dir, report, args.dry_run)

    print("\n-- settings.gradle.kts --")
    process_settings_gradle(project_dir, report, args.dry_run)

    print("\n-- build.gradle.kts (root) --")
    process_root_build_gradle(project_dir, report, args.dry_run)

    print(f"\n-- {args.module}/build.gradle.kts --")
    process_app_build_gradle(project_dir, args.module, report, args.dry_run)

    print(f"\n-- {args.module}/src/main/res/values/strings.xml --")
    process_strings_xml(project_dir, args.module, report, args.dry_run)

    print(f"\n-- {args.module}/src/main/java/MainActivity.kt --")
    process_main_activity_kt(project_dir, args.module, report, args.dry_run)

    print(f"\n-- {args.module}/src/main/java/MainActivity.java --")
    process_main_activity_java(project_dir, args.module, report, args.dry_run)

    if not args.skip_cleanup:
        print("\n-- Removing build/ directories --")
        cleanup_build_dirs(project_dir, report, args.dry_run)

        print("\n-- Removing keystore files --")
        cleanup_keystores(project_dir, report, args.dry_run)

        print("\n-- Flagging files that may contain personal information --")
        flag_personal_info_files(project_dir, report)

    print("\n=== Summary ===")
    print(f"  Modified:  {len(report.changed)}")
    print(f"  Skipped:   {len(report.skipped)}")
    print(f"  Removed:   {len(report.removed)}")
    print(f"  To review: {len(report.flagged)}")
    print(
        "\nNext step: inspect each generated .peb file to confirm the Pebble "
        "substitutions and spacing look right, then package the directory "
        "into a .cgt file, e.g.:\n"
        "  zip -r -9 -D -X <destination>/<filename>.cgt *\n"
    )


if __name__ == "__main__":
    main()
