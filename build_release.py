"""Build only the public application and its explicitly listed release assets."""
import hashlib
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent


def main():
    subprocess.run([sys.executable, str(ROOT / "test_action_hud.py")], cwd=ROOT, check=True)
    import action_hud

    notices = ROOT / "THIRD_PARTY_LICENSES"
    notices.mkdir(exist_ok=True)
    for name in ("flask", "mss", "numpy", "pillow", "blinker", "click", "itsdangerous",
                 "jinja2", "markupsafe", "werkzeug", "pyinstaller"):
        dist = importlib.metadata.distribution(name)
        files = [p for p in dist.files if p.name.lower().startswith(("license", "copying", "notice"))]
        if not files:
            raise RuntimeError(f"No license notice found for {name}")
        for index, file in enumerate(files):
            shutil.copyfile(dist.locate_file(file), notices / f"{name}-{dist.version}-{index}-{file.name}")
    shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", notices / "Python-LICENSE.txt")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--console", "--noupx", "--name", "NightbringerActionHUD",
        "--add-data", f"{ROOT / 'static'};static", "--specpath", "build",
        "--distpath", "dist", "--workpath", "build/pyinstaller", "action_hud.py",
    ], cwd=ROOT, check=True)
    exe = ROOT / "dist/NightbringerActionHUD.exe"
    subprocess.run([str(exe), "--version"], cwd=ROOT, check=True)
    archive = ROOT / "dist" / f"Nightbringer-Action-HUD-{action_hud.VERSION}-Windows-x64.zip"
    entries = {exe: "NightbringerActionHUD.exe", ROOT / "README.md": "README.md",
               ROOT / "RECALIBRATE.cmd": "RECALIBRATE.cmd"}
    entries.update({p: p.relative_to(ROOT).as_posix() for p in notices.iterdir() if p.is_file()})
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path, name in sorted(entries.items()):
            output.write(path, name)
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for path, name in entries.items():
            assert output.read(name) == path.read_bytes()
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / "dist/SHA256SUMS.txt").write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    print(f"Built {archive.name} ({archive.stat().st_size:,} bytes)\nSHA256 {checksum}")


if __name__ == "__main__":
    main()
