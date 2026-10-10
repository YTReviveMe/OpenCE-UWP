import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, List

from . import port_settings
from .android_build import (EXPAT_DIR, EXPAT_SOURCES, KCP_DIR, MONOCYPHER_DIR,
                            MUSL_DIR, MUSL_MATH_DIR, SDL_DIR, TOML_DIR,
                            VARIADIC_PROTOTYPE_FILES, ZLIB_DEFINES, ZLIB_DIR,
                            ZLIB_SOURCES, _musl_sources,
                            fetch_third_party)
from .embed_assets import hud_assets_build, hud_configure_inputs
from .linux_build import (LINUX_PROFILE, XDK_INCLUDE, compile_launcher,
                          game_defines_and_includes, game_sources,
                          musl_math_sources, opus_cflags, opus_sources,
                          pgo_mode, pgo_profile,
                          profile_use_flags, xdk_headers)
from .ninja_syntax import Writer

PORT_DIR = Path("port/xbox")
ANDROID_DIR = Path("port/android")
LINUX_DIR = Path("port/linux")
BUILD = Path("build/xbox")


def refresh_settings_assets() -> None:
    menu_dir = Path("port/assets/menus/ce")
    for name, lines in port_settings.settings_files().items():
        path = menu_dir / name
        contents = "\n".join(lines)
        if not path.is_file() or path.read_text(encoding="utf-8") != contents:
            path.write_text(contents, encoding="utf-8")


def xbox_configure_inputs() -> List[Path]:
    return [Path(__file__), PORT_DIR, ANDROID_DIR / "guest" / "runtime",
            LINUX_DIR / "src", *hud_configure_inputs()]


def _find_gles_headers() -> Path | None:
    configured = os.environ.get("HALO_XBOX_GLES_INCLUDE")
    candidates = [Path(configured)] if configured else []
    candidates += [
        Path("C:/bsuwp/libultraship/vcpkg/installed/x64-windows-static/include"),
        Path("C:/vcpkg/installed/x64-windows/include"),
    ]
    for path in candidates:
        if (path / "GLES3/gl32.h").is_file() and (path / "GLES2/gl2ext.h").is_file():
            return path
    return None


