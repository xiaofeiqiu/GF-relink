import logging

import pymem
import pymem.process
import win32process

log = logging.getLogger("gbf.memory")


def pid_from_hwnd(hwnd: int) -> int:
    _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid


class ProcessMemory:
    def __init__(self, pid: int, module_name: str) -> None:
        self._pm = pymem.Pymem()
        self._pm.open_process_from_id(pid)
        module = pymem.process.module_from_name(self._pm.process_handle, module_name)
        if module is None:
            self._pm.close_process()
            raise RuntimeError(f"Module not found in process {pid}: {module_name}")
        self._base = module.lpBaseOfDll
        log.info("Opened pid=%d, %s base=0x%X", pid, module_name, self._base)

    @property
    def base(self) -> int:
        return self._base

    def read_uint32(self, address: int) -> int:
        return self._pm.read_uint(address)

    def write_uint32(self, address: int, value: int) -> None:
        self._pm.write_uint(address, value)

    def read_bytes(self, address: int, length: int) -> bytes:
        return self._pm.read_bytes(address, length)

    def resolve_pointer_chain(self, base_offset: int, offsets: tuple[int, ...]) -> int:
        addr = self._pm.read_ulonglong(self._base + base_offset)
        for offset in offsets[:-1]:
            addr = self._pm.read_ulonglong(addr + offset)
        return addr + offsets[-1]

    def close(self) -> None:
        try:
            self._pm.close_process()
        except Exception:
            log.exception("Error closing process handle")
