[app]

title = EUFAMA Worker
package.name = eufamaworker
package.domain = com.eufamaholding

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav

# The FastAPI backend, and any local dev venvs, are not part of the
# Android app — only the eufama_client/ package and main.py get packaged.
source.exclude_dirs = backend,.venv,.client_venv,.github,.git

version = 1.0

p4a.bootstrap = sdl2
requirements = python3,kivy==2.3.0,plyer,pyjnius,urllib3,websocket-client

# Pin python-for-android itself (buildozer clones this from git — it is
# NOT resolved from the `pip install python-for-android` in build.yml, so
# pinning it there wouldn't do anything). Recent p4a releases hardcode the
# `python3` recipe to build Python 3.14, whose C API removed a 5-argument
# form of _PyLong_AsByteArray that Kivy 2.3.0's bundled/pre-cythonized
# cgl_debug.c and vertex_instructions.c still call, breaking the build with
# "too few arguments to function call". v2024.01.21 still targets Python
# 3.11.5, which those generated files are compatible with.
p4a.branch = v2024.01.21

# NDK version pinned here — buildozer reads android.ndk from [app], NOT [android]
android.ndk = 25b

# Orientation: portrait for phone usage
orientation = portrait
fullscreen = 0

# Icon and presplash (optional - using defaults for now)
# icon.filename = %(source.dir)s/icon.png

[android]

# Permissions needed: GPS, Camera, Internet, Storage, Mic (voice notes/calls), Vibration (Buzz)
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,CAMERA,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,WAKE_LOCK,FOREGROUND_SERVICE,VIBRATE

# Target modern Android (compatible with Samsung S26 Ultra)
android.api = 34
android.minapi = 26
android.sdk = 34

# Architecture - covers all modern Samsung devices
android.archs = arm64-v8a, armeabi-v7a

# Accept SDK license automatically during build
android.accept_sdk_license = True

# App will not be released to Play Store - internal distribution only
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
