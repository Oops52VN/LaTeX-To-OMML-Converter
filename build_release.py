# -*- coding: utf-8 -*-
"""
build_release.py
Automated release packaging pipeline for OMML Converter.
Compiles the full application into a standalone single-file Windows installer:
    releases/OMML_Converter_Setup_v.11.19.26.exe

Pipeline Steps:
1. Environment & Pre-requisite Verification (PyInstaller, PyQt5, etc.)
2. Icon Generation (converts resources/UI/assets/logo.png to resources/icons/app.ico if missing)
3. Portable Inno Setup 6 Toolchain Resolution (auto-installs to tools/InnoSetup if missing)
4. PyInstaller Staging Compilation (frozen application in dist/OMML Converter/)
5. Inno Setup Script Generation (OMML_Converter.iss)
6. Single-File Windows Installer Compilation (releases/OMML_Converter_Setup_v.11.19.26.exe)
7. Deterministic Post-Build Artifact Cleanup (removes build/, dist/, .spec, .iss)
"""

import os
import sys
import shutil
import hashlib
import importlib.util
import importlib.metadata
import subprocess
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
RELEASES_DIR = PROJECT_ROOT / "releases"
TOOLS_DIR = PROJECT_ROOT / "tools"
INNO_DIR = TOOLS_DIR / "InnoSetup"
ISCC_EXE = INNO_DIR / "ISCC.exe"
RESOURCES_DIR = PROJECT_ROOT / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
APP_ICO = ICONS_DIR / "app.ico"
LOGO_PNG = RESOURCES_DIR / "UI" / "assets" / "logo.png"
LOGO_JPG = ICONS_DIR / "logo.jpg"

APP_NAME = "OMML Converter"
APP_VERSION = "11.19.26"
RELEASE_TAG = f"v.{APP_VERSION}"
INSTALLER_BASENAME = f"OMML_Converter_Setup_{RELEASE_TAG}"

INNO_SETUP_DOWNLOAD_URL = "https://github.com/jrsoftware/issrc/releases/download/is-6_3_3/innosetup-6.3.3.exe"


def log(msg: str):
    print(f"[build_release] {msg}")


ICON_CORNER_RADIUS_RATIO = 0.20


def _build_rounded_icon_rgba(source: "Image.Image", size: int, radius_ratio: float = ICON_CORNER_RADIUS_RATIO) -> "Image.Image":
    """Composite source onto an opaque white background and apply anti-aliased rounded corners."""
    from PIL import Image, ImageDraw

    # Work at high resolution (4x supersampling) for crisp anti-aliased corner edges
    scale = 4
    hi_size = max(size * scale, 256)
    fg = source.convert("RGBA").resize((hi_size, hi_size), Image.Resampling.LANCZOS)
    white_bg = Image.new("RGBA", (hi_size, hi_size), (255, 255, 255, 255))
    composited = Image.alpha_composite(white_bg, fg)

    radius = max(1, round(hi_size * radius_ratio))
    mask = Image.new("L", (hi_size, hi_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (hi_size - 1, hi_size - 1)], radius=radius, fill=255)

    composited.putalpha(mask)
    if hi_size != size:
        composited = composited.resize((size, size), Image.Resampling.LANCZOS)
    return composited


def _ico_is_valid_rounded(ico_path: Path) -> bool:
    """Return True if app.ico has transparent rounded corners and an opaque white interior."""
    from PIL import Image

    with Image.open(ico_path) as ico:
        sizes = ico.info.get("sizes") or [ico.size]
        if (256, 256) not in sizes:
            return False
        ico.size = (256, 256)
        ico.load()
        rgba = ico.convert("RGBA")
        # Outer 4 corners must be transparent
        corners = [
            rgba.getpixel((0, 0))[3],
            rgba.getpixel((255, 0))[3],
            rgba.getpixel((0, 255))[3],
            rgba.getpixel((255, 255))[3],
        ]
        # Interior white region (top-center) must be fully opaque white
        top_center = rgba.getpixel((128, 12))
        return all(a == 0 for a in corners) and top_center == (255, 255, 255, 255)


def ensure_icon(force: bool = False):
    """Ensure resources/icons/app.ico exists with opaque white body and rounded corners."""
    if not force and APP_ICO.exists():
        try:
            if _ico_is_valid_rounded(APP_ICO):
                return
            log(f"Existing {APP_ICO} does not have rounded white-background corners; regenerating...")
        except Exception:
            pass
    log(f"Generating rounded white-background icon {APP_ICO}...")
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        if LOGO_PNG.exists():
            source = Image.open(LOGO_PNG).convert("RGBA")
        elif LOGO_JPG.exists():
            source = Image.open(LOGO_JPG).convert("RGBA")
        else:
            raise FileNotFoundError(f"No source logo found at {LOGO_PNG} or {LOGO_JPG}")

        sizes = [16, 24, 32, 48, 64, 128, 256]
        frames = [_build_rounded_icon_rgba(source, s) for s in sizes]
        # Save largest frame as primary and attach all smaller supersampled frames
        frames[-1].save(
            str(APP_ICO),
            format="ICO",
            append_images=frames[:-1],
            sizes=[(s, s) for s in sizes],
        )
        log(f"Generated rounded {APP_ICO} successfully.")
    except Exception as e:
        log(f"Warning: Failed to generate app.ico: {e}")


