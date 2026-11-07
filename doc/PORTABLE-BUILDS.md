# Playable portable builds

All compilation and packaging run on GitHub-hosted runners. No local tools are needed.

The default branch push starts .github/workflows/build.yml. You can also use Actions > Build playable Linux and Windows ZIPs > Run workflow. The pinned content commit is set in CONTENT_SHA; update it deliberately alongside source changes.

The workflow builds release binaries for Linux x86-64 (Ubuntu 22.04 baseline) and Windows x86-64 (MinGW64), bundles the complete content repository, recursively collects runtime libraries/DLLs, and includes licenses, exact game source, dependency package versions and file checksums. The Windows profile uses upstream's documented libsystre dependency for POSIX regex support.

The exact ZIPs are extracted and checksum-checked on fresh runners. Windows startup runs with only System32 on the game's PATH, without MSYS2 installed. Linux startup runs on Ubuntu 22.04 and 24.04 containers with Xvfb and no SDL/development packages installed. Startup tests exercise software rendering for 25 seconds; they do not establish full gameplay, audio, hardware acceleration or controller compatibility.

After all checks pass, the publish job creates a uniquely tagged prerelease containing exactly two playable ZIP assets and SHA-256 checksums in the release notes. ZIPs are also retained as Actions artifacts for 30 days. If a startup test fails, the ZIPs remain available from the successful build jobs, but no release is published. Failed steps print diagnostics in Actions.

Download a platform ZIP, extract the complete folder, and run Play.cmd (Windows) or ./Play.sh (Linux). On Linux, use chmod +x Play.sh UrQuanMasters if the extractor loses executable permissions. Linux requires glibc 2.35+ and host graphics/audio facilities; it does not support every possible Linux distribution. Saves remain in the game's normal per-user configuration directory.

Content includes base, HD, 3DO voices and optional DOS/3DO modes; the game chooses assets according to setup preferences. The content license is documented in content/README.md. Code and bundled libraries retain their own licenses. Package versions are recorded, but the OS/MSYS2 package repositories remain moving sources, so builds are traceable rather than bit-for-bit reproducible.
