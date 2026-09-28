"""Monotonic work budgets and bounded POSIX child-process execution."""
import os
import selectors
import signal
import subprocess
import time


class DeadlineExceeded(TimeoutError):
    pass


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        self.clock = clock
        self.end = clock() + seconds

    def remaining(self):
        return max(0.0, self.end - self.clock())

    def check(self):
        if self.remaining() <= 0:
            raise DeadlineExceeded('Vale work deadline exceeded; unfinished files need another check.')


def run_process(args, *, cwd=None, input=None, deadline=None, timeout=20, max_output=8 * 1024 * 1024):
    """Drain bounded pipes, and kill the whole parser process group on failure."""
    deadline = deadline or Deadline(timeout)
    deadline.check()
    end = time.monotonic() + min(timeout, deadline.remaining())
    content = input.encode('utf-8') if isinstance(input, str) else (input or b'')
    proc = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    selector = selectors.DefaultSelector()
    outputs = {'stdout': bytearray(), 'stderr': bytearray()}
    position = 0
    total = 0
    try:
        for label, stream in (('stdout', proc.stdout), ('stderr', proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        if content:
            os.set_blocking(proc.stdin.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE, 'stdin')
        else:
            proc.stdin.close()
        while selector.get_map():
            deadline.check()
            remaining = min(deadline.remaining(), end - time.monotonic())
            if remaining <= 0:
                raise DeadlineExceeded('Vale subprocess timed out; unfinished files need another check.')
            for key, mask in selector.select(min(remaining, .05)):
                stream, label = key.fileobj, key.data
                if label == 'stdin':
                    try:
                        position += os.write(stream.fileno(), content[position:position + 65536])
                    except BrokenPipeError:
                        position = len(content)
                    except BlockingIOError:
                        continue
                    if position >= len(content):
                        selector.unregister(stream)
                        stream.close()
                else:
                    try:
                        chunk = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                    else:
                        total += len(chunk)
                        if total > max_output:
                            raise RuntimeError('Vale subprocess output exceeded the 8 MiB capture limit.')
                        outputs[label].extend(chunk)
        deadline.check()
        remaining = min(deadline.remaining(), end - time.monotonic())
        if remaining <= 0:
            raise DeadlineExceeded('Vale subprocess timed out.')
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise DeadlineExceeded('Vale subprocess timed out.') from exc
        return subprocess.CompletedProcess(args, proc.returncode,
                                           outputs['stdout'].decode('utf-8', errors='replace'),
                                           outputs['stderr'].decode('utf-8', errors='replace'))
    finally:
        # Even an exited parent can leave a parser descendant holding a pipe.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()
        selector.close()
        proc.wait(timeout=1)
