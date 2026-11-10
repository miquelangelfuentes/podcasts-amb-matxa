"""
Script de Compilació Automatitzada per a Linux (Executable / Paquet autònom).
Utilitza PyInstaller per crear un paquet autònom per a distribucions Linux
(Ubuntu, Debian, Fedora, Arch, Linkat, Linux Mint, etc.).
"""

import os
import sys
import shutil
import subprocess
import tarfile
import time

from ui.version_check_modal import APP_VERSION


def build_linux():
    print("=" * 60)
    print(f"  Iniciant compilació de 'Pòdcasts amb Matxa' v{APP_VERSION} (Linux)")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, "dist")

    # Assegurar la carpeta de models abans de PyInstaller.
    # Els binaris neuronals són opcionals i es descarreguen amb el gestor de models.
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    models_readme = os.path.join(models_dir, "README.txt")
    if not os.path.exists(models_readme):
        with open(models_readme, "w", encoding="utf-8") as f:
            f.write("Els models de veu es poden descarregar des del gestor de components de Pòdcasts amb Matxa.\n")
    icon_png = os.path.join(base_dir, "assets", "icon_minimal.png")

    target_dist = os.path.join(dist_dir, "PodcastsAmbMatxa-Linux")
    if os.path.exists(target_dist):
        shutil.rmtree(target_dist, ignore_errors=True)

    # A Linux, el separador per a --add-data és ':' en lloc de ';'
    sep = ":" if sys.platform != "win32" else ";"

    # Localitzar espeak-ng-data de piper si està instal·lat
    piper_data_arg = []
    try:
        import piper
        piper_data_dir = os.path.join(os.path.dirname(piper.__file__), "espeak-ng-data")
        if os.path.exists(piper_data_dir):
            piper_data_arg = [f"--add-data={piper_data_dir}{sep}piper/espeak-ng-data"]
    except Exception:
        pass

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=PodcastsAmbMatxa",
        "--noconsole",
        "--onedir",
        "--clean",
        "-y",
        f"--distpath={dist_dir}",
        f"--add-data={os.path.join(base_dir, 'assets')}{sep}assets",
        f"--add-data={os.path.join(base_dir, 'docs')}{sep}docs",
        f"--add-data={os.path.join(base_dir, 'examples')}{sep}examples",
        f"--add-data={os.path.join(base_dir, 'models')}{sep}models",
        *piper_data_arg,
        "--collect-all=customtkinter",
        "--collect-all=imageio_ffmpeg",
        "--collect-all=soundfile",
        "--collect-all=edge_tts",
        "--collect-all=pyttsx3",
        "--collect-all=piper",
        "--collect-all=pathvalidate",
        "--exclude-module=piper.train",
        "--exclude-module=torch",
        "--hidden-import=piper",
        "--hidden-import=piper.voice",
        "--hidden-import=scipy.signal",
        "--hidden-import=scipy.special",
        "--hidden-import=pygame",
        "--hidden-import=onnxruntime",
        "--hidden-import=yaml",
        "--hidden-import=pydub",
        "--hidden-import=requests",
        "--hidden-import=aiohttp",
        "--hidden-import=aiohappyeyeballs",
        "--hidden-import=tabulate",
        "--hidden-import=uuid",
        "--hidden-import=asyncio",
        "--hidden-import=edge_tts",
        "--hidden-import=pyttsx3",
        os.path.join(base_dir, "app.py")
    ]

    print("Executant PyInstaller per a Linux...")
    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        built_dir = os.path.join(dist_dir, "PodcastsAmbMatxa")
        tar_name = f"PodcastsAmbMatxa-v{APP_VERSION}-Linux-x86_64.tar.gz"
        tar_path = os.path.join(dist_dir, tar_name)

        print(f"\nEmpaquetant a arxiu comprimit: {tar_name}...")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(built_dir, arcname="PodcastsAmbMatxa")

        tar_mb = os.path.getsize(tar_path) / (1024 * 1024)
        print("\n" + "=" * 60)
        print("  [OK] Compilació per a Linux COMPLETADA AMB ÈXIT!")
        print(f"  Arxiu comprimit generat a: {tar_path} ({tar_mb:.1f} MB)")
        print("=" * 60)
    else:
        print("\n[ERROR] La compilació per a Linux ha fallat.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build_linux()
