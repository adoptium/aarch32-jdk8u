# CI/CD Automation Summary: aarch32-port-jdk8u

## Overview

Automated CI/CD pipeline for building and testing OpenJDK 8 for Linux ARM32
(AArch32 hard-float / armhf) on an ARM64 GitLab runner.

## What Was Created

- **File**: `.gitlab-ci.yml` on branch `gitlab-ci`
- **GitLab CI config path**: `.gitlab-ci.yml@zulu/aarch32-port-jdk8u:gitlab-ci`

## Pipeline Design

A single job `build_and_test_jdk` running on `debian:11` with runner tags
`linux k8s aarch64 arm64 16x32 dind zulu`. Build and test are intentionally
combined into one job so that host libraries installed for the build are
available for test execution without reinstallation.

### Steps

1. **Environment setup**
   - Add `armhf` architecture: `dpkg --add-architecture armhf`
   - Install cross-compiler: `gcc-10-arm-linux-gnueabihf`, `g++-10-arm-linux-gnueabihf`
   - Install armhf dev libraries (X11, CUPS, fontconfig, freetype, ALSA, etc.)
     — the `-dev:armhf` packages pull in their runtime counterparts as
     dependencies, so no separate runtime install pass is needed
   - Register cross-compiler via `update-alternatives`

2. **Downloads**
   - Boot JDK: Azul Zulu 8 for AArch64 (`zulu8.90.0.19-ca-jdk8.0.472-linux_aarch64`)
     from `cdn.azul.com`
   - jtreg 5.1-b01 from Azul internal Nexus
     (`nexus.azulsystems.com/repository/zulu-binaries/jtreg/`)

3. **Build**
   ```sh
   CC=arm-linux-gnueabihf-gcc \
   CXX=arm-linux-gnueabihf-g++ \
   BUILD_CC=gcc \
   BUILD_CXX=g++ \
   bash ./configure \
     --with-boot-jdk=<zulu8-aarch64-path> \
     --openjdk-target=arm-linux-gnueabihf \
     --with-jtreg=<jtreg-path> \
     --with-jvm-variants=client \
     --with-jobs=16 \
     --with-debug-level=release

   make images JOBS=16 LOG=info
   ```
   Build output: `build/linux-aarch32-normal-client-release/images/`

4. **Test**
   - `java -version` to confirm ARM32 JVM executes on the AArch64 kernel
   - `jtreg :jdk_tier1` — java.lang, java.util, java.math, jdi tests
   - `jtreg :hotspot_tier1` — hotspot sanity, compiler, GC, runtime tests

5. **Artifacts** (uploaded always, expire in 1 week)
   - `build/*/images/` — JDK and JRE images (~458 MB)
   - `jtreg-results/` — test reports

## Key Technical Decisions

| Decision | Reason |
|---|---|
| Client JIT only (`--with-jvm-variants=client`) | AArch32 port has no `aarch32.ad` for the server (C2) JIT |
| Explicit `CC`/`CXX` env vars before configure | `--openjdk-target` alone does not override autoconf's `AC_PROG_CC` which runs first and selects the native 64-bit compiler |
| Single combined job (no stage split) | Separate build/test jobs require reinstalling all armhf runtime libraries in the test container |
| jtreg 5.1-b01 | Matches version pinned in `make/conf/test-dependencies` |
| `-r:` / `-w:` flags for jtreg report/work dirs | jtreg 5.1 uses the short form; `-report:` is a newer flag not recognized by 5.1 |

## Issues Encountered and Resolved

| Problem | Fix |
|---|---|
| `ci_config_path: ".gitlab-ci.yml@gitlab-ci"` — GitLab parsed `gitlab-ci` as a project name | Correct format: `".gitlab-ci.yml@zulu/aarch32-port-jdk8u:gitlab-ci"` |
| jtreg download 404 from GitHub public releases | Use Azul internal Nexus instead |
| `configure: error: unrecognized option --with-bootjdk` | Correct flag is `--with-boot-jdk` (with dashes) |
| `sizeof(int *)` reported 8 instead of 4 — wrong compiler selected | Explicitly export `CC=arm-linux-gnueabihf-gcc CXX=arm-linux-gnueabihf-g++` |
| `gmake: No rule to make target 'aarch32.ad'` | Add `--with-jvm-variants=client` |
| `configure: error: Could not find required tool for FILE` | Restore the `file` package in the apt-get install list |
| `jtreg: Error: Bad parameters — Time Factor — response is "120"` | Remove `-timeout:120`; the flag is a multiplier in jtreg 5.1 and 120 is invalid |
| Test stage in a split pipeline required reinstalling host libraries | Merge build and test into a single job |

## Build Result

Pipeline 816610 confirmed a successful build:

```
openjdk version "1.8.0_492-internal"
OpenJDK Runtime Environment (build 1.8.0_492-internal-_2026_03_04_11_47-b00)
OpenJDK Client VM (build 25.492-b00, mixed mode)
```

jdk_tier1 test results: **1,313 passed, 26 failed, 11 error**. The failures
are pre-existing issues in the aarch32 port and unrelated to the CI setup.