def ensure_inno_setup() -> Path:
    """Ensure Inno Setup compiler (ISCC.exe) is present in tools/InnoSetup."""
    if ISCC_EXE.exists():
        return ISCC_EXE

    log("Inno Setup compiler not found in tools/InnoSetup. Downloading installer...")
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    installer_path = TOOLS_DIR / "innosetup_setup.exe"

    try:
        urllib.request.urlretrieve(INNO_SETUP_DOWNLOAD_URL, str(installer_path))
        log(f"Downloaded Inno Setup installer ({installer_path.stat().st_size:,} bytes).")
        log(f"Installing Inno Setup silently into {INNO_DIR}...")
        cmd = [
            str(installer_path),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f"/DIR={INNO_DIR}",
        ]
        res = subprocess.run(cmd, check=True)
        if res.returncode != 0:
            raise RuntimeError(f"Inno Setup installation returned non-zero exit code: {res.returncode}")
    finally:
        if installer_path.exists():
            installer_path.unlink()

    if not ISCC_EXE.exists():
        raise FileNotFoundError(f"ISCC.exe was not created at expected path: {ISCC_EXE}")

    log(f"Inno Setup ready at: {ISCC_EXE}")
    return ISCC_EXE


def clean_intermediate_artifacts():
    """Remove build directories and temporary packaging files."""
    log("Cleaning temporary build artifacts...")
    for d in [PROJECT_ROOT / "build", PROJECT_ROOT / "dist"]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    for f in PROJECT_ROOT.glob("*.spec"):
        try:
            f.unlink()
        except OSError:
            pass

    for f in PROJECT_ROOT.glob("*.iss"):
        try:
            f.unlink()
        except OSError:
            pass


def _collect_installed_ocr_metadata() -> list[str]:
    """Collect distribution names whose .dist-info metadata PaddleX/PaddleOCR check at runtime."""
    dist_candidates = {
        "aiohttp", "aistudio-sdk", "attrs", "bce-python-sdk", "certifi",
        "chardet", "charset-normalizer", "colorlog", "filelock", "ftfy",
        "httpx", "huggingface-hub", "idna", "imagesize", "Jinja2",
        "latex2mathml", "lxml", "modelscope", "numpy", "opencv-contrib-python",
        "opencv-python", "openpyxl", "opt-einsum", "packaging", "paddleocr",
        "paddlepaddle", "paddlex", "pandas", "pillow", "prettytable",
        "py-cpuinfo", "pyclipper", "pydantic", "pydantic-core", "pypdfium2",
        "python-bidi", "python-docx", "PyYAML", "quast-core", "requests",
        "ruamel.yaml", "safetensors", "shapely", "tokenizers", "tqdm",
        "typing-extensions", "ujson", "urllib3", "yarl",
    }
    try:
        import paddlex.utils.deps as pdx_deps
        dist_candidates.update(pdx_deps.BASE_DEP_SPECS.keys())
        for extra_map in pdx_deps.EXTRAS.values():
            dist_candidates.update(extra_map.keys())
    except Exception:
        pass

    installed = []
    seen = set()
    for name in sorted(dist_candidates, key=str.lower):
        try:
            dist = importlib.metadata.distribution(name)
            canonical = dist.metadata["Name"]
            key = canonical.lower()
            if key not in seen:
                seen.add(key)
                installed.append(canonical)
        except importlib.metadata.PackageNotFoundError:
            pass
    return installed