def generate_xbox_build(n: Writer, sln: Any) -> None:
    refresh_settings_assets()
    config_path = LINUX_DIR / "port.json"
    if not config_path.is_file():
        return
    try:
        fetch_third_party()
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Xbox build disabled: cannot fetch musl/SDL3 ({error})", file=sys.stderr)
        return
    gles = _find_gles_headers()
    if not gles:
        n.comment("Xbox build: GLES headers not found (set HALO_XBOX_GLES_INCLUDE)")
        return

    config = json.loads(config_path.read_text(encoding="utf-8"))
    guest_dir = BUILD / "guest"
    obj_dir = guest_dir / "obj"
    gen_dir = guest_dir / "gen"
    libc_include = guest_dir / "libc_include"
    libc_internal = guest_dir / "libc_internal"
    xbox_arch = PORT_DIR / "guest" / "libc" / "arch" / "x32"
    musl_arch = MUSL_DIR / "arch" / "x32"
    image = BUILD / "halo_guest.elf"
    semantics_header = Path("build/linux/halo_msvc_semantics.h")
    platform_semantics_header = Path("build/linux/platform_msvc_semantics.h")
    prefix_header = LINUX_DIR / "include" / "halo_linux_prefix.h"
    python = "$python"

    n.comment("Xbox Dev Mode x64/UWP build; x32 game guest")
    n.variable("xbox_guest_cc", "clang")
    n.variable("xbox_llvm_ar", shutil.which("llvm-ar") or "llvm-ar")
    n.variable("xbox_ld", shutil.which("ld.lld") or "ld.lld")

    alltypes = libc_include / "bits" / "alltypes.h"
    syscall_h = libc_include / "bits" / "syscall.h"
    version_h = libc_internal / "version.h"
    n.rule("xbox_alltypes",
           command=(f"{python} tools/musl_headers.py alltypes "
                    f"{MUSL_DIR}/tools/mkalltypes.sed $out $in"),
           description="XBOX MUSL $out")
    n.build(outputs=alltypes, rule="xbox_alltypes",
            inputs=[musl_arch / "bits/alltypes.h.in", MUSL_DIR / "include/alltypes.h.in"])
    n.rule("xbox_syscall_h",
           command=f"{python} tools/musl_headers.py syscall $in $out",
           description="XBOX MUSL $out")
    n.build(outputs=syscall_h, rule="xbox_syscall_h", inputs=musl_arch / "bits/syscall.h.in")
    n.rule("xbox_version_h",
           command=f"{python} tools/musl_headers.py version $out 1.2.5",
           description="XBOX MUSL $out")
    n.build(outputs=version_h, rule="xbox_version_h")

    guest_gl_c = gen_dir / "guest_gl.c"
    gl_imports = gen_dir / "gl_imports.list"
    n.rule("xbox_gl_stubs",
           command=(f"{python} tools/android_gl_stubs.py {LINUX_DIR}/src/gl.h "
                    f"{gles}/GLES3/gl32.h {gles}/GLES2/gl2ext.h $out_c $out_list"),
           description="XBOX GL STUBS")
    n.build(outputs=[guest_gl_c, gl_imports], rule="xbox_gl_stubs",
            implicit=[Path("tools/android_gl_stubs.py"), LINUX_DIR / "src/gl.h"],
            variables={"out_c": guest_gl_c, "out_list": gl_imports})

    guest_posix_c = gen_dir / "guest_posix.c"
    posix_imports = gen_dir / "posix_imports.list"
    n.rule("xbox_posix_stubs",
           command=f"{python} tools/android_posix_stubs.py {LINUX_DIR}/src/posix.h $out_c $out_list",
           description="XBOX POSIX STUBS")
    n.build(outputs=[guest_posix_c, posix_imports], rule="xbox_posix_stubs",
            implicit=[Path("tools/android_posix_stubs.py"), LINUX_DIR / "src/posix.h"],
            variables={"out_c": guest_posix_c, "out_list": posix_imports})

    imports_s = gen_dir / "imports.s"
    host_table_c = BUILD / "host" / "host_import_table.c"
    n.rule("xbox_imports",
           command=(f"{python} tools/android_imports.py --arch x86_64 --host-table "
                    f"{host_table_c} $out_s $in"),
           description="XBOX IMPORTS")
    n.build(outputs=[imports_s, host_table_c], rule="xbox_imports",
            inputs=[ANDROID_DIR / "host_imports.list", PORT_DIR / "host_imports.list",
                    posix_imports, gl_imports],
            implicit=[Path("tools/android_imports.py")],
            variables={"out_s": imports_s})

    generated = [*xdk_headers(), alltypes, syscall_h, version_h,
                 semantics_header, platform_semantics_header]
    guest_abi_flags = [
        "--target=x86_64-unknown-linux-gnux32", "-DHALO_ANDROID=1",
        "-DHALO_UWP_PC=1",
        "-DHALO_GLES=1",
        "-DHALO_GUEST_IMAGE_BASE=0x70000000u",
        "-DHALO_XBOX_UWP=1", "-nostdinc", "-fshort-wchar",
        "-fno-stack-protector", "-fno-unwind-tables",
        "-fno-asynchronous-unwind-tables", "-femulated-tls",
        "-fno-pic", "-fno-pie", "-ffp-contract=off", "-O2",
    ]
    guest_code_flags = [
        "-fms-extensions", "-fcommon", "-fno-strict-aliasing", "-fwrapv",
        "-fno-delete-null-pointer-checks", "-fno-omit-frame-pointer",
    ] + [f"-fno-builtin-{name}" for name in (
        "wcslen", "wcsnlen", "wcschr", "wcsrchr", "wcscmp", "wcsncmp",
        "wcscpy", "wcsncpy", "wcscat", "wcsncat", "wmemchr", "wmemcmp",
        "wmemcpy", "wmemmove", "wmemset")]
    if getattr(sln, "port_release", False):
        guest_abi_flags.append("-DHALO_RELEASE")
    guest_abi = " ".join(guest_abi_flags)
    guest_code = " ".join(guest_code_flags)
    libc_includes = [
        f"-isystem {libc_include}", f"-isystem {xbox_arch}",
        f"-isystem {musl_arch}", f"-isystem {MUSL_DIR}/arch/generic",
        f"-isystem {MUSL_DIR}/include",
    ]

    n.rule("xbox_guest_cc",
           command=(f"{compile_launcher(sln)}$xbox_guest_cc -MMD -MF $out.d "
                    "$cflags -c $in -o $out"),
           description="XBOX GUEST CC $out", depfile="$out.d", deps="gcc")
    n.rule("xbox_guest_as",
           command="$xbox_guest_cc --target=x86_64-unknown-linux-gnux32 -c $in -o $out",
           description="XBOX GUEST AS $out")

    profile = pgo_profile(sln, LINUX_PROFILE if pgo_mode(sln) == "train" else None,
                          [LINUX_PROFILE], "clang")
    profile_flags = " ".join(profile_use_flags(profile))
    implicit = list(generated)
    if profile:
        implicit.append(profile)

    def guest_object(source: Path, cflags: str, prefix: str = "") -> Path:
        obj = obj_dir / prefix / Path(str(source).lstrip("/\\")).with_suffix(".o")
        if str(source).startswith(str(BUILD)):
            obj = obj_dir / prefix / source.relative_to(BUILD).with_suffix(".o")
        n.build(outputs=obj, rule="xbox_guest_cc", inputs=source,
                implicit=implicit, variables={"cflags": cflags})
        return obj

    musl_cflags = " ".join([
        guest_abi, "-std=c99", "-ffreestanding", "-fno-common",
        "-D_XOPEN_SOURCE=700", "-w", f"-I{xbox_arch}", f"-I{musl_arch}",
        f"-I{MUSL_DIR}/arch/generic", f"-I{libc_internal}",
        f"-I{ANDROID_DIR}/guest/libc/src_include", f"-I{MUSL_DIR}/src/include",
        f"-I{MUSL_DIR}/src/internal", f"-I{libc_include}", f"-I{MUSL_DIR}/include",
    ])
    musl_objects = [guest_object(source, musl_cflags, "musl") for source in _musl_sources()]
    musl_fenv_o = obj_dir / "musl" / "fenv_x32.o"
    n.build(outputs=musl_fenv_o, rule="xbox_guest_as",
            inputs=MUSL_DIR / "src/fenv/x32/fenv.s")
    musl_objects.append(musl_fenv_o)
    libguestc = guest_dir / "libguestc.a"
    n.rule("xbox_ar", command="$xbox_llvm_ar rcs $out @$out.rsp",
           description="XBOX AR $out", rspfile="$out.rsp", rspfile_content="$in_newline")
    n.build(outputs=libguestc, rule="xbox_ar", inputs=musl_objects)

    game_flags = " ".join([
        "-std=gnu89", "-D__STRICT_ANSI__", "-w",
        "-Wno-error=incompatible-pointer-types",
        "-Wno-error=incompatible-function-pointer-types",
        "-Wno-error=int-conversion", "-Wno-error=implicit-function-declaration",
        "-Wno-error=implicit-int", "-Wno-error=return-type",
    ])
    game_cflags = " ".join([
        guest_abi, guest_code, game_flags, profile_flags,
        f"-include {prefix_header}", f"-include {semantics_header}",
        f"-I{LINUX_DIR}/include",
        f"-iquote {Path(config['game_sources'])}",
        game_defines_and_includes(config),
        *libc_includes, f"-idirafter {XDK_INCLUDE}",
    ])
    objects: List[Path] = []
    for source in game_sources(config):
        flags = game_cflags
        if source.as_posix() in VARIADIC_PROTOTYPE_FILES:
            flags += f" -include {ANDROID_DIR}/include/halo_android_variadic_prototypes.h"
        objects.append(guest_object(source, flags))
    for source in sorted(Path(config["game_sources"]).glob("*.c")):
        objects.append(guest_object(source, game_cflags))

    platform_cflags = " ".join([
        guest_abi, guest_code, "-std=gnu11", "-D_GNU_SOURCE",
        "-DHALO_LINUX_PLATFORM_LAYER", "-w", profile_flags,
        f"-include {prefix_header}", f"-include {platform_semantics_header}",
        f"-I{LINUX_DIR}/src", f"-I{LINUX_DIR}/include",
        f"-I{ANDROID_DIR}/guest/runtime", f"-I{ANDROID_DIR}/include",
        f"-I{TOML_DIR}", f"-I{EXPAT_DIR}", f"-I{KCP_DIR}", f"-I{MONOCYPHER_DIR}",
        f"-I{ZLIB_DIR}",
        "-Isource -Isource/cseries", f"-I{SDL_DIR}/include", f"-I{gles}",
        *libc_includes, f"-idirafter {XDK_INCLUDE}",
    ])
    for source in sorted((LINUX_DIR / "src").glob("*.c")):
        if source.name.startswith("posix_") or source.name == "memory_watch.c":
            continue
        objects.append(guest_object(source, platform_cflags))
    for source in hud_assets_build(n, "xbox", gen_dir / "hud_hires_assets.c"):
        objects.append(guest_object(source, platform_cflags))
    objects.append(guest_object(TOML_DIR / "tomlc17.c", platform_cflags))
    for name in EXPAT_SOURCES:
        objects.append(guest_object(EXPAT_DIR / name, platform_cflags))
    objects.append(guest_object(KCP_DIR / "ikcp.c", platform_cflags))
    for source in opus_sources():
        objects.append(guest_object(source, " ".join([
            opus_cflags(guest_abi), "-U__SSE__", *libc_includes,
        ])))
    for name in ("monocypher.c", "monocypher-ed25519.c"):
        objects.append(guest_object(MONOCYPHER_DIR / name, platform_cflags))
    for name in ZLIB_SOURCES:
        objects.append(guest_object(ZLIB_DIR / name,
                                    " ".join([platform_cflags, *ZLIB_DEFINES])))

    math_cflags = " ".join([
        guest_abi, "-std=gnu11", "-w", profile_flags, *libc_includes,
        f"-I{MUSL_MATH_DIR}/include", f"-include {MUSL_MATH_DIR}/include/libm.h",
    ])
    for source in musl_math_sources():
        objects.append(guest_object(source, math_cflags))

    runtime_internal = " ".join([
        guest_abi, "-std=c99", "-ffreestanding", "-fno-common",
        "-D_XOPEN_SOURCE=700", "-D_GNU_SOURCE",
        f"-I{ANDROID_DIR}/guest/runtime", f"-I{ANDROID_DIR}/include",
        f"-I{xbox_arch}", f"-I{musl_arch}", f"-I{MUSL_DIR}/arch/generic",
        f"-I{libc_internal}", f"-I{ANDROID_DIR}/guest/libc/src_include",
        f"-I{MUSL_DIR}/src/include", f"-I{MUSL_DIR}/src/internal",
        f"-I{libc_include}", f"-I{MUSL_DIR}/include",
    ])
    runtime_cflags = " ".join([
        guest_abi, guest_code, "-std=gnu11", "-D_GNU_SOURCE",
        f"-I{ANDROID_DIR}/guest/runtime", f"-I{ANDROID_DIR}/include",
        f"-I{LINUX_DIR}/src", f"-I{SDL_DIR}/include", f"-I{gles}", *libc_includes,
    ])
    for source in sorted((ANDROID_DIR / "guest/runtime").glob("*.c")):
        flags = runtime_internal if source.name in ("guest_thread.c", "guest_start.c") else (
            platform_cflags if source.name == "guest_memory_watch.c" else runtime_cflags)
        objects.append(guest_object(source, flags))
    objects.append(guest_object(guest_gl_c, runtime_cflags))
    objects.append(guest_object(guest_posix_c, runtime_cflags))
    imports_o = obj_dir / "gen/imports.o"
    n.build(outputs=imports_o, rule="xbox_guest_as", inputs=imports_s)
    objects.append(imports_o)

    linker_script = PORT_DIR / "guest/guest.ld"
    n.rule("xbox_guest_link",
           command=(f"$xbox_ld --rsp-quoting=windows -m elf32_x86_64 -static -nostdlib -T {linker_script.as_posix()} "
                    f"-Map $out.map -o $out @$out.rsp {libguestc}"),
           description="XBOX GUEST LINK $out", rspfile="$out.rsp",
           rspfile_content="$in_newline")
    n.build(outputs=image, rule="xbox_guest_link", inputs=objects,
            implicit=[libguestc, linker_script])
    n.build(outputs="xbox_guest", rule="phony", inputs=image)
