#!/usr/bin/env python3
"""Download a pinned Vale binary into a caller-selected CI directory."""
import hashlib
import io
from pathlib import Path
import platform
import sys
import tarfile
import urllib.request

CHECKSUMS = {
    ('Linux', 'x86_64'): ('Linux_64-bit', 'cc35445a45186b8f0b01e11c01359694cf941e72cf6ab0fc44774f0e54c9d5fc'),
    ('Darwin', 'arm64'): ('macOS_arm64', 'b913574b2c83b541d8bc2d8938e53a58a2fb06bab15135efcc755afb074f4430'),
    ('Darwin', 'x86_64'): ('macOS_64-bit', '416fdd3ba32e32dc71c87b479cb86757bb6437bcebc7a3e4a095e863b7ce583d'),
}
name, checksum = CHECKSUMS[(platform.system(), platform.machine())]
url = f'https://github.com/vale-cli/vale/releases/download/v3.23.0/vale_3.23.0_{name}.tar.gz'
with urllib.request.urlopen(url, timeout=30) as response:
    archive = response.read()
if hashlib.sha256(archive).hexdigest() != checksum:
    raise SystemExit('Vale checksum mismatch')
target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    member = next(m for m in tar.getmembers() if m.isfile() and m.name == 'vale')
    (target / 'vale').write_bytes(tar.extractfile(member).read())
(target / 'vale').chmod(0o755)
print(f'Installed verified Vale 3.23.0 to {target}')
