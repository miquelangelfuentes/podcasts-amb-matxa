"""
Finestra Principal de l'Aplicació: Pòdcasts amb Matxa.
Disseny modern, elegant, accessible i minimalista (Clean Studio UI).
Garanteix conformitat estricta amb el contrast de colors (WCAG AAA):
- Fons verds -> SEMPRE text blanc pur (#FFFFFF). Mai text fosc sobre verd.
- Fons clars -> SEMPRE text fosc d'alta llegibilitat (#142419).
"""

import os
import re
import sys
import threading
import ctypes
import webbrowser
import queue
import tempfile
from typing import Optional, List, Dict
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image
import numpy as np
import soundfile as sf
import pygame

# Habilitar suport per a pantalles d'alta resolució (High-DPI) a Windows
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor DPI Aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from ui.theme import MatchaTheme
from ui.components import PillSelector, CleanButton
from ui.components_modal import ComponentsManagerModal
from ui.player_widget import AudioPlayerWidget
from core.script_parser import ScriptParser, PodcastScript, SpeakerConfig
from core.tts_engine import MicrosoftNeuralCatalanEngine
from core.matxa_tts_engine import MatxaTTSCatalanEngine
from core.upc_ona_engine import UPCOnaCatalanEngine
from core.audio_processor import AudioProcessor
from core.voice_preview import VoicePreviewManager
from ui.version_check_modal import VersionCheckModal, APP_VERSION

