[app]
title = Cricket Platinum
package.name = cricketplatinum
package.domain = org.cricket
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,wav,mp3,ogg
version = 1.1
requirements = python3,kivy==2.3.0,pyjnius,android
python_version = 3.10
p4a.branch = release-2024.01.21
orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 33
android.minapi = 21
android.ndk_version = 25b

[buildozer]
log_level = 2
warn_on_root = 0
