"""
Finestra Modal de Comprovació d'Actualitzacions i Versió (Version Check Modal).
Permet verificar si la versió local instal·lada està al dia amb el repositori
oficial de GitHub (miquelangelfuentes/podcasts-amb-estil-i-matxa) i permet
descarregar i aplicar actualitzacions automàticament.
"""

import os
import sys
import time
import json
import zipfile
import tempfile
import threading
import subprocess
import webbrowser
import requests
import customtkinter as ctk
from typing import Optional, Dict, Any

from ui.theme import MatchaTheme
from ui.components import CleanButton


APP_VERSION = "1.1.1"
GITHUB_OWNER = "miquelangelfuentes"
GITHUB_REPO = "podcasts-amb-estil-i-matxa"


class VersionCheckModal(ctk.CTkToplevel):
    """Diàleg modal de verificació de noves versions i actualització de l'aplicació."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Comprovació de versió — Pòdcasts amb Matxa")
        self.geometry("640x560")
        self.minsize(580, 480)
        self.configure(fg_color=MatchaTheme.BG_MAIN)
        self.transient(parent)
        self.grab_set()

        self._set_modal_icon()
        self._update_available = False
        self._latest_commit_sha = ""
        self._latest_commit_msg = ""
        self._latest_release_tag = ""
        self._is_updating = False

        self._build_ui()
        self._start_check_thread()

    def _set_modal_icon(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, "assets", "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

    def _build_ui(self):
        # 1. Capçalera
        header = ctk.CTkFrame(self, fg_color=MatchaTheme.BG_CARD, corner_radius=12, border_width=1, border_color=MatchaTheme.BORDER_CARD)
        header.pack(fill="x", padx=18, pady=(16, 10))

        title_lbl = ctk.CTkLabel(
            header,
            text="Comprovació de versió i actualitzacions",
            font=MatchaTheme.FONT_TITLE,
            text_color=MatchaTheme.TEXT_MAIN
        )
        title_lbl.pack(anchor="w", padx=16, pady=(12, 2))

        desc_lbl = ctk.CTkLabel(
            header,
            text="Comprova si hi ha millores, correccions o noves veus disponibles\nal repositori oficial del projecte a GitHub.",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_SECONDARY,
            justify="left"
        )
        desc_lbl.pack(anchor="w", padx=16, pady=(0, 12))

        # 2. Targeta d'estat de versió
        self.status_card = ctk.CTkFrame(self, fg_color=MatchaTheme.BG_CARD, corner_radius=10, border_width=1, border_color=MatchaTheme.BORDER_CARD)
        self.status_card.pack(fill="x", padx=18, pady=(0, 10))

        # Fila versió local
        ver_row = ctk.CTkFrame(self.status_card, fg_color="transparent")
        ver_row.pack(fill="x", padx=16, pady=(12, 6))

        local_lbl = ctk.CTkLabel(
            ver_row,
            text=f"Versió instal·lada a l'equip:  v{APP_VERSION}",
            font=MatchaTheme.FONT_SUBTITLE,
            text_color=MatchaTheme.TEXT_MAIN
        )
        local_lbl.pack(side="left")

        # Fila d'estat de connexió i diagnòstic
        self.state_lbl = ctk.CTkLabel(
            self.status_card,
            text="Connectant amb GitHub per comprovar novetats...",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED,
            wraplength=580,
            justify="left"
        )
        self.state_lbl.pack(anchor="w", padx=16, pady=(0, 6))

        # Barra de progrés
        self.prog_bar = ctk.CTkProgressBar(self.status_card, height=6, corner_radius=3, fg_color=MatchaTheme.BG_CARD_SUBTLE, progress_color=MatchaTheme.PRIMARY)
        self.prog_bar.pack(fill="x", padx=16, pady=(0, 12))
        self.prog_bar.configure(mode="indeterminate")
        self.prog_bar.start()

        # 3. Contenidor de canvis recents amb ajust de línia automàtic (word-wrap)
        changes_header = ctk.CTkFrame(self, fg_color="transparent")
        changes_header.pack(fill="x", padx=18, pady=(4, 4))

        self.changes_title = ctk.CTkLabel(
            changes_header,
            text="Darreres novetats del projecte:",
            font=MatchaTheme.FONT_SMALL_BOLD,
            text_color=MatchaTheme.TEXT_MAIN
        )
        self.changes_title.pack(side="left")

        self.commits_box = ctk.CTkTextbox(
            self,
            fg_color=MatchaTheme.BG_CARD,
            border_width=1,
            border_color=MatchaTheme.BORDER_CARD,
            corner_radius=8,
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MAIN,
            wrap="word",
            activate_scrollbars=True
        )
        self.commits_box.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self.commits_box.insert("1.0", "Obtenint informació de les darreres novetats...")
        self.commits_box.configure(state="disabled")

        # 4. Peu d'accions
        footer = ctk.CTkFrame(self, fg_color=MatchaTheme.BG_CARD, height=52, corner_radius=12, border_width=1, border_color=MatchaTheme.BORDER_CARD)
        footer.pack(fill="x", padx=18, pady=(0, 16))
        footer.pack_propagate(False)

        self.btn_update = CleanButton(
            footer,
            style="primary",
            text="⬇️ Actualitza l'aplicació",
            width=180,
            height=32,
            command=self._on_update_clicked
        )
        self.btn_update.pack(side="left", padx=12, pady=10)
        self.btn_update.configure(state="disabled")

        self.btn_github = CleanButton(
            footer,
            style="ghost",
            text="🌐 Obre a GitHub",
            width=130,
            height=32,
            command=self._open_github_repo
        )
        self.btn_github.pack(side="left", padx=4, pady=10)

        btn_close = CleanButton(
            footer,
            style="ghost",
            text="Tanca",
            width=80,
            height=32,
            command=self.destroy
        )
        btn_close.pack(side="right", padx=12, pady=10)

    def _start_check_thread(self):
        t = threading.Thread(target=self._check_github_worker, daemon=True)
        t.start()

    def _check_github_worker(self):
        time.sleep(0.3)
        try:
            headers = {"User-Agent": "PodcastsAmbMatxa-Updater"}
            commits_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits?per_page=5"

            res = requests.get(commits_url, headers=headers, timeout=12)
            if res.status_code == 200:
                commits = res.json()
                if commits and len(commits) > 0:
                    latest = commits[0]
                    self._latest_commit_sha = latest.get("sha", "")[:7]
                    commit_msg = latest.get("commit", {}).get("message", "").split("\n")[0]
                    self._latest_commit_msg = commit_msg
                    author = latest.get("commit", {}).get("author", {}).get("name", "Autor")
                    date_str = latest.get("commit", {}).get("author", {}).get("date", "")[:10]

                    # Recopilar llista de canvis
                    change_lines = []
                    for c in commits:
                        sha = c.get("sha", "")[:7]
                        msg = c.get("commit", {}).get("message", "").split("\n")[0]
                        dt = c.get("commit", {}).get("author", {}).get("date", "")[:10]
                        change_lines.append(f"• [{sha}] {msg}\n  ({dt})")

                    changes_text = "\n\n".join(change_lines)

                    self.after(0, lambda: self._on_check_success(self._latest_commit_sha, commit_msg, changes_text))
                    return

            # Si falla commits, intentem releases
            rel_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
            r_rel = requests.get(rel_url, headers=headers, timeout=10)
            if r_rel.status_code == 200:
                rel = r_rel.json()
                tag = rel.get("tag_name", "v1.0.0")
                body = rel.get("body", "Sense notes de la versió.")
                self.after(0, lambda: self._on_check_success(tag, tag, body))
                return

            self.after(0, lambda: self._on_check_error(f"Codi de resposta de GitHub: {res.status_code}"))

        except Exception as e:
            self.after(0, lambda: self._on_check_error(str(e)))

    def _on_check_success(self, version_or_sha: str, summary: str, details: str):
        try:
            self.prog_bar.stop()
            self.prog_bar.configure(mode="determinate")
            self.prog_bar.set(1.0)
        except Exception:
            pass

        # Mostrem missatge
        self.state_lbl.configure(
            text=f"Darrer estat al repositori: {version_or_sha}\n{summary}",
            wraplength=580,
            text_color=MatchaTheme.TEXT_MAIN
        )
        self.commits_box.configure(state="normal")
        self.commits_box.delete("1.0", "end")
        self.commits_box.insert("1.0", details)
        self.commits_box.configure(state="disabled")
        self._update_available = True
        self.btn_update.configure(state="normal")

    def _on_check_error(self, err_msg: str):
        try:
            self.prog_bar.stop()
            self.prog_bar.configure(mode="determinate")
            self.prog_bar.set(0.0)
        except Exception:
            pass

        self.state_lbl.configure(
            text=f"No s'ha pogut connectar amb GitHub per verificar la versió.\n({err_msg})",
            wraplength=580,
            text_color="#c0392b"
        )
        self.commits_box.configure(state="normal")
        self.commits_box.delete("1.0", "end")
        self.commits_box.insert(
            "1.0",
            "Revisa la connexió a internet o visita directament el repositori a GitHub per descarregar actualitzacions manuals."
        )
        self.commits_box.configure(state="disabled")

    def _open_github_repo(self):
        webbrowser.open(f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}")

    def _on_update_clicked(self):
        if self._is_updating:
            return
        self._is_updating = True
        self.btn_update.configure(state="disabled", text="⏳ Descarregant...")

        t = threading.Thread(target=self._run_auto_update, daemon=True)
        t.start()

    def _run_auto_update(self):
        try:
            temp_dir = tempfile.gettempdir()
            zip_path = os.path.join(temp_dir, "podcasts_update.zip")

            if getattr(sys, "frozen", False):
                # En executable compilat, descarregar el paquet binari oficial de la darrera release
                rel_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
                zip_url = None
                try:
                    r_rel = requests.get(rel_url, timeout=10)
                    if r_rel.status_code == 200:
                        for a in r_rel.json().get("assets", []):
                            if a.get("name", "").endswith(".zip"):
                                zip_url = a.get("browser_download_url")
                                break
                except Exception:
                    pass
                if not zip_url:
                    zip_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest/download/PodcastsAmbMatxa-v{APP_VERSION}-Windows.zip"
            else:
                zip_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/main.zip"

            self.after(0, lambda: self.state_lbl.configure(text="Descarregant el paquet més recent des de GitHub...", text_color=MatchaTheme.PRIMARY))

            # Descarregar zip
            r = requests.get(zip_url, stream=True, timeout=120)
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

            self.after(0, lambda: self.state_lbl.configure(text="Descomprimint fitxers d'actualització...", text_color=MatchaTheme.PRIMARY))

            extract_dir = os.path.join(temp_dir, "podcasts_update_extracted")
            if os.path.exists(extract_dir):
                import shutil
                shutil.rmtree(extract_dir, ignore_errors=True)
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)

            # Trobar directori arrel del zip
            subdirs = [os.path.join(extract_dir, d) for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
            source_root = subdirs[0] if subdirs else extract_dir

            # Si estem en entorn de desenvolupament (font directe)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if not getattr(sys, "frozen", False):
                # Còpia de fitxers de codi (preservant models i .venv)
                for item in os.listdir(source_root):
                    if item in [".venv", "models", ".git", "dist", "build"]:
                        continue
                    s = os.path.join(source_root, item)
                    d = os.path.join(base_dir, item)
                    if os.path.isdir(s):
                        import shutil
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        import shutil
                        shutil.copy2(s, d)

                self.after(0, lambda: self._on_update_completed("L'aplicació s'ha actualitzat correctament amb la darrera versió de GitHub!\nReinicia l'aplicació per carregar els canvis."))
            else:
                # Si estem en binari congelat (.exe)
                # Creem script de reemplaçament per lot que espera a que es tanqui l'aplicació
                exe_dir = os.path.dirname(sys.executable)
                bat_path = os.path.join(temp_dir, "update_podcasts.bat")
                bat_content = f"""@echo off
