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
