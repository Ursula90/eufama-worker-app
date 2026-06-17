[app]

title = EUFAMA Worker
package.name = eufamaworker
package.domain = com.eufamaholding

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

p4a.bootstrap = sdl2
requirements = python3,kivy==2.3.0,plyer,pyjnius,urllib3

# NDK version pinned here — buildozer reads android.ndk from [app], NOT [android]
android.ndk = 25b

# Orientation: portrait for phone usage
orientation = portrait
fullscreen = 0

# Icon and presplash (optional - using defaults for now)
# icon.filename = %(source.dir)s/icon.png

[android]

# Permissions needed: GPS, Camera, Internet, Storage
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,WAKE_LOCK,FOREGROUND_SERVICE

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
