"""
Script de Compilació Automatitzada a Executable Windows (.exe).
Utilitza PyInstaller per crear un paquet independent i autònom
amb l'aplicació 'Pòdcasts amb Matxa'.
"""

import os
import sys
import shutil
import subprocess
import time
import zipfile

from ui.version_check_modal import APP_VERSION

def build():
    print("=" * 60)
    print("  Iniciant compilació de 'Pòdcasts amb Matxa' (.exe)")
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
    build_dir = os.path.join(base_dir, "build")
    icon_path = os.path.join(base_dir, "assets", "icon.ico")

    # Tancar instancies previes obertes a Windows per alliberar bloquejos de fitxers
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "PodcastsAmbMatxa.exe"], capture_output=True)
        except Exception:
            pass
        time.sleep(1)

    # Neteja preventiva del directori destí amb reintents
    target_dist = os.path.join(dist_dir, "PodcastsAmbMatxa")
    if os.path.exists(target_dist):
        for _ in range(5):
            try:
                shutil.rmtree(target_dist, ignore_errors=True)
                if not os.path.exists(target_dist):
                    break
            except Exception:
                pass
            time.sleep(1)

    staging_dist = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "pm_stg")
    if os.path.exists(staging_dist):
        shutil.rmtree(staging_dist, ignore_errors=True)

    # Ordre PyInstaller amb el nou nom oficial i sortida a directori staging
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=PodcastsAmbMatxa",
        "--noconsole",
        "--onedir",
        "--clean",
        "-y",
        f"--icon={icon_path}",
        f"--distpath={staging_dist}",
        # Dades i carpetes de recursos
        f"--add-data={os.path.join(base_dir, 'assets')};assets",
        f"--add-data={os.path.join(base_dir, 'docs')};docs",
        f"--add-data={os.path.join(base_dir, 'examples')};examples",
        f"--add-data={os.path.join(base_dir, 'models')};models",
        f"--add-data={os.path.join(os.path.dirname(__import__('piper').__file__), 'espeak-ng-data')};piper/espeak-ng-data",
        # Recollida de mòduls essencials amb binaris
        "--collect-all=customtkinter",
        "--collect-all=imageio_ffmpeg",
        "--collect-all=soundfile",
        "--collect-all=edge_tts",
        "--collect-all=pyttsx3",
        "--collect-all=piper",
        "--collect-all=pathvalidate",
        "--exclude-module=piper.train",
        "--exclude-module=torch",
        # Imports ocults per a àudio i xarxa
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

    print("Executant PyInstaller amb la comanda:")
    print(" ".join(cmd))
    print("-" * 60)

    def robust_copy(src, dst):
        """Còpia segura de directoris que gestiona rutes llargues a Windows (MAX_PATH)."""
        if sys.platform == "win32":
            subprocess.run(["robocopy", src, dst, "/MIR", "/R:2", "/W:1", "/NP"], check=False)
        else:
            shutil.copytree(src, dst, dirs_exist_ok=True)

    result = subprocess.run(cmd, cwd=base_dir)
    if result.returncode == 0:
        built_dir = os.path.join(staging_dist, "PodcastsAmbMatxa")
        new_dist = os.path.join(dist_dir, "PodcastsAmbMatxa")
        os.makedirs(new_dist, exist_ok=True)
        print(f"\nCopiant fitxers generats a {new_dist}...")
        robust_copy(built_dir, new_dist)

        exe_path = os.path.join(new_dist, "PodcastsAmbMatxa.exe")
        print("\n" + "=" * 60)
        print("  [OK] Compilació de PodcastsAmbMatxa COMPLETADA AMB ÈXIT!")
        print(f"  Executable generat a:")
        print(f"  {exe_path}")

        # Empaquetar a fitxer ZIP oficial amb el nom de la versió actual
        zip_name = f"PodcastsAmbMatxa-v{APP_VERSION}-Windows.zip"
        zip_path = os.path.join(dist_dir, zip_name)
        print(f"\n  Empaquetant a arxiu comprimit oficial: {zip_name}...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(new_dist):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, dist_dir)
                    zipf.write(full_path, rel_path)
        zip_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"  [OK] Fitxer ZIP generat amb èxit ({zip_mb:.1f} MB):")
        print(f"  {zip_path}")

        # Sincronitzar còpia directa al directori Downloads de l'usuari si existeix
        user_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.exists(user_downloads):
            try:
                dest_zip_downloads = os.path.join(user_downloads, zip_name)
                shutil.copy2(zip_path, dest_zip_downloads)
                print(f"  [OK] Còpia de descàrrega sincronitzada a: {dest_zip_downloads}")
                # Sincronitzar també la carpeta extreta per a execució immediata
                unzipped_target = os.path.join(user_downloads, f"PodcastsAmbMatxa-v{APP_VERSION}-Windows", "PodcastsAmbMatxa")
                if os.path.exists(os.path.dirname(unzipped_target)):
                    robust_copy(new_dist, unzipped_target)
                    print(f"  [OK] Carpeta d'execució extreta actualitzada a: {unzipped_target}")
            except Exception as e:
                print(f"  [AVÍS] No s'ha pogut copiar a Downloads: {e}")

        # Neteja del directori staging temporal
        try:
            shutil.rmtree(staging_dist, ignore_errors=True)
        except Exception:
            pass

        print("=" * 60)
    else:
        print("\n[ERROR] La compilació ha fallat.")
        sys.exit(result.returncode)

if __name__ == "__main__":
    build()
