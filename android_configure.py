import platform
import sys
import os
import re

def patch_android():
    print("- Applying Android NDK compatibility patches -")

    # 1. Patch deps/v8/src/trap-handler/trap-handler.h
    trap_path = "deps/v8/src/trap-handler/trap-handler.h"
    if os.path.exists(trap_path):
        with open(trap_path, "r", encoding="utf-8") as f:
            txt = f.read()
        if "NODE_ANDROID_BUILD" not in txt:
            txt = txt.replace(
                "#if V8_HOST_ARCH_X64 && V8_TARGET_ARCH_X64 &&",
                "#if defined(V8_OS_ANDROID) || defined(NODE_ANDROID_BUILD)\n#define V8_TRAP_HANDLER_SUPPORTED false\n#elif V8_HOST_ARCH_X64 && V8_TARGET_ARCH_X64 &&"
            )
            txt = txt.replace(
                "#elif V8_TARGET_ARCH_ARM64 && V8_HOST_ARCH_X64 &&",
                "#elif 0 && V8_TARGET_ARCH_ARM64 && V8_HOST_ARCH_X64 &&"
            )
            with open(trap_path, "w", encoding="utf-8") as f:
                f.write(txt)
            print("[1] Patched " + trap_path)

    # 2. Patch deps/zlib/cpu_features.c (NDK r27+ removed cpu-features.h, use getauxval)
    zlib_path = "deps/zlib/cpu_features.c"
    if os.path.exists(zlib_path):
        with open(zlib_path, "r", encoding="utf-8") as f:
            txt = f.read()
        if "<cpu-features.h>" in txt:
            txt = re.sub(
                r"#if defined\(ARMV8_OS_ANDROID\)\s+#include <cpu-features\.h>\s+#elif defined\(ARMV8_OS_LINUX\)",
                "#if defined(ARMV8_OS_ANDROID) || defined(ARMV8_OS_LINUX)",
                txt
            )
            txt = re.sub(
                r"#if defined\(ARMV8_OS_ANDROID\) && defined\(__aarch64__\)[\s\S]*?#elif defined\(ARMV8_OS_LINUX\) && defined\(__aarch64__\)",
                "#if (defined(ARMV8_OS_ANDROID) || defined(ARMV8_OS_LINUX)) && defined(__aarch64__)",
                txt
            )
            txt = re.sub(
                r"#elif defined\(ARMV8_OS_ANDROID\) /\* aarch32 \*/[\s\S]*?#elif defined\(ARMV8_OS_LINUX\) && \(defined\(__ARM_NEON\) \|\| defined\(__ARM_NEON__\)\)",
                "#elif (defined(ARMV8_OS_ANDROID) || defined(ARMV8_OS_LINUX)) && (defined(__ARM_NEON) || defined(__ARM_NEON__))",
                txt
            )
            with open(zlib_path, "w", encoding="utf-8") as f:
                f.write(txt)
            print("[2] Patched " + zlib_path)

    # 3. Patch deps/uv/src/unix/linux.c (LLONG_MAX under --std=gnu89 on Bionic)
    uv_linux_path = "deps/uv/src/unix/linux.c"
    if os.path.exists(uv_linux_path):
        with open(uv_linux_path, "r", encoding="utf-8") as f:
            txt = f.read()
        if "__LONG_LONG_MAX__" not in txt:
            txt = txt.replace(
                "#include <unistd.h>",
                "#include <unistd.h>\n#include <limits.h>\n#ifndef LLONG_MAX\n#define LLONG_MAX __LONG_LONG_MAX__\n#endif"
            )
            with open(uv_linux_path, "w", encoding="utf-8") as f:
                f.write(txt)
            print("[3] Patched " + uv_linux_path)

if platform.system() != "Linux" and platform.system() != "Darwin":
    print("android-configure is currently only supported on Linux and Darwin.")
    sys.exit(1)

if len(sys.argv) == 2 and sys.argv[1] == "patch":
    patch_android()
    sys.exit(0)

if len(sys.argv) < 4:
    print("Usage: ./android-configure [patch] <path to the Android NDK> <Android SDK version> <target architecture> [extra configure args...]")
    sys.exit(1)