def run_pyinstaller() -> Path:
    """Freeze application into dist/OMML Converter via PyInstaller."""
    log("Running PyInstaller to compile application binaries...")

    dist_app_dir = PROJECT_ROOT / "dist" / APP_NAME
    entry_script = PROJECT_ROOT / "app" / "app.py"

    # Locate offline PP-FormulaNet_plus-M model weights for Image OCR bundling
    model_candidates = [
        RESOURCES_DIR / "models" / "PP-FormulaNet_plus-M",
        Path.home() / ".paddlex" / "official_models" / "PP-FormulaNet_plus-M",
    ]
    local_formula_model = next((p for p in model_candidates if p.is_dir()), None)

    collect_packages = [
        "quast_core",
        "docx",
        "latex2mathml",
        "paddle",
        "paddleocr",
        "paddlex",
        "cv2",
        "tokenizers",
        "safetensors",
        "pypdfium2",
        "pypdfium2_raw",
        "ftfy",
        "shapely",
        "pyclipper",
        "imagesize",
        "scipy",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(APP_ICO),
        "--add-data",
        f"{RESOURCES_DIR};resources",
        "--add-data",
        f"{PROJECT_ROOT / 'screenshots'};screenshots",
        "--add-data",
        f"{PROJECT_ROOT / 'README.md'};.",
    ]
    for pkg in collect_packages:
        if importlib.util.find_spec(pkg) is not None:
            cmd.extend(["--collect-all", pkg])
    for dist_name in _collect_installed_ocr_metadata():
        cmd.extend(["--copy-metadata", dist_name])
    cmd.extend([
        "--paths",
        str(PROJECT_ROOT / "app"),
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "maturin",
        "--exclude-module",
        "torch",
    ])
    if local_formula_model is not None:
        log(f"Bundling offline formula OCR model: {local_formula_model}")
        cmd.extend(["--add-data", f"{local_formula_model};resources/models/PP-FormulaNet_plus-M"])
    else:
        log("Warning: PP-FormulaNet_plus-M not found locally; packaged Image OCR will use Tier 2 fallback.")
    cmd.append(str(entry_script))

    log(f"PyInstaller command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    target_exe = dist_app_dir / f"{APP_NAME}.exe"
    if not target_exe.exists():
        raise FileNotFoundError(f"PyInstaller output executable missing: {target_exe}")

    log(f"PyInstaller build succeeded: {target_exe} ({target_exe.stat().st_size:,} bytes).")
    return dist_app_dir


def generate_inno_script(dist_app_dir: Path) -> Path:
    """Generate Inno Setup compilation script (.iss)."""
    iss_file = PROJECT_ROOT / "OMML_Converter.iss"
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)

    iss_content = f"""[Setup]
AppId={{{{5D99B167-3A21-4E65-9B2F-9C8F31E8D2E4}}}}
AppName={APP_NAME}
AppVersion={APP_VERSION}
AppPublisher=OOPS52 - QUAST
DefaultDirName={{autopf}}\\{APP_NAME}
DefaultGroupName={APP_NAME}
OutputDir={RELEASES_DIR}
OutputBaseFilename={INSTALLER_BASENAME}
SetupIconFile={APP_ICO}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={{app}}\\{APP_NAME}.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "{dist_app_dir}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"; IconFilename: "{{app}}\\_internal\\resources\\icons\\app.ico"
Name: "{{group}}\\{{cm:UninstallProgram,{APP_NAME}}}"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"; Tasks: desktopicon; IconFilename: "{{app}}\\_internal\\resources\\icons\\app.ico"

[Run]
Filename: "{{app}}\\{APP_NAME}.exe"; Description: "{{cm:LaunchProgram,{APP_NAME}}}"; Flags: nowait postinstall skipifsilent
"""
    iss_file.write_text(iss_content, encoding="utf-8")
    log(f"Generated Inno Setup script: {iss_file}")
    return iss_file


def compile_installer(iss_file: Path) -> Path:
    """Compile the single-file installer using ISCC.exe."""
    log(f"Compiling Windows installer via {ISCC_EXE}...")
    cmd = [str(ISCC_EXE), str(iss_file)]
    subprocess.run(cmd, check=True)

    installer_exe = RELEASES_DIR / f"{INSTALLER_BASENAME}.exe"
    if not installer_exe.exists():
        raise FileNotFoundError(f"Compiled installer missing: {installer_exe}")

    return installer_exe


def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    log("=== Starting Automated Single-File Release Packaging Pipeline ===")
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)

    ensure_icon()
    ensure_inno_setup()

    # Step 1: Clean previous builds
    clean_intermediate_artifacts()

    # Step 2: PyInstaller freeze
    dist_app_dir = run_pyinstaller()

    # Step 3: Generate Inno Setup script
    iss_file = generate_inno_script(dist_app_dir)

    # Step 4: Compile Inno Setup installer
    installer_exe = compile_installer(iss_file)

    # Step 5: Post-build cleanup
    clean_intermediate_artifacts()

    # Step 6: Report
    size_mb = installer_exe.stat().st_size / (1024 * 1024)
    sha256 = calculate_sha256(installer_exe)

    print("\n" + "=" * 80)
    print("PACKAGE BUILD COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"Installer Executable : {installer_exe}")
    print(f"Version              : {RELEASE_TAG}")
    print(f"File Size            : {size_mb:.2f} MB ({installer_exe.stat().st_size:,} bytes)")
    print(f"SHA-256 Checksum     : {sha256}")
    print("Package Type         : Single-file Windows Installer (Inno Setup 6, LZMA2 Solid)")
    print(f"Application Target   : {APP_NAME} ({RELEASE_TAG})")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