class MainWindow(ctk.CTk):
    """Finestra principal d'estudi de pòdcasts amb interfície moderna i accessible."""

    MATXA_VOICE_DESCRIPTIONS = {
        "elia": "Èlia — Central (Fem, didàctica)",
        "grau": "Grau — Central (Masc, dinàmic)",
        "ona": "Ona — Central (Fem, institucional)",
        "pau": "Pau — Central (Masc, narratiu)",
        "olga": "Olga — Balear (Fem, Mallorca)",
        "quim": "Quim — Balear (Masc, Menorca)",
        "bm": "Bernat — Balear (Masc, Mallorca)",
        "gina": "Gina — Valencià (Fem, càlida)",
        "lluc": "Lluc — Valencià (Masc, natural)",
        "arnau": "Arnau — Valencià (Masc, dinàmic)",
        "berta": "Berta — Valencià (Fem, expressiva)",
        "emma": "Emma — Nord-occidental (Fem, Lleida)",
        "pere": "Pere — Nord-occidental (Masc, Lleida)",
        "estel": "Estel — Nord-occidental (Fem, Pirineu)",
        "laura": "Laura — Septentrional (Fem, Rosselló)",
        "jordi": "Jordi — Septentrional (Masc, Perpinyà)"
    }

    NEURAL_VOICE_DESCRIPTIONS = {
        "ona": "Ona — Veu expressiva (Fem, càlida i professional)",
        "pau": "Pau — Veu expressiva (Masc, dinàmic i proper)",
        "bet": "Bet — Veu expressiva (Fem, didàctica i expressiva)",
        "jordi": "Jordi — Veu expressiva (Masc, acadèmic)",
        "teia": "Teia — Veu expressiva (Fem, narrativa)",
        "pere": "Pere — Veu expressiva (Masc, valencià natural)",
        "lluc": "Lluc — Veu expressiva (Masc, balear mallorquí)",
        "joana": "Joana — Microsoft Neural (Fem, ca-ES estàndard)",
        "enric": "Enric — Microsoft Neural (Masc, ca-ES estàndard)"
    }

    MICROSOFT_VOICE_DESCRIPTIONS = {
        "joana": "Joana — Microsoft Neural (Fem, ca-ES estàndard)",
        "enric": "Enric — Microsoft Neural (Masc, ca-ES estàndard)"
    }

    UPC_VOICE_DESCRIPTIONS = {
        "ona": "Ona — UPC FestCat (Fem, d'alta fidelitat 100% offline)",
        "pau": "Pau — UPC FestCat (Masc, d'alta fidelitat 100% offline)"
    }

    def __init__(self):
        super().__init__()

        # Configuració bàsica de la finestra i títol renovat.
        # CustomTkinter escala les dimensions segons el DPI de Windows;
        # adaptem la geometria a l'àrea útil de treball per no superar la pantalla a 150%.
        self.title(f"Pòdcasts amb Matxa v{APP_VERSION}")
        self._fit_window_to_work_area()

        # Configuració d'aparença neta
        ctk.set_appearance_mode("light")
        self.configure(fg_color=MatchaTheme.BG_MAIN)

        # Icona de l'aplicació per a la finestra i la barra de tasques de Windows
        self._set_app_icon()

        # Cua thread-safe per a comunicació segura entre fils secundaris i Tkinter
        self._ui_queue = queue.Queue()
        self.after(35, self._process_ui_queue)

        # Motors interns: per defecte s'obre amb Matxa-TTS v2 (100% Offline)
        self.script_parser = ScriptParser()
        self.matxa_engine = MatxaTTSCatalanEngine()
        self.upc_engine = UPCOnaCatalanEngine()
        self.neural_engine = MicrosoftNeuralCatalanEngine()
        self.tts_engine = self.matxa_engine
        self.audio_processor = AudioProcessor(sample_rate=self.tts_engine.sample_rate)
        self.voice_preview_manager = VoicePreviewManager()

        self.current_script = PodcastScript()
        self.ui_speaker_overrides = {}
        self._suppress_script_sync = False
        self._internal_mode_update = False
        self.is_generating = False
        self.cancel_requested = False

        # Mode d'edició: 'clean' (només diàlegs) o 'full' (codi .txt complet)
        self.editor_mode = "clean"
        self._raw_script_full = ""

        # Configuració de pista / música de fons
        self.bg_music_path: Optional[str] = None
        self.bg_music_loop: bool = True
        self.bg_music_ducking: bool = True
        self.bg_music_volume: float = 0.15
        self.bg_music_audio_data: Optional[np.ndarray] = None
        self._bg_preview_sound = None
        self._bg_preview_timer_id = None
        self._is_bg_previewing: bool = False

        self._build_ui()
        self._bind_keyboard_shortcuts()
        self._load_default_sample()

    def _get_logical_work_area(self):
        """Retorna l'àrea útil de pantalla en unitats lògiques de CustomTkinter."""
        try:
            window_scale = max(float(self._get_window_scaling()), 0.1)
        except Exception:
            window_scale = 1.0

        physical_w = self.winfo_screenwidth()
        physical_h = self.winfo_screenheight()

        if sys.platform.startswith("win"):
            try:
                from ctypes import wintypes
                rect = wintypes.RECT()
                SPI_GETWORKAREA = 0x0030
                ok = ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
                )
                if ok:
                    physical_w = rect.right - rect.left
                    physical_h = rect.bottom - rect.top
            except Exception:
                pass

        return int(physical_w / window_scale), int(physical_h / window_scale)

    def _fit_window_to_work_area(self):
        """Evita que la finestra inicial superi l'àrea útil després de l'escalat DPI."""
        work_w, work_h = self._get_logical_work_area()

        target_w = max(1000, min(1280, work_w - 24))
        target_h = max(620, min(840, work_h - 24))

        min_w = min(1020, target_w)
        min_h = min(620, target_h)
        self.minsize(min_w, min_h)
        self.geometry(f"{target_w}x{target_h}")

    def _set_app_icon(self):
        """Assigna la silueta geomètrica del chawan tant a la finestra com a la barra de tasques."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, "assets", "icon.ico")
        png_path = os.path.join(base_dir, "assets", "icon.png")

        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass
        if os.path.exists(png_path):
            try:
                self._icon_img = tk.PhotoImage(file=png_path)
                self.iconphoto(True, self._icon_img)
            except Exception:
                pass

    def safe_after(self, func):
        self._ui_queue.put(func)

    def _process_ui_queue(self):
        try:
            while not self._ui_queue.empty():
                task = self._ui_queue.get_nowait()
                try:
                    task()
                except Exception as e:
                    print(f"Error executant tasca segura d'UI: {e}")
        finally:
            self.after(35, self._process_ui_queue)

    def _build_ui(self):
        # 1. Barra Superior Minimalista (Clean Studio Navbar)
        header = ctk.CTkFrame(
            self,
            fg_color=MatchaTheme.BG_CARD,
            height=58,
            corner_radius=0,
            border_width=1,
            border_color=MatchaTheme.BORDER_CARD
        )
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=20, pady=10)

        # Logotip de la icona incrustada
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "assets", "icon_minimal.png")
        if os.path.exists(icon_path):
            try:
                pil_icon = Image.open(icon_path)
                self._header_icon_img = ctk.CTkImage(light_image=pil_icon, dark_image=pil_icon, size=(24, 24))
                icon_lbl = ctk.CTkLabel(brand_frame, image=self._header_icon_img, text="")
                icon_lbl.pack(side="left", padx=(0, 8))
            except Exception:
                pass

        app_title = ctk.CTkLabel(
            brand_frame,
            text="Pòdcasts amb Matxa",
            font=("Segoe UI", 16, "bold"),
            text_color=MatchaTheme.TEXT_MAIN
        )
        app_title.pack(side="left", padx=(0, 6))

        version_badge = ctk.CTkLabel(
            brand_frame,
            text=f"v{APP_VERSION}",
            font=MatchaTheme.FONT_TINY,
            fg_color=MatchaTheme.PRIMARY_LIGHT,
            text_color=MatchaTheme.PRIMARY,
            corner_radius=8,
            padx=7,
            pady=1
        )
        version_badge.pack(side="left", padx=(0, 8))

        tag_badge = ctk.CTkLabel(
            brand_frame,
            text="IA · CATALÀ",
            font=MatchaTheme.FONT_TINY,
            fg_color=MatchaTheme.PRIMARY_LIGHT,
            text_color=MatchaTheme.PRIMARY,
            corner_radius=8,
            padx=7,
            pady=1
        )
        tag_badge.pack(side="left", padx=(0, 10))

        self.badge = ctk.CTkLabel(
            brand_frame,
            text="BSC-LT Matxa-TTS v2 (100% Offline) & alVoCat 22kHz",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED
        )
        self.badge.pack(side="left")

        # Insígnia de mode escola (oculta per defecte, visible quan el mode està actiu)
        self.escola_badge = ctk.CTkLabel(
            brand_frame,
            text="🛡️ Mode escola: 0% dades a internet (RGPD protegit)",
            font=MatchaTheme.FONT_SMALL_BOLD,
            fg_color="#D4EDDA",
            text_color="#1A4731",
            corner_radius=8,
            padx=8,
            pady=2
        )
        # No es fa pack() aquí; s'activa amb _toggle_escola_mode

        # Botons d'ajuda i accessibilitat a la dreta amb contrast accessible
        help_frame = ctk.CTkFrame(header, fg_color="transparent")
        help_frame.pack(side="right", padx=18, pady=10)

        scale_lbl = ctk.CTkLabel(
            help_frame,
            text="Mida:",
            font=MatchaTheme.FONT_SMALL_BOLD,
            text_color=MatchaTheme.TEXT_MUTED
        )
        scale_lbl.pack(side="left", padx=(0, 4))

        self.scale_combo = ctk.CTkComboBox(
            help_frame,
            values=["100%", "125%", "150%", "175%", "200%"],
            width=80,
            height=28,
            corner_radius=14,
            fg_color=MatchaTheme.BG_CARD_SUBTLE,
            border_color=MatchaTheme.BORDER_CARD,
            button_color=MatchaTheme.PRIMARY,
            button_hover_color=MatchaTheme.PRIMARY_HOVER,
            text_color=MatchaTheme.TEXT_MAIN,
            font=MatchaTheme.FONT_SMALL,
            dropdown_font=MatchaTheme.FONT_SMALL,
            dropdown_text_color=MatchaTheme.TEXT_MAIN,
            command=self._on_scale_change
        )
        self.scale_combo.pack(side="left", padx=(0, 10))
        self.scale_combo.set("100%")

        btn_ssml = CleanButton(
            help_frame,
            style="ghost",
            text="Guia SSML",
            width=85,
            height=28,
            command=self._show_ssml_guide
        )
        btn_ssml.pack(side="left", padx=3)

        btn_llm = CleanButton(
            help_frame,
            style="ghost",
            text="Indicació per a models",
            width=145,
            height=28,
            command=self._show_llm_guide
        )
        btn_llm.pack(side="left", padx=3)

        btn_models = CleanButton(
            help_frame,
            style="ghost",
            text="📦 Models",
            width=85,
            height=28,
            command=self._show_components_manager
        )
        btn_models.pack(side="left", padx=3)

        btn_version = CleanButton(
            help_frame,
            style="ghost",
            text="🔄 Comprova versió",
            width=135,
            height=28,
            command=self._show_version_check_modal
        )
        btn_version.pack(side="left", padx=3)

        # Commutador «Mode escola 100% offline» — inhabilita el motor al núvol
        self._escola_mode = False
        self.btn_escola = CleanButton(
            help_frame,
            style="ghost",
            text="🏫 Mode escola",
            width=110,
            height=28,
            command=self._toggle_escola_mode
        )
        self.btn_escola.pack(side="left", padx=3)

        # 2. Barra d'estructura de veus global a la part superior (1 veu, 2 veus o 3 veus)
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=18, pady=(12, 4))

        format_label = ctk.CTkLabel(
            top_bar,
            text="Estructura del pòdcast:",
            font=MatchaTheme.FONT_SMALL_BOLD,
            text_color=MatchaTheme.TEXT_MUTED
        )
        format_label.pack(side="left", padx=(4, 10))

        self.voices_mode_seg = PillSelector(
            top_bar,
            values=["👤 1 veu (monòleg)", "👥 2 veus (diàleg)", "👥👥 3 veus (amb presentador)"],
            default_val="👥👥 3 veus (amb presentador)",
            height=32,
            font_size=10,
            command=self._on_voice_mode_change
        )
        self.voices_mode_seg.pack(side="left")

        # 3. Peu de pàgina (Footer) amb autoria i llicències
        footer = ctk.CTkFrame(
            self,
            fg_color=MatchaTheme.BG_CARD,
            height=32,
            corner_radius=0,
            border_width=1,
            border_color=MatchaTheme.BORDER_CARD
        )
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        footer_box = ctk.CTkFrame(footer, fg_color="transparent")
        footer_box.pack(anchor="center", pady=6)

        lbl_author = ctk.CTkLabel(
            footer_box,
            text="Aplicació creada mitjançant codificació per intencions amb Google Antigravity per Miquel Àngel Fuentes · ",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED
        )
        lbl_author.pack(side="left")

        lbl_code = ctk.CTkLabel(
            footer_box,
            text="Llicència de codi: ",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED
        )
        lbl_code.pack(side="left")

        link_agpl = ctk.CTkLabel(
            footer_box,
            text="AGPL v3",
            font=(MatchaTheme.FONT_FAMILY, 10, "underline"),
            text_color=MatchaTheme.PRIMARY,
            cursor="hand2"
        )
        link_agpl.pack(side="left")
        link_agpl.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://www.gnu.org/licenses/agpl-3.0.en.html"))

        lbl_sep = ctk.CTkLabel(
            footer_box,
            text=" · Continguts: ",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED
        )
        lbl_sep.pack(side="left")

        link_cc = ctk.CTkLabel(
            footer_box,
            text="CC BY-SA 4.0",
            font=(MatchaTheme.FONT_FAMILY, 10, "underline"),
            text_color=MatchaTheme.PRIMARY,
            cursor="hand2"
        )
        link_cc.pack(side="left")
        link_cc.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://creativecommons.org/licenses/by-sa/4.0/deed.es"))

        lbl_credits = ctk.CTkLabel(
            footer_box,
            text=" · Models: BSC-LT, UPC & Projecte AINA",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED
        )
        lbl_credits.pack(side="left")

        # 4. Contenidor Principal Dividit
        content_container = ctk.CTkFrame(self, fg_color="transparent")
        content_container.pack(fill="both", expand=True, padx=18, pady=(8, 8))

        # Panell Esquerre (L'Estudi de Guió)
        left_panel = ctk.CTkFrame(
            content_container,
            fg_color=MatchaTheme.BG_CARD,
            corner_radius=MatchaTheme.CARD_RADIUS,
            border_width=1,
            border_color=MatchaTheme.BORDER_CARD
        )
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self._build_editor_panel(left_panel)

        # Panell Dret (La Taula de Producció)
        right_panel = ctk.CTkFrame(content_container, fg_color="transparent", width=540)
        right_panel.pack(side="right", fill="both", padx=(10, 0))
        right_panel.pack_propagate(False)

        self._build_control_panel(right_panel)

    def _build_editor_panel(self, parent):
        # 1. Barra d'eines superior de l'editor
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=18, pady=(14, 8))

        section_lbl = ctk.CTkLabel(
            toolbar,
            text="📝 Estudi de guió",
            font=MatchaTheme.FONT_SUBTITLE,
            text_color=MatchaTheme.TEXT_MAIN
        )
        section_lbl.pack(side="left")

        actions_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions_box.pack(side="right")

        # Botó d'exemple de 5 minuts (text blanc sobre fons verd fosc per contrast impecable)
        btn_sample = CleanButton(
            actions_box,
            style="primary",
            text="🌟 Guió de 5 min",
            height=28,
            command=self._load_default_sample
        )
        btn_sample.pack(side="left", padx=3)

        # Desplegable de plantilles
        self.template_opt = ctk.CTkOptionMenu(
            actions_box,
            values=[
                "Plantilles...",
                "🌟 Guió de 5 min (com funciona l'aplicació)",
                "👤 1 veu: com funciona (monòleg)",
                "👥 2 veus: com funciona (diàleg)",
                "👥👥 3 veus: com funciona (tertúlia)"
            ],
            width=140,
            height=28,
            corner_radius=14,
            fg_color=MatchaTheme.BG_CARD_SUBTLE,
            button_color=MatchaTheme.PRIMARY,
            button_hover_color=MatchaTheme.PRIMARY_HOVER,
            text_color=MatchaTheme.TEXT_MAIN,
            font=MatchaTheme.FONT_SMALL,
            dropdown_font=MatchaTheme.FONT_SMALL,
            dropdown_text_color=MatchaTheme.TEXT_MAIN,
            command=self._on_template_selected
        )
        self.template_opt.pack(side="left", padx=3)
        self.template_opt.set("Plantilles...")

        btn_open = CleanButton(
            actions_box,
            style="ghost",
            text="Obrir",
            width=65,
            height=28,
            command=self._open_script_file
        )
        btn_open.pack(side="left", padx=3)

        btn_save = CleanButton(
            actions_box,
            style="ghost",
            text="Desar",
            width=65,
            height=28,
            command=self._save_script_file
        )
        btn_save.pack(side="left", padx=3)

        # 2. Camp separat per al Títol de l'Episodi (Elimina la necessitat d'escriure [TITOL:...])
        title_box = ctk.CTkFrame(parent, fg_color="transparent")
        title_box.pack(fill="x", padx=18, pady=(0, 8))

        lbl_titol = ctk.CTkLabel(
            title_box,
            text="Títol del pòdcast:",
            font=MatchaTheme.FONT_SMALL_BOLD,
            text_color=MatchaTheme.TEXT_SECONDARY
        )
        lbl_titol.pack(side="left", padx=(0, 8))

        self.title_entry = ctk.CTkEntry(
            title_box,
            placeholder_text="Escriu el títol del pòdcast...",
            height=30,
            corner_radius=8,
            fg_color=MatchaTheme.ENTRY_BG,
            border_color=MatchaTheme.ENTRY_BORDER,
            text_color=MatchaTheme.TEXT_MAIN,
            font=("Segoe UI", 11, "bold")
        )
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.title_entry.bind("<KeyRelease>", self._on_title_modified)

        # 3. Àrea de text de l'editor
        self.script_textbox = ctk.CTkTextbox(
            parent,
            fg_color=MatchaTheme.ENTRY_BG,
            border_color=MatchaTheme.ENTRY_BORDER,
            border_width=1,
            text_color=MatchaTheme.TEXT_MAIN,
            font=MatchaTheme.FONT_MONO,
            wrap="word",
            corner_radius=10
        )
        self.script_textbox.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        self.script_textbox.bind("<KeyRelease>", self._on_script_modified)

        # 4. Barra inferior de recompte i selector de mode guió
        statusbar = ctk.CTkFrame(parent, fg_color="transparent")
        statusbar.pack(fill="x", padx=18, pady=(0, 12))

        self.stats_lbl = ctk.CTkLabel(
            statusbar,
            text="0 paraules · ~00:00 min · 0 veus",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED
        )
        self.stats_lbl.pack(side="left")

        # Botó per alternar entre Mode Guió Net i Mode Codi Complet
        self.btn_toggle_view = CleanButton(
            statusbar,
            style="subtle",
            text="📝 Mode guió net (actiu)",
            height=24,
            command=self._toggle_editor_mode
        )
        self.btn_toggle_view.pack(side="right")

    def _build_control_panel(self, parent):
        # 1. El reproductor queda ancorat a la part inferior perquè les accions
        # essencials (escoltar i desar el fitxer MP3) siguin SEMPRE visibles i
        # mai quedin retallades fora de la pantalla (ex. a 150% de DPI o en pantalles petites).
        self.player_widget = AudioPlayerWidget(parent, self.audio_processor, height=1)
        self.player_widget.pack(side="bottom", fill="x", pady=(8, 0))

        # 2. Panell de controls superior desplaçable (Locutors + Generació).
        # height=1 evita heretar els 200 punts de mida desitjada per defecte de CustomTkinter.
        self.controls_scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            corner_radius=0,
            height=1
        )
        self.controls_scroll.pack(side="top", fill="both", expand=True)

        # 1. Targeta de Locutors & Panning Estèreo
        speakers_card = ctk.CTkFrame(
            self.controls_scroll,
            fg_color=MatchaTheme.BG_CARD,
            corner_radius=MatchaTheme.CARD_RADIUS,
            border_width=1,
            border_color=MatchaTheme.BORDER_CARD
        )
        speakers_card.pack(fill="x", pady=(0, 8))

        spk_header = ctk.CTkFrame(speakers_card, fg_color="transparent", height=1)
        spk_header.pack(fill="x", padx=18, pady=(10, 4))

        spk_title = ctk.CTkLabel(
            spk_header,
            text="👥 Repartiment de veus i espacialització",
            font=MatchaTheme.FONT_SUBTITLE,
            text_color=MatchaTheme.TEXT_MAIN
        )
        spk_title.pack(side="left")

        # Selector destacat de motor de veus (Matxa-TTS vs. Microsoft Neural)
        engine_row = ctk.CTkFrame(speakers_card, fg_color="transparent", height=1)
        engine_row.pack(fill="x", padx=18, pady=(2, 8))

        engine_lbl = ctk.CTkLabel(
            engine_row,
            text="Motor:",
            font=MatchaTheme.FONT_SMALL_BOLD,
            text_color=MatchaTheme.TEXT_MUTED
        )
        engine_lbl.pack(side="left", padx=(0, 8))

        self.engine_combo = ctk.CTkComboBox(
            engine_row,
            values=[
                "🍵 Matxa-TTS v2 (100% Offline — 16 veus BSC-LT)",
                "🎙️ UPC FestCat (100% Offline — Veus neuronals Ona i Pau)",
                "☁️ Veus neuronals ca-ES (Online — 9 veus expressives)"
            ],
            height=28,
            corner_radius=14,
            fg_color=MatchaTheme.BG_CARD_SUBTLE,
            border_color=MatchaTheme.BORDER_CARD,
            button_color=MatchaTheme.PRIMARY,
            button_hover_color=MatchaTheme.PRIMARY_HOVER,
            text_color=MatchaTheme.TEXT_MAIN,
            font=MatchaTheme.FONT_SMALL,
            dropdown_font=MatchaTheme.FONT_SMALL,
            dropdown_text_color=MatchaTheme.TEXT_MAIN,
            command=self._on_engine_change
        )
        self.engine_combo.pack(side="left", fill="x", expand=True)
        self.engine_combo.set("🍵 Matxa-TTS v2 (100% Offline — 16 veus BSC-LT)")

        # Contenidor per als locutors amb alçada dinàmica (evita malbaratar 180 px amb 1 sola veu)
        self.speakers_container = ctk.CTkFrame(
            speakers_card,
            fg_color=MatchaTheme.BG_CARD_SUBTLE,
            corner_radius=10,
            height=1
        )
        self.speakers_container.pack(fill="x", padx=18, pady=(0, 10))

        # 1.5 Targeta de Música o So de Fons (MP3 / WAV)
        bg_card = ctk.CTkFrame(
            self.controls_scroll,
            fg_color=MatchaTheme.BG_CARD,
            corner_radius=MatchaTheme.CARD_RADIUS,
            border_width=1,
            border_color=MatchaTheme.BORDER_CARD
        )
        bg_card.pack(fill="x", pady=(0, 8))

        bg_header = ctk.CTkFrame(bg_card, fg_color="transparent", height=1)
        bg_header.pack(fill="x", padx=18, pady=(10, 4))

        bg_title = ctk.CTkLabel(
            bg_header,
            text="🎵 Música o ambient de fons",
            font=MatchaTheme.FONT_SUBTITLE,
            text_color=MatchaTheme.TEXT_MAIN
        )
        bg_title.pack(side="left")

        # Fila 1: Selecció de fitxer
        file_row = ctk.CTkFrame(bg_card, fg_color="transparent", height=1)
        file_row.pack(fill="x", padx=18, pady=(2, 6))

        self.btn_select_bg = CleanButton(
            file_row,
            style="subtle",
            text="📂 Triar MP3...",
            height=28,
            command=self._select_bg_audio
        )
        self.btn_select_bg.pack(side="left", padx=(0, 8))

        self.lbl_bg_file = ctk.CTkLabel(
            file_row,
            text="Sense pista de fons",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED,
            anchor="w"
        )
        self.lbl_bg_file.pack(side="left", fill="x", expand=True)

        self.btn_clear_bg = CleanButton(
            file_row,
            style="ghost",
            text="✕",
            width=28,
            height=28,
            state="disabled",
            command=self._clear_bg_audio
        )
        self.btn_clear_bg.pack(side="right", padx=(4, 0))

        # Fila 2: Controls de reproducció (Bucle + Botó de prova d'escolta)
        ctrl_row = ctk.CTkFrame(bg_card, fg_color="transparent", height=1)
        ctrl_row.pack(fill="x", padx=18, pady=(2, 6))

        self.cb_bg_loop = ctk.CTkCheckBox(
            ctrl_row,
            text="🔁 Bucle",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_SECONDARY,
            checkmark_color=MatchaTheme.TEXT_ON_PRIMARY,
            fg_color=MatchaTheme.PRIMARY,
            hover_color=MatchaTheme.PRIMARY_HOVER,
            corner_radius=4,
            command=self._on_bg_loop_toggle
        )
        self.cb_bg_loop.pack(side="left", padx=(0, 10))
        self.cb_bg_loop.select()

        self.cb_bg_ducking = ctk.CTkCheckBox(
            ctrl_row,
            text="📉 Auto-ducking",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_SECONDARY,
            checkmark_color=MatchaTheme.TEXT_ON_PRIMARY,
            fg_color=MatchaTheme.PRIMARY,
            hover_color=MatchaTheme.PRIMARY_HOVER,
            corner_radius=4,
            command=self._on_bg_ducking_toggle
        )
        self.cb_bg_ducking.pack(side="left")
        self.cb_bg_ducking.select()

        self.btn_bg_preview = CleanButton(
            ctrl_row,
            style="subtle",
            text="▶ Prova",
            height=26,
            width=75,
            state="disabled",
            command=self._toggle_bg_preview
        )
        self.btn_bg_preview.pack(side="right")

        # Fila 3: Medidor i lliscador de volum
        vol_row = ctk.CTkFrame(bg_card, fg_color="transparent", height=1)
        vol_row.pack(fill="x", padx=18, pady=(2, 10))

        self.lbl_bg_volume = ctk.CTkLabel(
            vol_row,
            text="Volum: 15%",
            font=MatchaTheme.FONT_SMALL_BOLD,
            text_color=MatchaTheme.TEXT_MAIN,
            width=80,
            anchor="w"
        )
        self.lbl_bg_volume.pack(side="left", padx=(0, 8))

        self.slider_bg_volume = ctk.CTkSlider(
            vol_row,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            height=14,
            progress_color=MatchaTheme.PRIMARY,
            button_color=MatchaTheme.PRIMARY,
            button_hover_color=MatchaTheme.PRIMARY_HOVER,
            fg_color=MatchaTheme.PROGRESS_BG,
            command=self._on_bg_volume_change
        )
        self.slider_bg_volume.pack(side="left", fill="x", expand=True)
        self.slider_bg_volume.set(0.15)

        # 2. Targeta de Paràmetres & Acció de Generació
        gen_card = ctk.CTkFrame(
            self.controls_scroll,
            fg_color=MatchaTheme.BG_CARD,
            corner_radius=MatchaTheme.CARD_RADIUS,
            border_width=1,
            border_color=MatchaTheme.BORDER_CARD
        )
        gen_card.pack(fill="x", pady=(0, 2))

        gen_title = ctk.CTkLabel(
            gen_card,
            text="⚙ Masterització i paràmetres d'àudio",
            font=MatchaTheme.FONT_SUBTITLE,
            text_color=MatchaTheme.TEXT_MAIN
        )
        gen_title.pack(anchor="w", padx=18, pady=(10, 4))

        # Opcions inline netes
        opts_row = ctk.CTkFrame(gen_card, fg_color="transparent", height=1)
        opts_row.pack(fill="x", padx=18, pady=(0, 8))

        self.cb_normalizer = ctk.CTkCheckBox(
            opts_row,
            text="alVoCat (Normalitzador AINA)",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_SECONDARY,
            checkmark_color=MatchaTheme.TEXT_ON_PRIMARY,
            fg_color=MatchaTheme.PRIMARY,
            hover_color=MatchaTheme.PRIMARY_HOVER,
            corner_radius=4
        )
        self.cb_normalizer.pack(side="left", padx=(0, 14))
        self.cb_normalizer.select()

        self.cb_lufs = ctk.CTkCheckBox(
            opts_row,
            text="EBU R128 (-16 LUFS)",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_SECONDARY,
            checkmark_color=MatchaTheme.TEXT_ON_PRIMARY,
            fg_color=MatchaTheme.PRIMARY,
            hover_color=MatchaTheme.PRIMARY_HOVER,
            corner_radius=4
        )
        self.cb_lufs.pack(side="left")
        self.cb_lufs.select()

        # Botó principal de generació (Call-to-Action destacat amb TEXT BLANC sobre fons fosc)
        btn_row = ctk.CTkFrame(gen_card, fg_color="transparent", height=1)
        btn_row.pack(fill="x", padx=18, pady=(0, 6))

        self.generate_btn = CleanButton(
            btn_row,
            style="primary",
            text="🎙️ Generar pòdcast complet",
            height=40,
            font=("Segoe UI", 12, "bold"),
            command=self._start_generation
        )
        self.generate_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.cancel_btn = CleanButton(
            btn_row,
            style="danger",
            text="✕ Cancel·lar",
            width=85,
            height=40,
            state="disabled",
            command=self._cancel_generation
        )
        self.cancel_btn.pack(side="right")

        # Barra de progrés subtil
        self.progress_bar = ctk.CTkProgressBar(
            gen_card,
            height=6,
            corner_radius=3,
            progress_color=MatchaTheme.PRIMARY,
            fg_color=MatchaTheme.PROGRESS_BG
        )
        self.progress_bar.pack(fill="x", padx=18, pady=(3, 3))
        self.progress_bar.set(0.0)

        self.status_lbl = ctk.CTkLabel(
            gen_card,
            text="A punt per generar. Sense límit de temps.",
            font=MatchaTheme.FONT_SMALL,
            text_color=MatchaTheme.TEXT_MUTED
        )
        self.status_lbl.pack(anchor="w", padx=18, pady=(0, 10))

    def _extract_clean_dialogue(self, full_text: str) -> str:
        """Extreu exclusivament les línies de locució i pauses d'un fitxer de guió."""
        lines = full_text.splitlines()
        clean_lines = []
        is_dialogue = False

        for raw in lines:
            line = raw.strip()
            if not line:
                if is_dialogue:
                    clean_lines.append("")
                continue

            if line.startswith("---") or line.startswith("===") or line.startswith("***"):
                is_dialogue = True
                continue

            if line.startswith("[") and line.endswith("]"):
                # Mantenim pauses en el diàleg net
                if line.upper().startswith("[PAUSA") or line.upper().startswith("[PAUSE"):
                    if is_dialogue:
                        clean_lines.append(raw)
                continue

            if is_dialogue:
                clean_lines.append(raw)

        if not clean_lines:
            # Si no hi havia separador '---', retornem les línies que semblen diàlegs
            for raw in lines:
                line = raw.strip()
                if line.startswith("[") and line.endswith("]"):
                    if line.upper().startswith("[PAUSA"):
                        clean_lines.append(raw)
                    continue
                if ":" in line and not line.startswith("-"):
                    clean_lines.append(raw)

        return "\n".join(clean_lines).strip()

    def _compose_full_script(self, clean_dialogue: str) -> str:
        """Reconstrueix el fitxer .txt complet unint les capçaleres amb el diàleg net."""
        title = self.title_entry.get().strip() or "Pòdcast Educatiu"

        lines = [
            f"[TITOL: {title}]",
            "[FORMAT: Stereo 160kbps]",
            "[PAUSA_DEFECTE: 350ms]",
            "[PAUSA_INTERLOCUTOR: 700ms]",
            "",
            "[CONFIGURACIO_LOCUTORS]"
        ]

        # Identificar els locutors presents en el diàleg net (preservant ordre d'aparició)
        found_speakers = []
        dialogue_pattern = re.compile(r"^([A-ZÀ-Úa-zà-ú0-9_\-\.\s]+?)\s*:\s*(.*)$")
        for raw in clean_dialogue.splitlines():
            line = raw.strip()
            if not line or line.startswith("[") or line.startswith("-") or line.startswith("*"):
                continue
            m = dialogue_pattern.match(line)
            if m:
                spk = m.group(1).strip()
                if (len(spk.split()) <= 3 and spk[0].isupper() and 
                    not any(c in spk for c in "[]{}()<>;=\"'") and 
                    spk not in found_speakers):
                    found_speakers.append(spk)

        # Si hem detectat locutors en el diàleg net
        if found_speakers:
            if hasattr(self.tts_engine, "MATXA_SPEAKERS"):
                default_voices = ["elia", "grau", "ona", "pau", "olga", "quim", "gina", "lluc"]
                pres_voice = "elia"
            else:
                default_voices = ["joana", "enric", "ona", "pau", "bet", "jordi", "teia", "pere"]
                pres_voice = "joana"
            default_pans = [-0.25, 0.25, 0.0, -0.35, 0.35]
            assigned_idx = 0

            for spk_name in found_speakers:
                if spk_name in self.current_script.speakers:
                    spk_cfg = self.current_script.speakers[spk_name]
                    voice_id = spk_cfg.voice_id
                    pan_str = self._pan_val_to_str(spk_cfg.pan)
                else:
                    is_presenter = "presentad" in spk_name.lower()
                    if is_presenter:
                        voice_id = pres_voice
                        pan_str = "0%"
                    else:
                        voice_id = default_voices[assigned_idx % len(default_voices)]
                        pan_str = self._pan_val_to_str(default_pans[assigned_idx % len(default_pans)])
                        assigned_idx += 1
                lines.append(f"{spk_name}: veu={voice_id} pan={pan_str}")
        else:
            # Fallback si el diàleg encara està buit
            speakers = self.current_script.speakers
            if speakers:
                for spk_name, spk_cfg in speakers.items():
                    pan_str = self._pan_val_to_str(spk_cfg.pan)
                    lines.append(f"{spk_name}: veu={spk_cfg.voice_id} pan={pan_str}")
            else:
                mode = self.voices_mode_seg.get().lower()
                is_matxa = hasattr(self.tts_engine, "MATXA_SPEAKERS")
                v_fem = "elia" if is_matxa else "joana"
                v_masc = "grau" if is_matxa else "enric"
                if "1 veu" in mode:
                    lines.append(f"Veu presentadora: veu={v_fem} pan=0%")
                elif "2 veus" in mode:
                    lines.append(f"Veu 1: veu={v_fem} pan=-25%")
                    lines.append(f"Veu 2: veu={v_masc} pan=+25%")
                else:
                    lines.append(f"Veu presentadora: veu={v_fem} pan=0%")
                    lines.append(f"Veu 1: veu={v_fem} pan=-25%")
                    lines.append(f"Veu 2: veu={v_masc} pan=+25%")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(clean_dialogue)
        return "\n".join(lines)

    def _toggle_editor_mode(self):
        """Alterna entre el Mode Guió Net i el Mode Codi Complet."""
        current_content = self.script_textbox.get("1.0", "end-1c")

        if self.editor_mode == "clean":
            # Passar a Mode Codi Complet
            full_code = self._compose_full_script(current_content)
            self._raw_script_full = full_code
            self._suppress_script_sync = True
            try:
                self.script_textbox.delete("1.0", "end")
                self.script_textbox.insert("1.0", full_code)
                self.editor_mode = "full"
                self.btn_toggle_view.configure(text="⚙️ Mode codi .txt (actiu)")
            finally:
                self._suppress_script_sync = False
        else:
            # Passar a Mode Guió Net
            clean_text = self._extract_clean_dialogue(current_content)
            self._suppress_script_sync = True
            try:
                self.script_textbox.delete("1.0", "end")
                self.script_textbox.insert("1.0", clean_text)
                self.editor_mode = "clean"
                self.btn_toggle_view.configure(text="📝 Mode guió net (actiu)")
            finally:
                self._suppress_script_sync = False

        self._on_script_modified()

    def _on_title_modified(self, event=None):
        if self.editor_mode == "full":
            title = self.title_entry.get().strip()
            content = self.script_textbox.get("1.0", "end-1c")
            if re.search(r"^\[TITOL:\s*[^\]]+\]", content, flags=re.MULTILINE):
                content = re.sub(r"^\[TITOL:\s*[^\]]+\]", f"[TITOL: {title}]", content, flags=re.MULTILINE)
                self._suppress_script_sync = True
                try:
                    self.script_textbox.delete("1.0", "end")
                    self.script_textbox.insert("1.0", content)
                finally:
                    self._suppress_script_sync = False

    def _on_scale_change(self, choice: str):
        mapping = {"100%": 1.0, "125%": 1.25, "150%": 1.5, "175%": 1.75, "200%": 2.0}
        factor = mapping.get(choice, 1.0)
        try:
            ctk.set_widget_scaling(factor)
            self._fit_window_to_work_area()
        except Exception as e:
            print(f"Error aplicant escala: {e}")

    def _load_script_from_text(self, content: str, source_label: str = ""):
        """Carrega un guió a partir de text brut estructurat, actualitzant model i interfície."""
        parsed = self.script_parser.parse(content)
        self.current_script = parsed
        self.ui_speaker_overrides.clear()

        # Actualitzar el camp de títol
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, parsed.title)

        # Actualitzar l'àrea d'edició
        self._suppress_script_sync = True
        try:
            self.script_textbox.delete("1.0", "end")
            if self.editor_mode == "clean":
                self.script_textbox.insert("1.0", self._extract_clean_dialogue(content))
            else:
                self.script_textbox.insert("1.0", content)
        finally:
            self._suppress_script_sync = False

        self._update_script_stats_and_ui()
        if source_label:
            self._set_status(f"Carregat: {source_label}")

    def _on_template_selected(self, choice: str):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        examples_dir = os.path.join(base_dir, "examples")

        if "5 min" in choice:
            path = os.path.join(examples_dir, "guio_exemple_5min.txt")
        elif "1 veu" in choice.lower():
            path = os.path.join(examples_dir, "plantilla_1veu.txt")
        elif "2 veus" in choice.lower():
            path = os.path.join(examples_dir, "plantilla_2veus.txt")
        elif "3 veus" in choice.lower():
            path = os.path.join(examples_dir, "plantilla_3veus.txt")
        else:
            return

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._load_script_from_text(content, f"Plantilla carregada: {choice}")

        self.template_opt.set("Plantilles...")

    def _on_voice_mode_change(self, choice: str):
        if self._internal_mode_update:
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        examples_dir = os.path.join(base_dir, "examples")

        choice_lower = choice.lower()
        if "1 veu" in choice_lower:
            path = os.path.join(examples_dir, "plantilla_1veu.txt")
            target_name = "1 veu (monòleg amb Veu presentadora)"
        elif "2 veus" in choice_lower:
            path = os.path.join(examples_dir, "plantilla_2veus.txt")
            target_name = "2 veus (diàleg amb Veu 1 i Veu 2)"
        elif "3 veus" in choice_lower:
            path = os.path.join(examples_dir, "plantilla_3veus.txt")
            target_name = "3 veus (tertúlia amb Veu presentadora, Veu 1 i Veu 2)"
        else:
            return

        # Carregar la plantilla corresponent directament de forma fluida
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._load_script_from_text(content, f"Format canviat a {target_name}.")

    def _update_voice_mode_segment(self):
        count = len(self.current_script.speakers)
        self._internal_mode_update = True
        try:
            if count == 1:
                self.voices_mode_seg.set("👤 1 veu (monòleg)")
            elif count == 2:
                self.voices_mode_seg.set("👥 2 veus (diàleg)")
            elif count >= 3:
                self.voices_mode_seg.set("👥👥 3 veus (amb presentador)")
        finally:
            self._internal_mode_update = False

    def _get_voice_catalog(self) -> dict:
        engine_str = self.engine_combo.get() if hasattr(self, "engine_combo") else ""
        if "UPC" in engine_str:
            return self.UPC_VOICE_DESCRIPTIONS
        elif "Matxa" in engine_str:
            return self.MATXA_VOICE_DESCRIPTIONS
        elif any(k in engine_str for k in ["Online", "Microsoft", "Neural", "Expressiva"]):
            return self.NEURAL_VOICE_DESCRIPTIONS
        if hasattr(self.tts_engine, "UPC_SPEAKERS"):
            return self.UPC_VOICE_DESCRIPTIONS
        if hasattr(self.tts_engine, "MATXA_SPEAKERS"):
            return self.MATXA_VOICE_DESCRIPTIONS
        return self.MATXA_VOICE_DESCRIPTIONS

    def _get_voice_label(self, voice_id: str) -> str:
        cat = self._get_voice_catalog()
        v_key = str(voice_id).lower().strip()
        if v_key in cat:
            return cat[v_key]
        if hasattr(self, "UPC_VOICE_DESCRIPTIONS") and v_key in self.UPC_VOICE_DESCRIPTIONS:
            return self.UPC_VOICE_DESCRIPTIONS[v_key]
        if v_key in self.MATXA_VOICE_DESCRIPTIONS:
            return self.MATXA_VOICE_DESCRIPTIONS[v_key]
        if v_key in self.MICROSOFT_VOICE_DESCRIPTIONS:
            return self.MICROSOFT_VOICE_DESCRIPTIONS[v_key]
        if v_key in self.NEURAL_VOICE_DESCRIPTIONS:
            return self.NEURAL_VOICE_DESCRIPTIONS[v_key]
        return f"{v_key.capitalize()} — Català"

    def _get_voice_id_from_label(self, label: str) -> str:
        cat = self._get_voice_catalog()
        for v_id, desc in cat.items():
            if desc == label:
                return v_id
        for full_cat in (self.NEURAL_VOICE_DESCRIPTIONS, self.MATXA_VOICE_DESCRIPTIONS, self.MICROSOFT_VOICE_DESCRIPTIONS):
            for v_id, desc in full_cat.items():
                if desc == label:
                    return v_id
        first_token = label.split(" — ")[0].strip().lower()
        if first_token in cat:
            return first_token
        return label.split(" — ")[0].split()[0].lower().strip()

    def _get_available_voice_labels(self) -> list:
        return list(self._get_voice_catalog().values())

    @staticmethod
    def _pan_val_to_label(pan_val: float) -> str:
        if pan_val <= -0.38:
            return "-50% L"
        elif pan_val <= -0.12:
            return "-25% L"
        elif pan_val >= 0.38:
            return "+50% R"
        elif pan_val >= 0.12:
            return "+25% R"
        else:
            return "Centre"

    @staticmethod
    def _pan_label_to_val(label: str) -> float:
        mapping = {"-50% L": -0.50, "-25% L": -0.25, "Centre": 0.0, "+25% R": 0.25, "+50% R": 0.50}
        return mapping.get(label, 0.0)

    @staticmethod
    def _pan_val_to_str(pan_val: float) -> str:
        if abs(pan_val) < 0.05:
            return "0%"
        elif pan_val < 0:
            return f"-{int(round(abs(pan_val)*100))}%"
        else:
            return f"+{int(round(pan_val*100))}%"

    def _on_script_modified(self, event=None):
        if self._suppress_script_sync:
            return

        text = self.script_textbox.get("1.0", "end-1c")

        # Si estem en Mode Guió Net, construïm la representació completa per al parser
        if self.editor_mode == "clean":
            full_to_parse = self._compose_full_script(text)
        else:
            full_to_parse = text

        self.current_script = self.script_parser.parse(full_to_parse)

        # Si el títol del guió analitzat no coincideix amb l'entrada, actualitzem el camp si està buit
        if self.current_script.title and not self.title_entry.get().strip():
            self.title_entry.delete(0, "end")
            self.title_entry.insert(0, self.current_script.title)

        # Aplicar qualsevol override actiu de la UI per mantenir coherència
        for spk_name, overrides in self.ui_speaker_overrides.items():
            if spk_name in self.current_script.speakers:
                if "voice_id" in overrides:
                    self.current_script.speakers[spk_name].voice_id = overrides["voice_id"]
                if "pan" in overrides:
                    self.current_script.speakers[spk_name].pan = overrides["pan"]

        self._update_script_stats_and_ui()

    def _update_script_stats_and_ui(self):
        """Actualitza el recompte de paraules, el temps estimat, el mode de veus i les targetes de locutor."""
        dialogue_words = sum(len(s.text.split()) for s in self.current_script.segments if s.segment_type == "dialogue")
        est_seconds = (dialogue_words / 145.0 * 60.0) + (len(self.current_script.segments) * 0.7)
        mins = int(est_seconds // 60)
        secs = int(est_seconds % 60)

        spk_count = len(self.current_script.speakers)
        spk_names = ", ".join(list(self.current_script.speakers.keys())[:3])
        if spk_count > 3:
            spk_names += f" (+{spk_count-3})"

        self.stats_lbl.configure(
            text=f"{dialogue_words} paraules · ~{mins:02d}:{secs:02d} min · {spk_count} veus ({spk_names})"
        )

        self._update_voice_mode_segment()
        self._refresh_speakers_ui()

    def _refresh_speakers_ui(self):
        for widget in self.speakers_container.winfo_children():
            widget.destroy()

        if not self.current_script.speakers:
            no_spk = ctk.CTkLabel(
                self.speakers_container,
                text="Escriu línies com 'Veu presentadora: text' o 'Nom: text' per detectar les veus.",
                font=MatchaTheme.FONT_SMALL,
                text_color=MatchaTheme.TEXT_MUTED
            )
            no_spk.pack(padx=10, pady=16)
            return

        available_labels = self._get_available_voice_labels()
        available_ids = list(self._get_voice_catalog().keys())

        engine_choice = self.engine_combo.get() if hasattr(self, "engine_combo") else ""
        is_matxa = "Matxa" in engine_choice or hasattr(self.tts_engine, "MATXA_SPEAKERS")
        for i, (spk_name, spk_cfg) in enumerate(self.current_script.speakers.items()):
            if spk_cfg.voice_id not in available_ids:
                if "UPC" in engine_choice:
                    spk_cfg.voice_id = available_ids[min(i, len(available_ids) - 1)]
                elif is_matxa:
                    spk_cfg.voice_id = available_ids[min(i, len(available_ids) - 1)]
                elif any(k in engine_choice for k in ["Online", "Microsoft", "Neural", "Expressiva"]):
                    spk_cfg.voice_id = available_ids[min(i, len(available_ids) - 1)]
                else:
                    spk_cfg.voice_id = available_ids[0] if available_ids else "ona"

            card = ctk.CTkFrame(
                self.speakers_container,
                fg_color=MatchaTheme.BG_CARD,
                corner_radius=10,
                border_width=1,
                border_color=MatchaTheme.BORDER_CARD,
                height=1
            )
            card.pack(fill="x", padx=4, pady=4)

            # Línia 1: Nom distingit, Selector de Veu i Botó d'Escolta
            top_line = ctk.CTkFrame(card, fg_color="transparent", height=1)
            top_line.pack(fill="x", padx=10, pady=(6, 2))

            is_presenter = "presentad" in spk_name.lower()
            spk_icon = "🎙️" if is_presenter else "👤"

            spk_lbl = ctk.CTkLabel(
                top_line,
                text=f"{spk_icon} {spk_name}",
                font=MatchaTheme.FONT_BODY_BOLD,
                text_color=MatchaTheme.PRIMARY if is_presenter else MatchaTheme.TEXT_MAIN,
                width=135,
                anchor="w"
            )
            spk_lbl.pack(side="left")

            current_voice_label = self._get_voice_label(spk_cfg.voice_id)
            voice_combo = ctk.CTkComboBox(
                top_line,
                values=available_labels,
                height=26,
                corner_radius=13,
                fg_color=MatchaTheme.BG_CARD_SUBTLE,
                border_color=MatchaTheme.BORDER_CARD,
                button_color=MatchaTheme.PRIMARY,
                button_hover_color=MatchaTheme.PRIMARY_HOVER,
                text_color=MatchaTheme.TEXT_MAIN,
                font=MatchaTheme.FONT_SMALL,
                dropdown_font=MatchaTheme.FONT_SMALL,
                dropdown_text_color=MatchaTheme.TEXT_MAIN,
                command=lambda val, name=spk_name: self._on_speaker_voice_change(name, val)
            )
            voice_combo.pack(side="left", fill="x", expand=True, padx=(4, 6))
            voice_combo.set(current_voice_label)

            # Botó Escolta: Disseny suau amb text fosc o blanc quan reprodueix
            sample_btn = CleanButton(
                top_line,
                style="subtle",
                text="▶ Escolta",
                width=72,
                height=26
            )
            sample_btn.configure(command=lambda name=spk_name, btn=sample_btn: self._play_speaker_sample(name, btn))
            sample_btn.pack(side="right")

            # Línia 2: Espacialització Estèreo amb PillSelector d'alt contrast (Blanc sobre verd quan és actiu!)
            pan_line = ctk.CTkFrame(card, fg_color="transparent", height=1)
            pan_line.pack(fill="x", padx=10, pady=(2, 6))

            pan_lbl = ctk.CTkLabel(
                pan_line,
                text="Espai estèreo:",
                font=MatchaTheme.FONT_SMALL,
                text_color=MatchaTheme.TEXT_MUTED,
                width=85,
                anchor="w"
            )
            pan_lbl.pack(side="left")

            pan_seg = PillSelector(
                pan_line,
                values=["-50% L", "-25% L", "Centre", "+25% R", "+50% R"],
                default_val=self._pan_val_to_label(spk_cfg.pan),
                height=24,
                font_size=9,
                expand_buttons=True,
                command=lambda val, name=spk_name: self._on_speaker_pan_change(name, val)
            )
            pan_seg.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _on_engine_change(self, choice):
        if "UPC" in choice:
            self.tts_engine = self.upc_engine
            self.badge.configure(text="UPC FestCat Ona i Pau (Piper Neural 100% Offline) & alVoCat 22kHz")
        elif "Matxa" in choice:
            self.tts_engine = self.matxa_engine
            self.badge.configure(text="BSC-LT Matxa-TTS v2 (100% Offline) & alVoCat 22kHz")
        elif any(k in choice for k in ["Online", "Microsoft", "Neural", "Expressiva"]):
            self.tts_engine = self.neural_engine
            self.badge.configure(text="Veus neuronals ca-ES (Online — Requereix internet) & alVoCat 22kHz")
        else:
            self.tts_engine = self.matxa_engine
            self.badge.configure(text="BSC-LT Matxa-TTS v2 (100% Offline) & alVoCat 22kHz")
        self._refresh_speakers_ui()

    def _sync_speaker_config_to_editor(self, spk_name: str):
        """Si estem en mode complet, actualitza les propietats del locutor al text cru."""
        if self.editor_mode != "full":
            return
        if spk_name not in self.current_script.speakers:
            return

        spk_cfg = self.current_script.speakers[spk_name]
        pan_str = self._pan_val_to_str(spk_cfg.pan)
        voice_id = spk_cfg.voice_id

        content = self.script_textbox.get("1.0", "end-1c")
        spk_line_pattern = re.compile(rf"^(\s*{re.escape(spk_name)}\s*:\s*)([^\r\n]*)", re.MULTILINE)
        m = spk_line_pattern.search(content)
        if m:
            prefix = m.group(1)
            rest = m.group(2)
            if re.search(r'\b(?:veu|voice)=([^\s]+)', rest, flags=re.IGNORECASE):
                rest = re.sub(r'\b(?:veu|voice)=([^\s]+)', f'veu={voice_id}', rest, flags=re.IGNORECASE)
            else:
                rest = f"veu={voice_id} " + rest
            if re.search(r'\b(?:pan|panning)=([^\s]+)', rest, flags=re.IGNORECASE):
                rest = re.sub(r'\b(?:pan|panning)=([^\s]+)', f'pan={pan_str}', rest, flags=re.IGNORECASE)
            else:
                rest = rest + f" pan={pan_str}"
            new_line = f"{prefix}{rest.strip()}"
            updated = content[:m.start()] + new_line + content[m.end():]

            self._suppress_script_sync = True
            try:
                self.script_textbox.delete("1.0", "end")
                self.script_textbox.insert("1.0", updated)
            finally:
                self._suppress_script_sync = False

    def _on_speaker_voice_change(self, spk_name, voice_label):
        voice_id = self._get_voice_id_from_label(voice_label)
        if spk_name in self.current_script.speakers:
            self.current_script.speakers[spk_name].voice_id = voice_id
        if spk_name not in self.ui_speaker_overrides:
            self.ui_speaker_overrides[spk_name] = {}
        self.ui_speaker_overrides[spk_name]["voice_id"] = voice_id
        self._sync_speaker_config_to_editor(spk_name)

    def _on_speaker_pan_change(self, spk_name, pan_label):
        pan_val = self._pan_label_to_val(pan_label)
        if spk_name in self.current_script.speakers:
            self.current_script.speakers[spk_name].pan = pan_val
        if spk_name not in self.ui_speaker_overrides:
            self.ui_speaker_overrides[spk_name] = {}
        self.ui_speaker_overrides[spk_name]["pan"] = pan_val
        self._sync_speaker_config_to_editor(spk_name)

    def _set_status(self, text: str):
        if hasattr(self, "status_lbl") and self.status_lbl is not None:
            try:
                self.status_lbl.configure(text=text)
            except Exception:
                pass

    def _handle_sample_start(self, btn: CleanButton, spk_name: str, voice_id: str):
        try:
            btn.configure(
                text="🔊 ...",
                state="disabled",
                fg_color="#2E5E41",
                text_color="#FFFFFF"
            )
            self._set_status(f"Reproduint mostra de veu: {spk_name} ({voice_id})...")
        except Exception:
            pass

    def _handle_sample_complete(self, btn: CleanButton):
        try:
            btn.configure(
                text="▶ Escolta",
                state="normal",
                fg_color="#EBF3EB",
                text_color="#223E2A"
            )
            self._set_status("A punt per generar. Sense límit de temps.")
        except Exception:
            pass

    def _handle_sample_error(self, btn: CleanButton, err_msg: str):
        try:
            btn.configure(
                text="▶ Escolta",
                state="normal",
                fg_color="#EBF3EB",
                text_color="#223E2A"
            )
            self._set_status(f"Avís a la mostra: {err_msg}")
        except Exception:
            pass

    def _play_speaker_sample(self, spk_name: str, btn: CleanButton):
        if spk_name not in self.current_script.speakers:
            return
        voice_id = self.current_script.speakers[spk_name].voice_id
        engine_name = getattr(self.tts_engine, "name", "matxa")

        try:
            is_cached = self.voice_preview_manager.is_cached(engine_name, voice_id)
            if is_cached:
                btn.configure(
                    text="🔊 ...",
                    state="disabled",
                    fg_color="#2E5E41",
                    text_color="#FFFFFF"
                )
                self._set_status(f"Reproduint mostra de veu: {spk_name} ({voice_id})...")
            else:
                btn.configure(
                    text="⏳ ...",
                    state="disabled",
                    fg_color="#B8955A",
                    text_color="#FFFFFF"
                )
                self._set_status(f"Sintetitzant mostra de veu per a {spk_name} ({voice_id})...")

            def on_start():
                self.safe_after(lambda: self._handle_sample_start(btn, spk_name, voice_id))

            def on_complete():
                self.safe_after(lambda: self._handle_sample_complete(btn))

            def on_error(err_msg):
                self.safe_after(lambda: self._handle_sample_error(btn, err_msg))
                print(f"Avís reproduint mostra: {err_msg}")

            self.voice_preview_manager.play_preview(
                self.tts_engine,
                voice_id,
                on_start=on_start,
                on_complete=on_complete,
                on_error=on_error
            )
        except Exception as e:
            print(f"Error a _play_speaker_sample: {e}")
            btn.configure(
                text="▶ Escolta",
                state="normal",
                fg_color="#EBF3EB",
                text_color="#223E2A"
            )
            self._set_status(f"Error generant mostra: {e}")

    def _load_default_sample(self):
        sample_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "guio_exemple_5min.txt")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._load_script_from_text(content, "Guió de mostra de 5 minuts carregat amb èxit.")

    def _open_script_file(self):
        path = filedialog.askopenfilename(
            title="Obrir Guió de Pòdcast",
            filetypes=[("Fitxers de text (.txt)", "*.txt"), ("Tots els fitxers", "*.*")]
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._load_script_from_text(content, os.path.basename(path))

    def _save_script_file(self):
        path = filedialog.asksaveasfilename(
            title="Desar guió de pòdcast",
            defaultextension=".txt",
            filetypes=[("Fitxers de text (.txt)", "*.txt")]
        )
        if path:
            current_content = self.script_textbox.get("1.0", "end-1c")
            if self.editor_mode == "clean":
                full_to_save = self._compose_full_script(current_content)
            else:
                full_to_save = current_content

            with open(path, "w", encoding="utf-8") as f:
                f.write(full_to_save)
            messagebox.showinfo("Desat", "El guió complet s'ha desat correctament.")

    def _show_ssml_guide(self):
        doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "GUIA_SSML_CATALA.md")
        if os.path.exists(doc_path):
            with open(doc_path, "r", encoding="utf-8") as f:
                doc_text = f.read()
            self._open_text_viewer("Guia d'opcions SSML en català", doc_text)

    def _show_llm_guide(self):
        doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "GUIA_PROMPT_LLM.md")
        if os.path.exists(doc_path):
            with open(doc_path, "r", encoding="utf-8") as f:
                doc_text = f.read()
            self._open_text_viewer("Indicació per a models (Pòdcasts amb Matxa)", doc_text)

    def _show_components_manager(self):
        ComponentsManagerModal(self, on_update_callback=self._on_models_updated)

    def _show_version_check_modal(self):
        from ui.version_check_modal import VersionCheckModal
        VersionCheckModal(self)

    def _on_models_updated(self):
        """Callback executat en descarregar o eliminar models."""
        pass

    def _toggle_escola_mode(self):
        """Activa o desactiva el Mode escola (100% offline sense motor al núvol)."""
        self._escola_mode = not self._escola_mode

        if self._escola_mode:
            # Activat: marca el botó, mostra insígnia, elimina motor al núvol
            self.btn_escola.configure(
                fg_color=MatchaTheme.PRIMARY,
                text_color="#FFFFFF",
                text="🏫 Mode escola ✔"
            )
            self.badge.pack_forget()
            self.escola_badge.pack(side="left", padx=(8, 0))

            # Elimina l'opció Online del desplegable si hi és
            current_values = list(self.engine_combo.cget("values"))
            offline_values = [v for v in current_values if "Online" not in v]
            self.engine_combo.configure(values=offline_values)
            # Si l'usuari estava al motor Online, torna al Matxa-TTS
            if "Online" in self.engine_combo.get():
                self.engine_combo.set("🍵 Matxa-TTS v2 (100% Offline — 16 veus BSC-LT)")
                self._on_engine_change("🍵 Matxa-TTS v2 (100% Offline — 16 veus BSC-LT)")
        else:
            # Desactivat: restaura el botó, oculta insígnia, torna el motor al núvol
            self.btn_escola.configure(
                fg_color="#FFFFFF",
                text_color="#223E2A",
                text="🏫 Mode escola"
            )
            self.escola_badge.pack_forget()
            self.badge.pack(side="left")

            # Restaura l'opció Online al desplegable
            all_engines = [
                "🍵 Matxa-TTS v2 (100% Offline — 16 veus BSC-LT)",
                "🎙️ UPC FestCat (100% Offline — Veus neuronals Ona i Pau)",
                "☁️ Veus neuronals ca-ES (Online — 9 veus expressives)"
            ]
            self.engine_combo.configure(values=all_engines)

    def _bind_keyboard_shortcuts(self):
        """Vincula les dreceres de teclat globals d'accessibilitat."""
        # Ctrl+G o Ctrl+Intro: Generar pòdcast
        self.bind_all("<Control-g>", lambda e: self._start_generation())
        self.bind_all("<Control-Return>", lambda e: self._start_generation())
        # Ctrl+S: Desar guió
        self.bind_all("<Control-s>", lambda e: self._save_script_file())
        # Ctrl+O: Obrir guió
        self.bind_all("<Control-o>", lambda e: self._open_script_file())
        # F1: Obrir guia SSML
        self.bind_all("<F1>", lambda e: self._show_ssml_guide())
        # Escape durant la generació: cancel·lar
        self.bind_all("<Escape>", lambda e: self._cancel_generation() if self.is_generating else None)

    def _open_text_viewer(self, title, text):
        viewer = ctk.CTkToplevel(self)
        viewer.title(title)
        viewer.geometry("720x560")
        viewer.configure(fg_color=MatchaTheme.BG_MAIN)
        viewer.transient(self)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, "assets", "icon.ico")
        if os.path.exists(ico_path):
            try:
                viewer.iconbitmap(ico_path)
                viewer.after(200, lambda: viewer.iconbitmap(ico_path))
            except Exception:
                pass

        txt = ctk.CTkTextbox(
            viewer,
            fg_color=MatchaTheme.ENTRY_BG,
            text_color=MatchaTheme.TEXT_MAIN,
            font=MatchaTheme.FONT_MONO,
            wrap="word",
            corner_radius=10
        )
        txt.pack(fill="both", expand=True, padx=20, pady=20)
        txt.insert("1.0", text)
        txt.configure(state="disabled")

    def _select_bg_audio(self):
        """Obre el selector de fitxers per triar una pista MP3/WAV/OGG/FLAC de fons."""
        path = filedialog.askopenfilename(
            title="Seleccionar música o ambient de fons",
            filetypes=[
                ("Fitxers d'àudio (*.mp3, *.wav, *.ogg, *.flac, *.m4a)", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                ("Fitxers MP3 (*.mp3)", "*.mp3"),
                ("Fitxers WAV (*.wav)", "*.wav"),
                ("Tots els fitxers", "*.*")
            ]
        )
        if not path:
            return

        self._stop_bg_preview()
        self.bg_music_path = path
        filename = os.path.basename(path)
        display_name = filename if len(filename) <= 28 else filename[:25] + "..."

        self.lbl_bg_file.configure(
            text=f"🎵 {display_name}",
            text_color=MatchaTheme.TEXT_MAIN
        )
        self.btn_clear_bg.configure(state="normal")
        self.btn_bg_preview.configure(state="normal")
        self._set_status(f"Pista de fons seleccionada: {filename}")

        # Pre-carrega en segon pla per tenir la mostra d'escolta instantània
        def _preload():
            try:
                audio = self.audio_processor.load_audio_file(path, target_sr=22050)
                self.bg_music_audio_data = audio
            except Exception as e:
                print(f"Avís pre-carregant pista de fons: {e}")
                self.bg_music_audio_data = None

        threading.Thread(target=_preload, daemon=True).start()

    def _clear_bg_audio(self):
        """Elimina la pista de fons actual."""
        self._stop_bg_preview()
        self.bg_music_path = None
        self.bg_music_audio_data = None
        self.lbl_bg_file.configure(
            text="Sense pista de fons",
            text_color=MatchaTheme.TEXT_MUTED
        )
        self.btn_clear_bg.configure(state="disabled")
        self.btn_bg_preview.configure(state="disabled")
        self._set_status("Pista de fons desactivada.")

    def _on_bg_loop_toggle(self):
        """Activa o desactiva la repetició en bucle de la música de fons."""
        self.bg_music_loop = bool(self.cb_bg_loop.get())
        if getattr(self, "_is_bg_previewing", False):
            self._play_bg_preview_sound()

    def _on_bg_ducking_toggle(self):
        """Activa o desactiva l'auto-ducking intel·ligent de la música de fons."""
        self.bg_music_ducking = bool(self.cb_bg_ducking.get())

    def _on_bg_volume_change(self, val):
        """Ajusta el volum de la pista de fons i actualitza l'etiqueta."""
        v = float(val)
        self.bg_music_volume = v
        pct = int(round(v * 100))
        self.lbl_bg_volume.configure(text=f"Volum: {pct}%")
        # Ajust de volum en directe sense reiniciar la reproducció si ja està sonant
        if getattr(self, "_is_bg_previewing", False):
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.set_volume(self.bg_music_volume)
            except Exception:
                pass

    def _toggle_bg_preview(self):
        """Reprodueix o atura una mostra de la música de fons al volum seleccionat."""
        if getattr(self, "_is_bg_previewing", False):
            self._stop_bg_preview()
            self._set_status("Prova de música de fons aturada.")
            return

        if not self.bg_music_path or not os.path.exists(self.bg_music_path):
            messagebox.showwarning("Atenció", "Primer has de seleccionar un fitxer d'àudio de fons.")
            return

        self._play_bg_preview_sound()

    def _play_bg_preview_sound(self):
        """Genera i reprodueix la mostra d'àudio de fons al volum actual de forma 100% nativa."""
        if not self.bg_music_path or not os.path.exists(self.bg_music_path):
            return

        try:
            if self.bg_music_audio_data is not None:
                audio = self.bg_music_audio_data
            else:
                self._set_status("Carregant pista d'àudio...")
                audio = self.audio_processor.load_audio_file(self.bg_music_path, target_sr=22050)
                self.bg_music_audio_data = audio

            if audio is None or audio.size == 0:
                self._stop_bg_preview()
                self._set_status("No s'ha pogut obtenir àudio del fitxer seleccionat.")
                return

            vol = max(0.0, min(1.0, float(self.bg_music_volume)))
            self._is_bg_previewing = True
            played = False

            # Prioritzar Pygame mixer directament amb el fitxer d'àudio complet per reproducció íntegra i volum dinàmic
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
                pygame.mixer.music.load(self.bg_music_path)
                pygame.mixer.music.set_volume(vol)
                pygame.mixer.music.play(-1 if self.bg_music_loop else 0)
                played = True
            except Exception as pe:
                print(f"Fallback reproducció Pygame: {pe}")

            if not played:
                tmp_dir = os.path.join(tempfile.gettempdir(), "podcasts_matxa_preview")
                os.makedirs(tmp_dir, exist_ok=True)
                self._bg_preview_tmp_wav = os.path.join(tmp_dir, f"bg_preview_{os.getpid()}.wav")
                sf.write(self._bg_preview_tmp_wav, audio.T, 22050, subtype="PCM_16")

                try:
                    if not pygame.mixer.get_init():
                        pygame.mixer.init(frequency=22050, size=-16, channels=audio.shape[0], buffer=1024)
                    pygame.mixer.music.load(self._bg_preview_tmp_wav)
                    pygame.mixer.music.set_volume(vol)
                    pygame.mixer.music.play(-1 if self.bg_music_loop else 0)
                    played = True
                except Exception:
                    pass

                if not played and sys.platform == "win32":
                    try:
                        scaled = np.clip(audio * vol, -1.0, 1.0)
                        sf.write(self._bg_preview_tmp_wav, scaled.T, 22050, subtype="PCM_16")
                        import winsound
                        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
                        if self.bg_music_loop:
                            flags |= winsound.SND_LOOP
                        winsound.PlaySound(self._bg_preview_tmp_wav, flags)
                        played = True
                    except Exception as we:
                        print(f"Avís winsound: {we}")

            if played:
                self.btn_bg_preview.configure(
                    text="■ Atura",
                    fg_color="#2E5E41",
                    text_color="#FFFFFF"
                )
                dur_secs = audio.shape[1] / 22050.0
                loop_text = "en bucle continu" if self.bg_music_loop else f"{dur_secs:.1f}s"
                self._set_status(f"Reproduint prova de fons ({loop_text}, volum {int(round(vol*100))}%)...")

                if not self.bg_music_loop:
                    dur_ms = int(dur_secs * 1000) + 150
                    if self._bg_preview_timer_id:
                        try:
                            self.after_cancel(self._bg_preview_timer_id)
                        except Exception:
                            pass
                    self._bg_preview_timer_id = self.after(dur_ms, self._on_bg_preview_finished)
                else:
                    if self._bg_preview_timer_id:
                        try:
                            self.after_cancel(self._bg_preview_timer_id)
                        except Exception:
                            pass
                        self._bg_preview_timer_id = None
            else:
                self._stop_bg_preview()
                self._set_status("No s'ha pogut reproduir el so al dispositiu d'àudio.")

        except Exception as e:
            print(f"Error a _play_bg_preview_sound: {e}")
            self._stop_bg_preview()
            self._set_status(f"Error en provar la pista: {e}")

    def _on_bg_preview_finished(self):
        self._is_bg_previewing = False
        self._bg_preview_timer_id = None
        try:
            self.btn_bg_preview.configure(
                text="▶ Prova",
                fg_color=MatchaTheme.BUTTON_SUBTLE_BG,
                text_color=MatchaTheme.TEXT_MAIN
            )
            self._set_status("A punt per generar. Sense límit de temps.")
        except Exception:
            pass

    def _stop_bg_preview(self):
        self._is_bg_previewing = False
        if self._bg_preview_timer_id:
            try:
                self.after_cancel(self._bg_preview_timer_id)
            except Exception:
                pass
            self._bg_preview_timer_id = None

        # 1. Aturar Pygame mixer music i Sound
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                pygame.mixer.stop()
        except Exception as pe:
            print(f"Avís aturant pygame: {pe}")

        # 2. Aturar winsound si s'estava reproduint per allà
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception as we:
                print(f"Avís aturant winsound: {we}")

        try:
            self.btn_bg_preview.configure(
                text="▶ Prova",
                fg_color=MatchaTheme.BUTTON_SUBTLE_BG,
                text_color=MatchaTheme.TEXT_MAIN
            )
        except Exception:
            pass

    def _start_generation(self):
        if self.is_generating:
            return

        self._stop_bg_preview()

        current_content = self.script_textbox.get("1.0", "end-1c")
        if self.editor_mode == "clean":
            full_to_process = self._compose_full_script(current_content)
        else:
            full_to_process = current_content

        self.current_script = self.script_parser.parse(full_to_process)

        for spk_name, overrides in self.ui_speaker_overrides.items():
            if spk_name in self.current_script.speakers:
                if "voice_id" in overrides:
                    self.current_script.speakers[spk_name].voice_id = overrides["voice_id"]
                if "pan" in overrides:
                    self.current_script.speakers[spk_name].pan = overrides["pan"]

        for seg in self.current_script.segments:
            if seg.segment_type == "dialogue" and seg.speaker in self.current_script.speakers:
                spk_cfg = self.current_script.speakers[seg.speaker]
                seg.voice_id = spk_cfg.voice_id
                seg.pan = spk_cfg.pan

        if not self.current_script.segments:
            messagebox.showwarning("Atenció", "El guió està buit o no conté línies de diàleg.")
            return

        self.is_generating = True
        self.cancel_requested = False
        self.generate_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress_bar.set(0.0)

        threading.Thread(target=self._generation_worker, daemon=True).start()

    def _cancel_generation(self):
        if self.is_generating:
            self.cancel_requested = True
            self.status_lbl.configure(text="Cancel·lant generació...")

    def _generation_worker(self):
        def on_progress(current, total_steps, text):
            pct = current / max(1, total_steps)
            self.safe_after(lambda: self._update_progress_ui(pct, f"[{current}/{total_steps}] {text}"))

        def is_cancelled():
            return self.cancel_requested

        try:
            if not self.tts_engine.is_loaded():
                self.safe_after(lambda: self._update_progress_ui(0.01, f"Inicialitzant model neuronal {self.tts_engine.name} a la memòria RAM..."))
                self.tts_engine.ensure_loaded()

            audio_segments = self.tts_engine.synthesize_podcast_stream(
                self.current_script.segments,
                on_progress=on_progress,
                is_cancelled=is_cancelled
            )

            if self.cancel_requested:
                self.safe_after(lambda: self._on_generation_finished(None, "Generació cancel·lada per l'usuari."))
                return

            self.safe_after(lambda: self._update_progress_ui(0.95, "Masteritzant àudio (Estèreo i EBU R128)..."))
            mastered_stereo = self.audio_processor.assemble_podcast(audio_segments)

            # Mescla de pista o música de fons si s'ha seleccionat
            if self.bg_music_path and os.path.exists(self.bg_music_path) and self.bg_music_volume > 0.0:
                self.safe_after(lambda: self._update_progress_ui(0.98, "Mesclant música de fons..."))
                mastered_stereo = self.audio_processor.mix_background_track(
                    voice_audio=mastered_stereo,
                    bg_audio=self.bg_music_path,
                    volume=self.bg_music_volume,
                    loop=self.bg_music_loop,
                    ducking=self.bg_music_ducking
                )

            self.safe_after(lambda: self._on_generation_finished(mastered_stereo, "Pòdcast generat amb èxit!"))

        except Exception as e:
            self.safe_after(lambda: self._on_generation_finished(None, f"Error durant la generació: {e}"))

    def _update_progress_ui(self, pct, status_text):
        self.progress_bar.set(pct)
        self.status_lbl.configure(text=status_text)

    def _on_generation_finished(self, stereo_audio, status_message):
        self.is_generating = False
        self.generate_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_lbl.configure(text=status_message)

        if stereo_audio is not None and stereo_audio.size > 0:
            self.progress_bar.set(1.0)
            self.player_widget.load_audio(stereo_audio, title=self.current_script.title)
            messagebox.showinfo("Pòdcast completat", "El pòdcast s'ha generat correctament!\nPots escoltar-lo o desar-lo directament com a MP3.")
