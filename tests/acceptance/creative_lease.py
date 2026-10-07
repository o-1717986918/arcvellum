"""One OS-owned writer per acceptance variant; a crashed process releases its lease."""
from contextlib import contextmanager
import os


@contextmanager
def case_lease(folder):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / '.acceptance.lock').open('a+b') as stream:
        if stream.tell()==0:
            stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('本案例版本已有验收进程，等其退出后再恢复。') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name=='nt':
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