echo Actualitzant Podcasts amb Matxa...
timeout /t 2 /nobreak > nul
robocopy "{source_root}" "{exe_dir}" /E /XO /XD models .venv /R:2 /W:2 > nul
start "" "{sys.executable}"
del "%~f0"
"""
                with open(bat_path, "w", encoding="utf-8") as bf:
                    bf.write(bat_content)

                self.after(0, lambda: self._prompt_restart_updater(bat_path))

        except Exception as e:
            self.after(0, lambda: self.state_lbl.configure(text=f"Error en l'actualització: {e}", text_color="#c0392b"))
            self.after(0, lambda: self.btn_update.configure(state="normal", text="Reintenta actualitzar"))
            self._is_updating = False

    def _on_update_completed(self, msg: str):
        self.state_lbl.configure(text="✅ Actualització completada amb èxit!", text_color="#27ae60")
        self.btn_update.configure(state="disabled", text="✅ Actualitzat")
        from tkinter import messagebox
        messagebox.showinfo("Actualització completada", msg)

    def _prompt_restart_updater(self, bat_path: str):
        from tkinter import messagebox
        res = messagebox.askyesno(
            "Reiniciar per actualitzar",
            "L'actualització s'ha preparat correctament.\n\n"
            "L'aplicació s'ha de tancar ara per copiar els fitxers nous i es reiniciarà automàticament en un parell de segons.\n\n"
            "Vols reiniciar ara?"
        )
        if res:
            subprocess.Popen([bat_path], shell=True)
            sys.exit(0)
        else:
            self.state_lbl.configure(text="Actualització preparada. S'aplicarà en la propera sessió.", text_color=MatchaTheme.TEXT_MAIN)
            self.btn_update.configure(state="normal", text="Aplica ara")
