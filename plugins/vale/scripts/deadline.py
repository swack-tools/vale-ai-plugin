"""Monotonic work budgets and bounded POSIX child-process execution."""
import os
import selectors
import signal
import subprocess
import time

PROCESS_EXIT_GRACE = 0.1
PROCESS_REAP_TIMEOUT = 1.0


class DeadlineExceeded(TimeoutError):
    pass


class OutputLimitExceeded(RuntimeError):
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


def run_process(args, *, cwd=None, input=None, deadline=None, timeout=20, max_output=8 * 1024 * 1024, text=True):
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
                            raise OutputLimitExceeded(f'Vale subprocess output exceeded the {max_output}-byte capture limit.')
                        outputs[label].extend(chunk)
        deadline.check()
        remaining = min(deadline.remaining(), end - time.monotonic())
        if remaining <= 0:
            raise DeadlineExceeded('Vale subprocess timed out.')
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise DeadlineExceeded('Vale subprocess timed out.') from exc
        stdout, stderr = bytes(outputs['stdout']), bytes(outputs['stderr'])
        if text:
            stdout, stderr = (stream.decode('utf-8', errors='replace') for stream in (stdout, stderr))
        return subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)
    finally:
        # Even an exited parent can leave a parser descendant holding a pipe.
        cleanup_error = None
        try:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                # The process group has already exited; no descendants need killing.
                pass
            except PermissionError as signal_error:
                # macOS can report EPERM while an owned child is completing exit.
                # Reap briefly, then retry the group signal to catch descendants.
                try:
                    proc.wait(timeout=PROCESS_EXIT_GRACE)
                except subprocess.TimeoutExpired:
                    # A live child means the group signal really failed. Kill
                    # the owned direct child so it cannot leak, but report the
                    # group failure because descendants may still be running.
                    cleanup_error = signal_error
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    except OSError as kill_error:
                        cleanup_error.add_note(f'Could not kill owned child: {kill_error}')
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except PermissionError as retry_error:
                        cleanup_error = retry_error
        finally:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()
            selector.close()
            try:
                proc.wait(timeout=PROCESS_REAP_TIMEOUT)
            except subprocess.TimeoutExpired as wait_error:
                if cleanup_error is None:
                    cleanup_error = RuntimeError('Could not reap the owned Vale subprocess within one second.')
                cleanup_error.add_note(str(wait_error))
            if cleanup_error is not None:
                raise cleanup_error
