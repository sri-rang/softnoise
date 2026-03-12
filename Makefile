SCHEME    = SoftNoise
PROJECT   = macos/SoftNoise.xcodeproj
BUILD_DIR = macos/build

.PHONY: build run clean

build:
	xcodebuild -project $(PROJECT) \
	           -scheme $(SCHEME) \
	           -configuration Debug \
	           -derivedDataPath $(BUILD_DIR) \
	           CODE_SIGN_IDENTITY="-" \
	           ENABLE_HARDENED_RUNTIME=NO \
	           build

run: build
	xattr -cr "$(BUILD_DIR)/Build/Products/Debug/SoftNoise.app"
	open "$(BUILD_DIR)/Build/Products/Debug/SoftNoise.app"

clean:
	rm -rf $(BUILD_DIR)

# ── Linux ──────────────────────────────────────────────────────────────────
LINUX_BUILD_DIR = linux/build

.PHONY: linux-build linux-run linux-deb linux-appimage linux-flatpak linux-clean

linux-build:
	meson setup $(LINUX_BUILD_DIR) linux && meson compile -C $(LINUX_BUILD_DIR)

linux-run:
	cd linux && python3 -m softnoise

linux-deb:
	cd linux && dpkg-buildpackage -us -uc -b

linux-appimage:
	appimage-builder --recipe linux/packaging/appimage/AppImageBuilder.yml

linux-flatpak:
	flatpak-builder --force-clean linux/flatpak-build linux/flatpak/com.softnoise.app.yml

linux-clean:
	rm -rf $(LINUX_BUILD_DIR) linux/flatpak-build
