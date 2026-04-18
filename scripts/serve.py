"""
Start the FastAPI app and expose it via a Cloudflare Tunnel.

Usage:
    uv run python scripts/serve.py [--port 8000]
"""

import argparse
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = PROJECT_ROOT / "bin"
CLOUDFLARED = BIN_DIR / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve app + Cloudflare Tunnel")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--export-url",
        metavar="FILE",
        nargs="?",
        const=str(PROJECT_ROOT / ".tunnel_url"),
        help="Write the public tunnel URL to a file (default: .tunnel_url)",
    )
    args = parser.parse_args()

    if not CLOUDFLARED.exists():
        sys.exit(
            f"cloudflared binary not found at {CLOUDFLARED}.\n"
            "Run:  uv run python scripts/install_cloudflared.py"
        )

    # Free the port if something is already bound to it
    if sys.platform == "win32":
        subprocess.run(
            f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr ":{args.port}"\') do taskkill /F /PID %a',
            shell=True, cwd=PROJECT_ROOT
        )
    else:
        subprocess.run(
            f"lsof -ti tcp:{args.port} | xargs -r kill -9",
            shell=True, cwd=PROJECT_ROOT
        )

    uvicorn_cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(args.port),
        "--reload",
    ]
    tunnel_cmd = [str(CLOUDFLARED), "tunnel", "--url", f"http://localhost:{args.port}"]

    print(f"Starting app on port {args.port} ...")
    app_proc = subprocess.Popen(uvicorn_cmd, cwd=PROJECT_ROOT)

    # Give the server a moment to bind before the tunnel connects
    time.sleep(2)

    print(f"Starting Cloudflare Tunnel -> http://localhost:{args.port} ...")
    tunnel_proc = subprocess.Popen(
        tunnel_cmd, cwd=PROJECT_ROOT,
        stderr=subprocess.PIPE, text=True
    )

    def _print_tunnel_output(proc: subprocess.Popen) -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            print(line, end="")
            url_match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if url_match:
                url = url_match.group()
                print(f"\n{'='*60}")
                print(f"  PUBLIC URL: {url}")
                print(f"{'='*60}\n")
                # Export to file
                if args.export_url:
                    Path(args.export_url).write_text(url + "\n")
                    print(f"  URL saved to: {args.export_url}")
                # Copy to clipboard (best-effort)
                try:
                    if sys.platform == "darwin":
                        subprocess.run(["pbcopy"], input=url, text=True, check=True)
                        print("  URL copied to clipboard.")
                    elif sys.platform == "win32":
                        subprocess.run(["clip"], input=url, text=True, check=True)
                        print("  URL copied to clipboard.")
                    else:
                        subprocess.run(["xclip", "-selection", "clipboard"], input=url, text=True, check=True)
                        print("  URL copied to clipboard.")
                except Exception:
                    pass  # clipboard is optional

    threading.Thread(target=_print_tunnel_output, args=(tunnel_proc,), daemon=True).start()

    try:
        app_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        tunnel_proc.terminate()
        app_proc.terminate()


if __name__ == "__main__":
    main()
