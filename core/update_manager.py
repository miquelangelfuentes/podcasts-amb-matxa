"""Eines independents de la interfície per actualitzar el paquet de Windows.

Les actualitzacions són releases publicades, no commits de desenvolupament.
La còpia del paquet només comença quan l'executable actual s'ha tancat.
"""

import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f"Versió de release incorrecta: {value!r}")
    return tuple(int(item) for item in match.groups())


def is_newer_release(installed_version: str, remote_tag: str) -> bool:
    return parse_version(remote_tag) > parse_version(installed_version)


def get_windows_asset(release: dict) -> dict:
    """Selecciona només el ZIP Windows de la release indicada, no altres adjunts."""
    version = parse_version(release.get("tag_name", ""))
    expected = "PodcastsAmbMatxa-v{}.{}.{}-Windows.zip".format(*version)
    for asset in release.get("assets", []):
        if asset.get("name") == expected and asset.get("browser_download_url", "").startswith(
            "https://github.com/"
        ):
            return asset
    raise ValueError(f"La release no conté l'executable oficial de Windows ({expected}).")


def extract_windows_release(zip_path: str, destination: str) -> str:
    """Valida l'estructura i evita extraccions fora del directori temporal."""
    with zipfile.ZipFile(zip_path) as archive:
        names = {entry.filename for entry in archive.infolist()}
        required = {
            "PodcastsAmbMatxa/PodcastsAmbMatxa.exe",
            "PodcastsAmbMatxa/_internal/assets/previews/preview_styletts_2_joana.wav",
            "PodcastsAmbMatxa/_internal/assets/previews/preview_styletts_2_enric.wav",
        }
        missing = required - names
        if missing:
            raise ValueError("El paquet de Windows no és complet: " + ", ".join(sorted(missing)))

        for entry in archive.infolist():
            normalized = entry.filename.replace("\\", "/")
            parts = PurePosixPath(normalized).parts
            mode = (entry.external_attr >> 16) & 0xFFFF
            if (
                normalized != entry.filename
                or not parts
                or parts[0] != "PodcastsAmbMatxa"
                or any(part in (".", "..") for part in parts)
                or normalized.startswith("/")
                or ":" in normalized
                or stat.S_ISLNK(mode)
            ):
                raise ValueError(f"Ruta no permesa dins del ZIP: {entry.filename!r}")
        archive.extractall(destination)

    root = os.path.join(destination, "PodcastsAmbMatxa")
    if not os.path.isfile(os.path.join(root, "PodcastsAmbMatxa.exe")):
        raise ValueError("L'executable no existeix després d'extreure el paquet.")
    return root


def _ps_literal(path: str) -> str:
    """Escapa cometes simples en literals de PowerShell (incloent-hi noms d'usuari)."""
    return "'" + str(path).replace("'", "''") + "'"


def make_windows_update_script(
    source_dir: str,
    install_dir: str,
    exe_path: str,
    parent_pid: int,
    version: str,
    staging_dir: str,
) -> str:
    """Genera un ajudant extern que espera la sortida del procés i verifica la còpia."""
    parse_version(version)
    for path in (source_dir, install_dir, exe_path, staging_dir):
        if not os.path.isabs(path):
            raise ValueError(f"La ruta d'actualització ha de ser absoluta: {path!r}")
    if not parent_pid or int(parent_pid) < 1:
        raise ValueError("Identificador de procés invàlid.")

    src = _ps_literal(source_dir)
    dst = _ps_literal(install_dir)
    exe = _ps_literal(exe_path)
    stage = _ps_literal(staging_dir)
    log_name = _ps_literal(f"PodcastsAmbMatxa-update-v{version}.log")
    return f"""$ErrorActionPreference = 'Stop'
$SourceDir = {src}
$TargetDir = {dst}
$TargetExe = {exe}
$StageDir = {stage}
$ParentPid = {int(parent_pid)}
$LogPath = Join-Path $env:TEMP {log_name}
try {{
    Add-Content -LiteralPath $LogPath -Value "Iniciant actualitzacio v{version}."
    $limit = (Get-Date).AddSeconds(120)
    while (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {{
        if ((Get-Date) -gt $limit) {{
            throw "L'aplicacio anterior encara esta oberta. Tanqueu-la i torneu-ho a provar."
        }}
        Start-Sleep -Milliseconds 500
    }}
    Start-Sleep -Milliseconds 750
    if (-not (Test-Path -LiteralPath (Join-Path $SourceDir 'PodcastsAmbMatxa.exe'))) {{
        throw "No s'ha trobat el nou executable."
    }}
    # /E preserva les dades de l'usuari. /XD preserva els models existents.
    # /IS /IT evita ometre binaris encara que la marca temporal coincideixi.
    & robocopy.exe $SourceDir $TargetDir /E /IS /IT /R:6 /W:2 /COPY:DAT /DCOPY:DA /XD models .venv /NP /NFL /NDL /NJH /NJS
    $copyCode = $LASTEXITCODE
    Add-Content -LiteralPath $LogPath -Value "Robocopy exit code: $copyCode"
    if ($copyCode -ge 8) {{
        throw "La copia dels fitxers ha fallat (robocopy: $copyCode)."
    }}
    if (-not (Test-Path -LiteralPath $TargetExe)) {{
        throw "No s'ha trobat l'executable actualitzat."
    }}
    $newHash = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'PodcastsAmbMatxa.exe') -Algorithm SHA256).Hash
    $installedHash = (Get-FileHash -LiteralPath $TargetExe -Algorithm SHA256).Hash
    if ($newHash -ne $installedHash) {{
        throw "La verificacio de l'executable copiat ha fallat."
    }}
    Add-Content -LiteralPath $LogPath -Value 'Copia completada i verificada.'
    Start-Process -FilePath $TargetExe -WorkingDirectory $TargetDir
    Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
}} catch {{
    $message = $_.Exception.Message
    Add-Content -LiteralPath $LogPath -Value ("ERROR: " + $message)
    try {{
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            "No s'ha pogut completar l'actualitzacio: " + $message + "\nConsulteu: " + $LogPath,
            'Error en actualitzar Podcasts amb Matxa',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    }} catch {{}}
    exit 1
}}
"""
