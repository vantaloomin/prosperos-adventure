"""Build the self-contained Windows x64 bundle: python scripts/package/build_bundle.py

The bundle carries its own Python runtime (the python.org NuGet package, pinned by digest), the
locked runtime dependencies as Windows wheels, the backend and the built interface, so it installs
and launches without Python, Node or Prospero's Study. Run `npm run build` first. Dependencies
are fetched with `--platform win_amd64`, so the bundle can be assembled on any host; on Windows
the bytecode is also precompiled for a faster first launch.

Output in build/package/: ProsperoDungeon-<version>-win-x64.zip and SHA256SUMS.txt.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dungeon.identity import APP_ID, APP_NAME, SCHEMA_VERSION, VERSION  # noqa: E402

PYTHON_VERSION = '3.12.10'
PYTHON_URL = f'https://api.nuget.org/v3-flatcontainer/python/{PYTHON_VERSION}/python.{PYTHON_VERSION}.nupkg'
PYTHON_SHA256 = '0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8'
BUNDLE_DIR = 'ProsperoDungeon'
LAUNCHER = 'Prospero Dungeon.cmd'
MANIFEST = 'bundle.json'
# Development tools in the lockfile that the installed app never imports.
DEV_ONLY = {'pytest', 'ruff', 'iniconfig', 'pluggy', 'pygments', 'packaging'}
# Runtime pieces only needed to build extensions or install packages.
RUNTIME_PRUNE = ('include', 'libs', 'Scripts', 'Lib/site-packages/pip', 'Lib/ensurepip/_bundled')
# The runtime reads only these paths: PYTHONPATH, PYTHONHOME and the user's site-packages are
# ignored, so another Python or Prospero's Study on the machine cannot change what loads.
PTH = 'DLLs\nLib\n.\nLib\\site-packages\n..\\app\nimport site\n'
LAUNCHER_TEXT = (
    '@echo off\r\n'
    'rem Starts Prospero Dungeon with its own Python runtime. Keep this window open while you use it.\r\n'
    'setlocal\r\n'
    '"%~dp0runtime\\python.exe" -I -m dungeon.launch %*\r\n'
    'exit /b %ERRORLEVEL%\r\n')


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            sha.update(block)
    return sha.hexdigest()


def fetch_runtime(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    package = cache / f'python.{PYTHON_VERSION}.nupkg'
    if not package.exists() or digest(package) != PYTHON_SHA256:
        print(f'Downloading Python {PYTHON_VERSION} runtime', flush=True)
        partial = package.with_suffix('.partial')
        with urllib.request.urlopen(PYTHON_URL, timeout=120) as response, partial.open('wb') as handle:
            shutil.copyfileobj(response, handle)
        partial.replace(package)
    found = digest(package)
    if found != PYTHON_SHA256:
        raise SystemExit(f'The Python runtime digest does not match: {found}')
    return package


def extract_runtime(package: Path, runtime: Path):
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            if not member.filename.startswith('tools/') or member.is_dir():
                continue
            target = runtime / member.filename[len('tools/'):]
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open('wb') as handle:
                shutil.copyfileobj(source, handle)
    for relative in RUNTIME_PRUNE:
        shutil.rmtree(runtime / relative, ignore_errors=True)
    for leftover in (runtime / 'Lib' / 'site-packages').glob('pip-*.dist-info'):
        shutil.rmtree(leftover)
    (runtime / 'python312._pth').write_text(PTH, encoding='utf-8')


def for_windows(marker: str) -> bool:
    """pip judges markers by the host, so they are resolved here for the Windows target."""
    from pip._vendor.packaging.markers import Marker
    return Marker(marker).evaluate({'sys_platform': 'win32', 'platform_system': 'Windows', 'os_name': 'nt',
                                    'platform_machine': 'AMD64', 'python_version': '3.12',
                                    'python_full_version': PYTHON_VERSION, 'implementation_name': 'cpython',
                                    'platform_python_implementation': 'CPython'})


def runtime_requirements(scratch: Path) -> Path:
    lines = []
    for line in (ROOT / 'requirements.lock.txt').read_text(encoding='utf-8').splitlines():
        requirement, _, marker = line.partition(';')
        name = requirement.split('==')[0].strip().lower()
        if requirement.strip() and not line.startswith('#') and name not in DEV_ONLY \
                and (not marker.strip() or for_windows(marker.strip())):
            lines.append(requirement.strip())
    path = scratch / 'runtime-requirements.txt'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def install_dependencies(requirements: Path, site_packages: Path):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-deps',
                    '--only-binary=:all:', '--platform', 'win_amd64', '--implementation', 'cp',
                    '--python-version', '3.12', '--abi', 'cp312', '--target', str(site_packages),
                    '--no-compile', '-r', str(requirements)], check=True)
    shutil.rmtree(site_packages / 'bin', ignore_errors=True)


def copy_app(app: Path):
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo')
    shutil.copytree(ROOT / 'dungeon', app / 'dungeon', ignore=ignore)
    shutil.copytree(ROOT / 'dist', app / 'dist')
    shutil.copy2(ROOT.parent / 'LICENSE', app / 'LICENSE')


def compile_bytecode(bundle: Path):
    """Only the bundled interpreter can write bytecode it will use, so this runs on Windows only."""
    if os.name != 'nt':
        print('Skipping bytecode compilation: it needs the Windows runtime.', flush=True)
        return
    subprocess.run([str(bundle / 'runtime' / 'python.exe'), '-I', '-m', 'compileall', '-q', '-j', '0',
                    str(bundle / 'app'), str(bundle / 'runtime' / 'Lib')], check=True)


def file_list(bundle: Path) -> dict:
    files = {}
    for path in sorted(bundle.rglob('*')):
        relative = path.relative_to(bundle).as_posix()
        if path.is_file() and relative != MANIFEST and '__pycache__' not in relative:
            files[relative] = digest(path)
    return files


def commit() -> str:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def write_archive(bundle: Path, archive_path: Path):
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                archive.write(path, Path(BUNDLE_DIR) / path.relative_to(bundle))


def build(output: Path, cache: Path) -> Path:
    if not (ROOT / 'dist' / 'index.html').is_file():
        raise SystemExit('Build the interface first: npm run build')
    package = fetch_runtime(cache)
    shutil.rmtree(output, ignore_errors=True)
    bundle = output / BUNDLE_DIR
    extract_runtime(package, bundle / 'runtime')
    install_dependencies(runtime_requirements(output), bundle / 'runtime' / 'Lib' / 'site-packages')
    copy_app(bundle / 'app')
    (bundle / LAUNCHER).write_bytes(LAUNCHER_TEXT.encode('ascii'))
    compile_bytecode(bundle)
    manifest = {'app_id': APP_ID, 'app_name': APP_NAME, 'version': VERSION, 'schema_version': SCHEMA_VERSION,
                'platform': 'win-x64', 'python': PYTHON_VERSION, 'commit': commit(), 'files': file_list(bundle)}
    (bundle / MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    archive_path = output / f'ProsperoDungeon-{VERSION}-win-x64.zip'
    write_archive(bundle, archive_path)
    (output / 'SHA256SUMS.txt').write_text(f'{digest(archive_path)}  {archive_path.name}\n', encoding='utf-8')
    print(f'Built {archive_path} ({archive_path.stat().st_size // (1 << 20)} MiB, '
          f"{len(manifest['files'])} files)", flush=True)
    return archive_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=ROOT / 'build' / 'package')
    parser.add_argument('--cache', type=Path, default=ROOT / 'build' / 'cache')
    args = parser.parse_args(argv)
    build(args.output.resolve(), args.cache.resolve())


if __name__ == '__main__':
    main()
