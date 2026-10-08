#!/usr/bin/env python3
"""Generate typed SysV wrappers around OpenCE's native Windows POSIX layer."""
import re
import sys


def main():
    guest_c, output = sys.argv[1:3]
    text = open(guest_c, encoding="utf-8").read()
    decls = re.findall(r"^([A-Za-z_][A-Za-z0-9_ \t*]*?)\s+(hostposix_(\w+))\((.*?)\);$", text, re.M)
    lines = ['#include "host.h"', '#include "posix.h"', '#include <windows.h>', '#include <stdint.h>', '',
             '#define DIRECTORY_HANDLE_COUNT 256',
             'static void *directory_handles[DIRECTORY_HANDLE_COUNT];',
             'static SRWLOCK directory_handle_lock = SRWLOCK_INIT;', '',
             'static uint32_t directory_handle_new(void *directory)', '{',
             '    uint32_t index;',
             '    if (!directory) return 0;',
             '    AcquireSRWLockExclusive(&directory_handle_lock);',
             '    for (index = 1; index < DIRECTORY_HANDLE_COUNT && directory_handles[index]; ++index) {}',
             '    if (index < DIRECTORY_HANDLE_COUNT) directory_handles[index] = directory;',
             '    ReleaseSRWLockExclusive(&directory_handle_lock);',
             '    if (index == DIRECTORY_HANDLE_COUNT) posix_directory_close(directory);',
             '    return index < DIRECTORY_HANDLE_COUNT ? index : 0;', '}', '',
             'static void *directory_handle_get(void *handle)', '{',
             '    uintptr_t index = (uintptr_t)handle;',
             '    return index && index < DIRECTORY_HANDLE_COUNT ? directory_handles[index] : NULL;', '}', '',
             'static void *directory_handle_take(void *handle)', '{',
             '    uintptr_t index = (uintptr_t)handle;',
             '    void *directory = NULL;',
             '    AcquireSRWLockExclusive(&directory_handle_lock);',
             '    if (index && index < DIRECTORY_HANDLE_COUNT) { directory = directory_handles[index]; directory_handles[index] = NULL; }',
             '    ReleaseSRWLockExclusive(&directory_handle_lock);',
             '    return directory;', '}', '']
    for ret, host, suffix, params in decls:
        plist = [] if params.strip() in ("", "void") else [p.strip() for p in params.split(",")]
        named, args = [], []
        for i, param in enumerate(plist):
            name = f"a{i}"
            match = re.match(r"^(.*?)([A-Za-z_]\w*)$", param)
            ptype = match.group(1).rstrip() if match else param
            named.append(f"{ptype} {name}"); args.append(name)
        body = f"    {'return ' if ret != 'void' else ''}posix_{suffix}({', '.join(args)});"
        if suffix == "directory_open":
            body = "    return (void *)(uintptr_t)directory_handle_new(posix_directory_open(a0));"
        elif suffix == "directory_next":
            body = "    return posix_directory_next(directory_handle_get(a0), a1, a2);"
        elif suffix == "directory_close":
            body = "    void *directory = directory_handle_take(a0);\n    if (directory) posix_directory_close(directory);"
        lines += [f"{ret} GUEST_ABI {host}({', '.join(named) or 'void'})", "{", body, "}", ""]
    open(output, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__": main()
