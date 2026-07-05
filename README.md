# templatize-project

`templatize_project.py` converts an Android Studio project into a
[Code On the Go](https://codeonthego.app/) (`.cgt`) template by applying the
substitutions described in "Template Creation and Installation":

- Replaces concrete values (Gradle/AGP/Kotlin versions, package name, app
  name, SDK levels, Java compatibility levels) with Pebble tokens
  (`${{ TOKEN }}`).
- Saves each modified file with a `.peb` suffix and removes the original.
- Removes `build/` directories.
- Deletes common keystore files (`*.jks`, `*.keystore`, `*.p12`) and flags
  other files that may contain machine-specific or personal information
  (`local.properties`, `google-services.json`, `key.properties`,
  `GoogleService-Info.plist`) for manual review.

Both Kotlin DSL (`build.gradle.kts`) and Groovy DSL (`build.gradle`) projects
are supported.

## Usage

```
python templatize_project.py <path-to-android-project> [--module app] [--dry-run] [--skip-cleanup]
```

- `--module` — app module directory name (default: `app`)
- `--dry-run` — show what would change without writing or deleting anything
- `--skip-cleanup` — skip `build/` and keystore removal

## Files processed

- `gradle/wrapper/gradle-wrapper.properties` — Gradle version
- `settings.gradle.kts` — `rootProject.name`
- `build.gradle.kts` / `build.gradle` (root) — AGP version
- `<module>/build.gradle.kts` / `build.gradle` — AGP/Kotlin plugin versions,
  namespace, applicationId, compileSdk, minSdk, targetSdk, Java source/target
  compatibility, `kotlinOptions.jvmTarget`
- `<module>/src/main/res/values/strings.xml` — `app_name`
- `<module>/src/main/java/MainActivity.kt` / `MainActivity.java` — package
  name

## Pebble whitespace quirk

A line/segment that ends with a Pebble token must be followed by at least
one character of whitespace, or the parser eats the next character (often a
newline, quote, semicolon, or dot). The script inserts a sacrificial space
after every inserted token — after the closing quote when the token is
immediately followed by one, so the quote itself isn't eaten.

## Next steps

After running the script, inspect each generated `.peb` file to confirm the
substitutions and spacing look right, then package the directory into a
`.cgt` file:

```
zip -r -9 -D -X <destination>/<filename>.cgt *
```
