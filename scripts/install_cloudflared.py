import platform, urllib.request, os, stat, sys, tarfile, tempfile

RELEASES = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
BINARIES = {
    ("linux",  "x86_64"):  "cloudflared-linux-amd64",
    ("linux",  "aarch64"): "cloudflared-linux-arm64",
    ("darwin", "x86_64"):  "cloudflared-darwin-amd64.tgz",
    ("darwin", "arm64"):   "cloudflared-darwin-arm64.tgz",
    ("windows","amd64"):   "cloudflared-windows-amd64.exe",
}

system = platform.system().lower()
machine = platform.machine().lower()
name = BINARIES.get((system, machine))
if not name:
    sys.exit(f"Unsupported platform: {system}/{machine}")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bin_name = "cloudflared.exe" if system == "windows" else "cloudflared"
dest = os.path.join(project_root, "bin", bin_name)
os.makedirs(os.path.dirname(dest), exist_ok=True)
url = RELEASES + name
print(f"Downloading {url}")

if name.endswith(".tgz"):
    with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as tmp:
        urllib.request.urlretrieve(url, tmp.name)
        with tarfile.open(tmp.name, "r:gz") as tar:
            # The archive contains a single binary named 'cloudflared'
            member = next(m for m in tar.getmembers() if m.name == "cloudflared")
            member.name = bin_name
            tar.extract(member, path=os.path.dirname(dest))
    os.unlink(tmp.name)
else:
    urllib.request.urlretrieve(url, dest)

os.chmod(dest, os.stat(dest).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
print(f"Installed to {dest}")