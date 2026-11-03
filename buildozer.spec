[app]
title = Cricket Platinum
package.name = cricketplatinum
package.domain = org.cricket
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,wav,mp3
version = 1.0
requirements = python3,kivy==2.3.0,pyjnius,android
orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 33
android.minapi = 21

[buildozer]
log_level = 2
warn_on_root = 0
