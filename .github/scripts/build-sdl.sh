#!/bin/sh
set -eu
mkdir -p /tmp/uqm-sdl
cd /tmp/uqm-sdl
curl --fail --location --retry 3 \
  https://github.com/libsdl-org/SDL/releases/download/release-2.32.10/SDL2-2.32.10.tar.gz \
  -o SDL2-2.32.10.tar.gz
echo '5f5993c530f084535c65a6879e9b26ad441169b3e25d789d83287040a9ca5165  SDL2-2.32.10.tar.gz' | sha256sum -c -
tar -xzf SDL2-2.32.10.tar.gz
cmake -S SDL2-2.32.10 -B out -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/uqm-sdl \
  -DCMAKE_INSTALL_LIBDIR=lib -DSDL_SHARED=ON -DSDL_STATIC=OFF \
  -DSDL_TEST=OFF -DSDL_TESTS=OFF \
  -DSDL_X11_SHARED=OFF -DSDL_WAYLAND_SHARED=OFF \
  -DSDL_ALSA_SHARED=OFF -DSDL_PULSEAUDIO_SHARED=OFF \
  -DSDL_LIBSAMPLERATE_SHARED=OFF
cmake --build out --parallel 2
cmake --install out
pkg-config --atleast-version=2.32.10 sdl2
pkg-config --modversion sdl2