if not os.path.exists(sys.argv[1]) or not os.listdir(sys.argv[1]):
    print("\033[91mError: \033[0m" + "Invalid path to the Android NDK")
    sys.exit(1)

if int(sys.argv[2]) < 24:
    print("\033[91mError: \033[0m" + "Android SDK version must be at least 24 (Android 7.0)")
    sys.exit(1)

patch_android()

android_ndk_path = os.path.abspath(sys.argv[1])
android_sdk_version = sys.argv[2]
arch = sys.argv[3]
extra_args = " ".join(sys.argv[4:])

if arch == "arm":
    DEST_CPU = "arm"
    TOOLCHAIN_PREFIX = "armv7a-linux-androideabi"
elif arch in ("aarch64", "arm64"):
    DEST_CPU = "arm64"
    TOOLCHAIN_PREFIX = "aarch64-linux-android"
    arch = "arm64"
elif arch == "x86":
    DEST_CPU = "ia32"
    TOOLCHAIN_PREFIX = "i686-linux-android"
elif arch == "x86_64":
    DEST_CPU = "x64"
    TOOLCHAIN_PREFIX = "x86_64-linux-android"
    arch = "x64"
else:
    print("\033[91mError: \033[0m" + "Invalid target architecture, must be one of: arm, arm64, aarch64, x86, x86_64")
    sys.exit(1)

print("\033[92mInfo: \033[0m" + "Configuring for " + DEST_CPU + "...")

if platform.system() == "Darwin":
    host_os = "darwin"
    toolchain_path = android_ndk_path + "/toolchains/llvm/prebuilt/darwin-x86_64"
elif platform.system() == "Linux":
    host_os = "linux"
    toolchain_path = android_ndk_path + "/toolchains/llvm/prebuilt/linux-x86_64"

os.environ['PATH'] += os.pathsep + toolchain_path + "/bin"
os.environ['CC'] = toolchain_path + "/bin/" + TOOLCHAIN_PREFIX + android_sdk_version + "-clang"
os.environ['CXX'] = toolchain_path + "/bin/" + TOOLCHAIN_PREFIX + android_sdk_version + "-clang++"
os.environ['AR'] = toolchain_path + "/bin/llvm-ar"
os.environ['RANLIB'] = toolchain_path + "/bin/llvm-ranlib"
os.environ['LINK'] = toolchain_path + "/bin/" + TOOLCHAIN_PREFIX + android_sdk_version + "-clang++"

os.environ['CC_host'] = os.environ.get('CC_host', 'gcc')
os.environ['CXX_host'] = os.environ.get('CXX_host', 'g++')
os.environ['AR_host'] = os.environ.get('AR_host', 'ar')
os.environ['LINK_host'] = os.environ.get('LINK_host', 'g++')

os.environ['CFLAGS'] = os.environ.get('CFLAGS', '') + " -fPIC -DNODE_ANDROID_BUILD=1 -D__ISO_C_VISIBLE=1999 -DLLONG_MAX=__LONG_LONG_MAX__"
os.environ['CXXFLAGS'] = os.environ.get('CXXFLAGS', '') + " -fPIC -DNODE_ANDROID_BUILD=1"
os.environ['CFLAGS_host'] = os.environ.get('CFLAGS_host', '') + " -DNODE_ANDROID_BUILD=1"
os.environ['CXXFLAGS_host'] = os.environ.get('CXXFLAGS_host', '') + " -DNODE_ANDROID_BUILD=1"

GYP_DEFINES = "target_arch=" + arch
GYP_DEFINES += " v8_target_arch=" + arch
GYP_DEFINES += " android_target_arch=" + arch
GYP_DEFINES += " host_os=" + host_os + " OS=android"
GYP_DEFINES += " android_ndk_path=" + android_ndk_path
os.environ['GYP_DEFINES'] = GYP_DEFINES

if os.path.exists("./configure"):
    cmd = "./configure --dest-cpu=" + DEST_CPU + " --dest-os=android --openssl-no-asm --cross-compiling " + extra_args
    print("Running: " + cmd)
    ret = os.system(cmd)
    if ret != 0:
        sys.exit(1)