#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
=============================================================================
PORTUGALETEKO XAKE TALDEA - SISTEMA DE CONTROL DE ELO DE RÁPIDAS (GUI)
=============================================================================
Aplicación de escritorio moderna construida con CustomTkinter y SQLite.
Permite gestionar jugadores, procesar torneos con cálculo automático FIDE (K=10),
consultar fichas estadísticas de socios, historial y exportar clasificaciones.
=============================================================================
"""

import os
import shutil
import sqlite3
import csv
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Dict, Any

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
import customtkinter as ctk
from PIL import Image, ImageTk

from elo_club_improved import ELOClub

# Configuración inicial de CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ELOClubGUI(ctk.CTk):
    """Ventana principal de la aplicación gráfica."""
    
    def __init__(self, db_name="elo_club.db"):
        super().__init__()
        
        self.db_name = db_name
        self.backend = ELOClub(db_name=db_name)
        
        self.title("Portugaleteko Xake Taldea - Control ELO Rápidas")
        self.geometry("1220x780")
        self.minsize(1050, 680)

        # Cargar escudo oficial del club
        self.escudo_sidebar = None
        self.escudo_small = None
        self._tk_icon = None
        escudo_file = "EscudoPAPColor_low.jpg"
        if os.path.exists(escudo_file):
            try:
                pil_escudo = Image.open(escudo_file)
                # Icono de la ventana
                self._tk_icon = ImageTk.PhotoImage(pil_escudo.resize((32, 32)))
                self.iconphoto(False, self._tk_icon)
                # Imagen para el sidebar (proporción original 354x409 -> 74x85)
                self.escudo_sidebar = ctk.CTkImage(light_image=pil_escudo, dark_image=pil_escudo, size=(74, 85))
                # Imagen pequeña para cabeceras y tarjetas (40x46)
                self.escudo_small = ctk.CTkImage(light_image=pil_escudo, dark_image=pil_escudo, size=(40, 46))
            except Exception as e:
                print(f"Aviso: no se pudo cargar la imagen del escudo: {e}")
        
        # Estado interno de la sesión
        self.sort_column = "elo"
        self.sort_desc = True
        self.torneo_participantes = []  # Jugadores añadidos al torneo en curso
        
        # Configuración del grid principal (Sidebar a la izquierda, Contenido a la derecha)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._setup_styles()
        self._create_sidebar()
        self._create_views()
        
        # Seleccionar la vista inicial
        self.select_view("ranking")

    def get_connection(self):
        return self.backend.get_connection()

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        """Elimina acentos, diacríticos y pasa a minúsculas para comparaciones insensibles."""
        if not texto: return ""
        return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

    def _setup_styles(self):
        """Configuración de estilos para los widgets estándar ttk (como Treeview)."""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Estilo oscuro para Treeview
        style.configure(
            "Treeview",
            background="#242424",
            foreground="#FFFFFF",
            fieldbackground="#242424",
            rowheight=30,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure(
            "Treeview.Heading",
            background="#1f538d",
            foreground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=6
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#2980b9")]
        )
        style.map(
            "Treeview",
            background=[("selected", "#1f538d")],
            foreground=[("selected", "#FFFFFF")]
        )

    # -------------------------------------------------------------------------
    # SIDEBAR / NAVEGACIÓN
    # -------------------------------------------------------------------------
    def _create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        curr_row = 0
        # Escudo oficial del Club
        if self.escudo_sidebar:
            self.escudo_label = ctk.CTkLabel(self.sidebar, image=self.escudo_sidebar, text="")
            self.escudo_label.grid(row=curr_row, column=0, padx=20, pady=(18, 6))
            curr_row += 1

        # Encabezado del Club
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="PORTUGALETEKO\nXAKE TALDEA", 
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold")
        )
        self.logo_label.grid(row=curr_row, column=0, padx=20, pady=(0 if self.escudo_sidebar else 24, 4))
        curr_row += 1

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar, 
            text="Control ELO Rápidas", 
            font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
            text_color="#95a5a6"
        )
        self.subtitle_label.grid(row=curr_row, column=0, padx=20, pady=(0, 16))
        curr_row += 1

        # Botones de navegación
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        items = [
            ("ranking", "📊  Ranking y Socios"),
            ("torneo", "♟️  Procesar Torneo"),
            ("ficha", "👤  Ficha del Jugador"),
            ("historial", "📜  Historial Torneos"),
            ("mantenimiento", "⚙️  Mantenimiento")
        ]

        for key, label in items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                height=38,
                corner_radius=8,
                command=lambda k=key: self.select_view(k)
            )
            btn.grid(row=curr_row, column=0, padx=16, pady=5, sticky="ew")
            self.nav_buttons[key] = btn
            curr_row += 1

        # Espaciador flexible
        self.sidebar.grid_rowconfigure(curr_row, weight=1)
        curr_row += 1

        # Selector de Tema / Estado en la parte inferior
        self.theme_label = ctk.CTkLabel(self.sidebar, text="Tema:", font=ctk.CTkFont(size=11))
        self.theme_label.grid(row=curr_row, column=0, padx=20, pady=(10, 0), sticky="w")
        curr_row += 1
        
        self.theme_option = ctk.CTkOptionMenu(
            self.sidebar, 
            values=["Dark", "Light", "System"],
            command=self._change_appearance_mode,
            height=28
        )
        self.theme_option.grid(row=curr_row, column=0, padx=16, pady=(4, 16), sticky="ew")
        curr_row += 1

        # Versión / Estado
        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text=f"BD: {os.path.basename(self.db_name)}",
            font=ctk.CTkFont(size=11),
            text_color="#7f8c8d"
        )
        self.status_label.grid(row=curr_row, column=0, padx=16, pady=(0, 16))

    def _change_appearance_mode(self, mode: str):
        ctk.set_appearance_mode(mode)

    def select_view(self, name: str):
        """Cambia la vista activa y resalta el botón correspondiente."""
        for key, btn in self.nav_buttons.items():
            if key == name:
                btn.configure(fg_color=["#3a7ebf", "#1f538d"], text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=["#333333", "#DCE4EE"])

        for key, frame in self.views.items():
            if key == name:
                frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
                # Llamar al callback de refresco de la vista
                if hasattr(self, f"_on_show_{name}"):
                    getattr(self, f"_on_show_{name}")()
            else:
                frame.grid_forget()

    # -------------------------------------------------------------------------
    # CONTENEDOR DE VISTAS
    # -------------------------------------------------------------------------
    def _create_views(self):
        self.views: Dict[str, ctk.CTkFrame] = {}
        
        # 1. Ranking y Jugadores
        self.views["ranking"] = self._create_ranking_view()
        # 2. Procesar Torneo
        self.views["torneo"] = self._create_torneo_view()
        # 3. Ficha del Jugador
        self.views["ficha"] = self._create_ficha_view()
        # 4. Historial de Torneos y Listas
        self.views["historial"] = self._create_historial_view()
        # 5. Mantenimiento y Exportación
        self.views["mantenimiento"] = self._create_mantenimiento_view()

    # =========================================================================
    # VISTA 1: RANKING Y JUGADORES
    # =========================================================================
    def _create_ranking_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self, corner_radius=12)
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        # 1. Banner superior de métricas
        metrics_frame = ctk.CTkFrame(view, fg_color="transparent")
        metrics_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        metrics_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Tarjeta 1: Total Jugadores
        self.card_total = ctk.CTkFrame(metrics_frame, corner_radius=10)
        self.card_total.grid(row=0, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkLabel(self.card_total, text="SOCIOS REGISTRADOS", font=ctk.CTkFont(size=11, weight="bold"), text_color="#3498db").pack(pady=(8, 2))
        self.lbl_total_jugadores = ctk.CTkLabel(self.card_total, text="0", font=ctk.CTkFont(size=22, weight="bold"))
        self.lbl_total_jugadores.pack(pady=(0, 8))

        # Tarjeta 2: ELO Medio
        self.card_media = ctk.CTkFrame(metrics_frame, corner_radius=10)
        self.card_media.grid(row=0, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkLabel(self.card_media, text="ELO MEDIO DEL CLUB", font=ctk.CTkFont(size=11, weight="bold"), text_color="#9b59b6").pack(pady=(8, 2))
        self.lbl_media_elo = ctk.CTkLabel(self.card_media, text="0.0", font=ctk.CTkFont(size=22, weight="bold"))
        self.lbl_media_elo.pack(pady=(0, 8))

        # Tarjeta 3: Última lista oficial
        self.card_lista = ctk.CTkFrame(metrics_frame, corner_radius=10)
        self.card_lista.grid(row=0, column=2, padx=6, pady=4, sticky="ew")
        ctk.CTkLabel(self.card_lista, text="ÚLTIMA LISTA OFICIAL", font=ctk.CTkFont(size=11, weight="bold"), text_color="#2ecc71").pack(pady=(8, 2))
        self.lbl_fecha_lista = ctk.CTkLabel(self.card_lista, text="Pendiente", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_fecha_lista.pack(pady=(4, 8))

        # 2. Barra de búsqueda y acciones
        toolbar = ctk.CTkFrame(view, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        toolbar.grid_columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_ranking())
        
        self.entry_search = ctk.CTkEntry(
            toolbar,
            placeholder_text="🔍  Buscar por nombre o apellidos...",
            textvariable=self.search_var,
            height=34,
            corner_radius=8
        )
        self.entry_search.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        btn_new = ctk.CTkButton(toolbar, text="➕ Nuevo Jugador", height=34, width=130, command=self._dialog_crear_jugador)
        btn_new.grid(row=0, column=1, padx=4)

        btn_edit = ctk.CTkButton(toolbar, text="✏️ Modificar", height=34, width=110, fg_color="#e67e22", hover_color="#d35400", command=self._dialog_modificar_jugador)
        btn_edit.grid(row=0, column=2, padx=4)

        btn_del = ctk.CTkButton(toolbar, text="🗑️ Eliminar", height=34, width=100, fg_color="#c0392b", hover_color="#962d22", command=self._accion_eliminar_jugador)
        btn_del.grid(row=0, column=3, padx=4)

        btn_profile = ctk.CTkButton(toolbar, text="👤 Ver Ficha", height=34, width=110, fg_color="#27ae60", hover_color="#1e8449", command=self._ver_ficha_seleccionado)
        btn_profile.grid(row=0, column=4, padx=4)

        btn_wa = ctk.CTkButton(toolbar, text="📱 WhatsApp", height=34, width=115, fg_color="#25d366", hover_color="#1e8449", text_color="#ffffff", command=self._copiar_ranking_whatsapp)
        btn_wa.grid(row=0, column=5, padx=4)

        btn_web = ctk.CTkButton(toolbar, text="🌐 Web", height=34, width=95, fg_color="#1b3a57", hover_color="#2c5282", text_color="#ffffff", command=self._export_web_interactiva)
        btn_web.grid(row=0, column=6, padx=(4, 0))

        # 3. Tabla de Jugadores
        table_container = ctk.CTkFrame(view)
        table_container.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        columns = ("pos", "id", "jugador", "elo", "titulo", "variacion", "torneos", "ultimo_torneo", "inactividad")
        self.tree_ranking = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse")

        self.tree_ranking.heading("pos", text="RK", command=lambda: self._sort_ranking("pos"))
        self.tree_ranking.heading("id", text="ID", command=lambda: self._sort_ranking("id"))
        self.tree_ranking.heading("jugador", text="JUGADOR", command=lambda: self._sort_ranking("jugador"))
        self.tree_ranking.heading("elo", text="ELO", command=lambda: self._sort_ranking("elo"))
        self.tree_ranking.heading("titulo", text="TÍTULO", command=lambda: self._sort_ranking("titulo"))
        self.tree_ranking.heading("variacion", text="VAR.", command=lambda: self._sort_ranking("variacion"))
        self.tree_ranking.heading("torneos", text="TORN.", command=lambda: self._sort_ranking("torneos"))
        self.tree_ranking.heading("ultimo_torneo", text="ÚLT. TORNEO", command=lambda: self._sort_ranking("ultimo_torneo"))
        self.tree_ranking.heading("inactividad", text="DÍAS INACT.", command=lambda: self._sort_ranking("inactividad"))

        self.tree_ranking.column("pos", width=45, anchor="center")
        self.tree_ranking.column("id", width=45, anchor="center")
        self.tree_ranking.column("jugador", width=250, anchor="w")
        self.tree_ranking.column("elo", width=75, anchor="center")
        self.tree_ranking.column("titulo", width=75, anchor="center")
        self.tree_ranking.column("variacion", width=70, anchor="center")
        self.tree_ranking.column("torneos", width=65, anchor="center")
        self.tree_ranking.column("ultimo_torneo", width=110, anchor="center")
        self.tree_ranking.column("inactividad", width=100, anchor="center")

        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_ranking.yview)
        self.tree_ranking.configure(yscrollcommand=scrollbar.set)

        self.tree_ranking.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Doble clic para abrir ficha
        self.tree_ranking.bind("<Double-1>", lambda event: self._ver_ficha_seleccionado())

        # Configurar tags de color para las filas
        self.tree_ranking.tag_configure("var_pos", foreground="#2ecc71")
        self.tree_ranking.tag_configure("var_neg", foreground="#e74c3c")
        self.tree_ranking.tag_configure("alerta_inactivo", foreground="#f39c12")
        self.tree_ranking.tag_configure("inactivo_grave", foreground="#e74c3c")

        return view

    def _on_show_ranking(self):
        self._refresh_ranking_data()

    def _refresh_ranking_data(self):
        """Lee los jugadores de la base de datos y actualiza métricas y tabla."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Métricas
            last_list = cursor.execute("SELECT fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC LIMIT 1").fetchone()
            if last_list:
                fecha_loc = self.backend.utc_to_local_str(last_list[0])[:10]
                self.lbl_fecha_lista.configure(text=fecha_loc)
            else:
                self.lbl_fecha_lista.configure(text="Sin listas previas")

            media_res = cursor.execute("SELECT AVG(elo), COUNT(*) FROM jugadores").fetchone()
            media_elo = media_res[0] if media_res and media_res[0] else 0.0
            total_jug = media_res[1] if media_res else 0
            
            self.lbl_media_elo.configure(text=f"{media_elo:.1f}")
            self.lbl_total_jugadores.configure(text=str(total_jug))

            # Datos de jugadores
            jugadores = cursor.execute('''
                SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, num_torneos, fecha_ultimo_torneo 
                FROM jugadores ORDER BY elo DESC, num_torneos DESC
            ''').fetchall()

        self.raw_ranking_data = []
        for i, (jid, nom, ape, elo, tit, var, torn, fec_ult) in enumerate(jugadores, 1):
            dias = self.backend.calcular_dias_desde_ultimo_torneo(fec_ult)
            self.raw_ranking_data.append({
                "pos": i,
                "id": jid,
                "nombre_completo": f"{nom} {ape}",
                "nombre": nom,
                "apellidos": ape,
                "elo": elo,
                "titulo": tit or "-",
                "variacion": var,
                "torneos": torn,
                "ultimo_torneo": fec_ult or "Nunca",
                "inactividad": dias
            })

        self._filter_ranking()

    def _filter_ranking(self):
        query = self.search_var.get().strip().lower()
        self.tree_ranking.delete(*self.tree_ranking.get_children())
        
        filtered = [
            j for j in self.raw_ranking_data 
            if query in j["nombre_completo"].lower() or query in str(j["id"])
        ]

        # Ordenación
        reverse = self.sort_desc
        if self.sort_column in ("pos", "id", "elo", "variacion", "torneos", "inactividad"):
            filtered.sort(key=lambda x: x[self.sort_column], reverse=reverse)
        else:
            filtered.sort(key=lambda x: str(x[self.sort_column]).lower(), reverse=reverse)

        for j in filtered:
            var_str = f"{j['variacion']:+d}" if j['variacion'] != 0 else "0"
            tag = "normal"
            if j['variacion'] > 0:
                tag = "var_pos"
            elif j['variacion'] < 0:
                tag = "var_neg"
            elif j['inactividad'] > 365:
                tag = "inactivo_grave"
            elif j['inactividad'] > 180:
                tag = "alerta_inactivo"

            self.tree_ranking.insert("", "end", values=(
                j["pos"], j["id"], j["nombre_completo"], j["elo"], j["titulo"],
                var_str, j["torneos"], j["ultimo_torneo"], j["inactividad"]
            ), tags=(tag,))

    def _sort_ranking(self, col: str):
        if self.sort_column == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = col
            self.sort_desc = True
        self._filter_ranking()

    def _get_selected_player_id(self) -> Optional[int]:
        selected = self.tree_ranking.selection()
        if not selected:
            messagebox.showwarning("Atención", "Por favor, selecciona un jugador de la tabla primero.")
            return None
        values = self.tree_ranking.item(selected[0], "values")
        return int(values[1])

    # Diálogos de CRUD de jugador
    def _dialog_crear_jugador(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Crear Nuevo Jugador")
        dialog.geometry("400x340")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nuevo Jugador", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(16, 12))

        entry_nombre = ctk.CTkEntry(dialog, placeholder_text="Nombre")
        entry_nombre.pack(padx=20, pady=6, fill="x")

        entry_apellidos = ctk.CTkEntry(dialog, placeholder_text="Apellidos")
        entry_apellidos.pack(padx=20, pady=6, fill="x")

        entry_elo = ctk.CTkEntry(dialog, placeholder_text="ELO Inicial (por defecto 2000)")
        entry_elo.pack(padx=20, pady=6, fill="x")

        entry_titulo = ctk.CTkEntry(dialog, placeholder_text="Título (opcional, ej. FM, PFM)")
        entry_titulo.pack(padx=20, pady=6, fill="x")

        def guardar():
            nombre = entry_nombre.get().strip()
            apellidos = entry_apellidos.get().strip()
            elo_val = entry_elo.get().strip()
            titulo = entry_titulo.get().strip()

            if not nombre or not apellidos:
                messagebox.showerror("Error", "El nombre y los apellidos son obligatorios.", parent=dialog)
                return

            elo = 2000
            if elo_val:
                try:
                    elo = int(elo_val)
                except ValueError:
                    messagebox.showerror("Error", "El ELO inicial debe ser un número entero.", parent=dialog)
                    return

            with self.get_connection() as conn:
                conn.cursor().execute(
                    "INSERT INTO jugadores (nombre, apellidos, elo, titulo) VALUES (?, ?, ?, ?)",
                    (nombre, apellidos, elo, titulo)
                )
            messagebox.showinfo("Éxito", f"Jugador {nombre} {apellidos} creado correctamente.", parent=dialog)
            dialog.destroy()
            self._refresh_ranking_data()

        ctk.CTkButton(dialog, text="Guardar Jugador", command=guardar, height=36).pack(padx=20, pady=16, fill="x")

    def _dialog_modificar_jugador(self):
        jid = self._get_selected_player_id()
        if not jid: return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugador = cursor.execute("SELECT nombre, apellidos, elo, titulo FROM jugadores WHERE id = ?", (jid,)).fetchone()
        
        if not jugador:
            messagebox.showerror("Error", "Jugador no encontrado.")
            return

        nom_act, ape_act, elo_act, tit_act = jugador

        dialog = ctk.CTkToplevel(self)
        dialog.title("Modificar Jugador")
        dialog.geometry("400x340")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=f"Modificar: {nom_act} {ape_act}", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(16, 12))

        entry_nom = ctk.CTkEntry(dialog)
        entry_nom.insert(0, nom_act)
        entry_nom.pack(padx=20, pady=6, fill="x")

        entry_ape = ctk.CTkEntry(dialog)
        entry_ape.insert(0, ape_act)
        entry_ape.pack(padx=20, pady=6, fill="x")

        entry_elo = ctk.CTkEntry(dialog)
        entry_elo.insert(0, str(elo_act))
        entry_elo.pack(padx=20, pady=6, fill="x")

        entry_tit = ctk.CTkEntry(dialog)
        entry_tit.insert(0, tit_act or "")
        entry_tit.pack(padx=20, pady=6, fill="x")

        def guardar():
            nuevo_nom = entry_nom.get().strip()
            nuevo_ape = entry_ape.get().strip()
            nuevo_elo_str = entry_elo.get().strip()
            nuevo_tit = entry_tit.get().strip()

            if not nuevo_nom or not nuevo_ape:
                messagebox.showerror("Error", "El nombre y los apellidos no pueden estar vacíos.", parent=dialog)
                return

            try:
                nuevo_elo = int(nuevo_elo_str)
            except ValueError:
                messagebox.showerror("Error", "El ELO debe ser un número entero válido.", parent=dialog)
                return

            with self.get_connection() as conn:
                conn.cursor().execute(
                    "UPDATE jugadores SET nombre = ?, apellidos = ?, elo = ?, titulo = ? WHERE id = ?",
                    (nuevo_nom, nuevo_ape, nuevo_elo, nuevo_tit, jid)
                )
            messagebox.showinfo("Éxito", "Jugador actualizado correctamente.", parent=dialog)
            dialog.destroy()
            self._refresh_ranking_data()

        ctk.CTkButton(dialog, text="Guardar Cambios", command=guardar, height=36).pack(padx=20, pady=16, fill="x")

    def _accion_eliminar_jugador(self):
        jid = self._get_selected_player_id()
        if not jid: return

        with self.get_connection() as conn:
            jugador = conn.cursor().execute("SELECT nombre, apellidos FROM jugadores WHERE id = ?", (jid,)).fetchone()
        
        if not jugador: return
        nombre_completo = f"{jugador[0]} {jugador[1]}"

        if messagebox.askyesno("Confirmar Eliminación", f"¿Estás seguro de eliminar a '{nombre_completo}'?\n\nEsta acción es irreversible y eliminará todas sus participaciones."):
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM participaciones WHERE jugador_id = ?", (jid,))
                cursor.execute("DELETE FROM jugadores WHERE id = ?", (jid,))
            messagebox.showinfo("Eliminado", f"Jugador '{nombre_completo}' eliminado.")
            self._refresh_ranking_data()

    def _ver_ficha_seleccionado(self):
        jid = self._get_selected_player_id()
        if not jid: return
        self.select_view("ficha")
        self._cargar_ficha_por_id(jid)

    # =========================================================================
    # VISTA 2: PROCESAR TORNEO
    # =========================================================================
    def _create_torneo_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self, corner_radius=12)
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        # 1. Datos del Torneo
        header_frame = ctk.CTkFrame(view, corner_radius=10)
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        header_frame.grid_columnconfigure((0, 1), weight=1)

        header_frame_top = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_frame_top.grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 4), sticky="ew")
        header_frame_top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame_top, text="DATOS DEL TORNEO", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        if self.escudo_small:
            ctk.CTkLabel(header_frame_top, image=self.escudo_small, text="").grid(row=0, column=1, sticky="e")

        self.torneo_nombre_entry = ctk.CTkEntry(header_frame, placeholder_text="Nombre del torneo (ej. Torneo Primavera 2026)", height=34)
        self.torneo_nombre_entry.grid(row=1, column=0, padx=(16, 8), pady=(0, 12), sticky="ew")

        self.torneo_fecha_entry = ctk.CTkEntry(header_frame, placeholder_text="Fecha YYYY-MM-DD", height=34)
        self.torneo_fecha_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.torneo_fecha_entry.grid(row=1, column=1, padx=(8, 16), pady=(0, 12), sticky="ew")

        # 2. Formulario para añadir participantes
        form_frame = ctk.CTkFrame(view, corner_radius=10)
        form_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        form_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(form_frame, text="AÑADIR RESULTADO DE JUGADOR", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 6), sticky="w")

        # Fila 1: Búsqueda dinámica y selector con autocompletado
        player_select_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        player_select_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=8, pady=4)
        player_select_frame.grid_columnconfigure(1, weight=1)

        self.torneo_search_var = tk.StringVar()
        self.torneo_search_var.trace_add("write", lambda *args: self._on_filter_torneo_jugadores())
        
        self.torneo_search_entry = ctk.CTkEntry(
            player_select_frame, 
            placeholder_text="🔍 Escribe nombre o apellido...", 
            textvariable=self.torneo_search_var,
            height=32,
            width=260
        )
        self.torneo_search_entry.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.torneo_search_entry.bind("<Return>", lambda e: self._on_torneo_search_enter())
        self.torneo_search_entry.bind("<Down>", lambda e: self.combo_jugadores.focus_set())

        self.combo_jugadores = ctk.CTkComboBox(
            player_select_frame, 
            height=32, 
            command=self._on_torneo_player_selected
        )
        self.combo_jugadores.grid(row=0, column=1, sticky="ew")

        # Fila 2: Rc, Partidas, Puntos y Botón Añadir
        self.torneo_rc_entry = ctk.CTkEntry(form_frame, placeholder_text="ELO Medio Rivales (Rc)", height=32)
        self.torneo_rc_entry.grid(row=2, column=0, padx=8, pady=(6, 4), sticky="ew")
        self.torneo_rc_entry.bind("<KeyRelease>", lambda e: self._update_preview_calculo())
        self.torneo_rc_entry.bind("<Return>", lambda e: self.torneo_partidas_entry.focus_set())

        self.torneo_partidas_entry = ctk.CTkEntry(form_frame, placeholder_text="Partidas (>0)", height=32)
        self.torneo_partidas_entry.grid(row=2, column=1, padx=8, pady=(6, 4), sticky="ew")
        self.torneo_partidas_entry.bind("<KeyRelease>", lambda e: self._update_preview_calculo())
        self.torneo_partidas_entry.bind("<Return>", lambda e: self.torneo_puntos_entry.focus_set())

        self.torneo_puntos_entry = ctk.CTkEntry(form_frame, placeholder_text="Puntos obtenidos", height=32)
        self.torneo_puntos_entry.grid(row=2, column=2, padx=8, pady=(6, 4), sticky="ew")
        self.torneo_puntos_entry.bind("<KeyRelease>", lambda e: self._update_preview_calculo())
        self.torneo_puntos_entry.bind("<Return>", lambda e: self._add_participante_torneo())

        btn_add = ctk.CTkButton(form_frame, text="➕ Añadir Jugador", height=32, fg_color="#27ae60", hover_color="#1e8449", command=self._add_participante_torneo)
        btn_add.grid(row=2, column=3, padx=8, pady=(6, 4), sticky="ew")

        # Fila 3: Preview de cálculo dinámico
        self.lbl_preview_calculo = ctk.CTkLabel(
            form_frame, 
            text="Escribe el nombre del socio y completa sus datos para ver la variación en vivo.",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#95a5a6"
        )
        self.lbl_preview_calculo.grid(row=3, column=0, columnspan=4, sticky="w", padx=16, pady=(4, 10))

        # 3. Tabla de participantes añadidos
        table_frame = ctk.CTkFrame(view)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        cols = ("id", "jugador", "elo_ini", "rc", "partidas", "puntos", "perf", "var", "nuevo_elo")
        self.tree_torneo = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        self.tree_torneo.heading("id", text="ID")
        self.tree_torneo.heading("jugador", text="JUGADOR")
        self.tree_torneo.heading("elo_ini", text="ELO INI")
        self.tree_torneo.heading("rc", text="RIV. MED")
        self.tree_torneo.heading("partidas", text="PART.")
        self.tree_torneo.heading("puntos", text="PUNTOS")
        self.tree_torneo.heading("perf", text="PERF.")
        self.tree_torneo.heading("var", text="VAR. ELO")
        self.tree_torneo.heading("nuevo_elo", text="NUEVO ELO")

        self.tree_torneo.column("id", width=40, anchor="center")
        self.tree_torneo.column("jugador", width=220, anchor="w")
        self.tree_torneo.column("elo_ini", width=80, anchor="center")
        self.tree_torneo.column("rc", width=80, anchor="center")
        self.tree_torneo.column("partidas", width=65, anchor="center")
        self.tree_torneo.column("puntos", width=75, anchor="center")
        self.tree_torneo.column("perf", width=75, anchor="center")
        self.tree_torneo.column("var", width=85, anchor="center")
        self.tree_torneo.column("nuevo_elo", width=85, anchor="center")

        scroll_t = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_torneo.yview)
        self.tree_torneo.configure(yscrollcommand=scroll_t.set)
        self.tree_torneo.grid(row=0, column=0, sticky="nsew")
        scroll_t.grid(row=0, column=1, sticky="ns")

        # 4. Barra inferior de confirmación
        bottom_bar = ctk.CTkFrame(view, fg_color="transparent")
        bottom_bar.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        bottom_bar.grid_columnconfigure(0, weight=1)

        self.lbl_torneo_count = ctk.CTkLabel(bottom_bar, text="Participantes: 0", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_torneo_count.grid(row=0, column=0, sticky="w")

        btn_quitar = ctk.CTkButton(bottom_bar, text="Eliminar Seleccionado", height=36, fg_color="#c0392b", hover_color="#962d22", command=self._quitar_participante_torneo)
        btn_quitar.grid(row=0, column=1, padx=8)

        btn_guardar_torneo = ctk.CTkButton(
            bottom_bar, 
            text="💾 Guardar Torneo y Actualizar ELOs", 
            height=36, 
            fg_color="#2980b9", 
            hover_color="#1f618d", 
            command=self._guardar_torneo_completo
        )
        btn_guardar_torneo.grid(row=0, column=2, padx=(8, 0))

        return view

    def _on_show_torneo(self):
        # Cargar jugadores en el combo
        with self.get_connection() as conn:
            jugadores = conn.cursor().execute("SELECT id, nombre, apellidos, elo FROM jugadores ORDER BY nombre ASC").fetchall()
        
        self.all_jugadores_torneo = {f"{j[0]} - {j[1]} {j[2]} (ELO: {j[3]})": j for j in jugadores}
        self.jugadores_map = dict(self.all_jugadores_torneo)
        self.torneo_search_var.set("")
        self._on_filter_torneo_jugadores()
        self.torneo_search_entry.focus_set()

    def _on_torneo_search_enter(self):
        sel = self.combo_jugadores.get()
        if sel and sel != "No hay coincidencias":
            self.torneo_rc_entry.focus_set()
            self.torneo_rc_entry.select_range(0, 'end')

    def _on_filter_torneo_jugadores(self):
        if not hasattr(self, "all_jugadores_torneo"): return
        raw_query = self.torneo_search_var.get().strip()
        q_norm = self._normalizar_texto(raw_query)
        
        if not q_norm:
            filtered = list(self.all_jugadores_torneo.keys())
        else:
            q_words = q_norm.split()
            filtered = []
            for k in self.all_jugadores_torneo.keys():
                k_norm = self._normalizar_texto(k)
                if all(word in k_norm for word in q_words):
                    filtered.append(k)
            
        self.jugadores_map = {k: self.all_jugadores_torneo[k] for k in filtered}
        
        if filtered:
            self.combo_jugadores.configure(values=filtered)
            self.combo_jugadores.set(filtered[0])
            self._update_preview_calculo()
        else:
            self.combo_jugadores.configure(values=["No hay coincidencias"])
            self.combo_jugadores.set("No hay coincidencias")
            self.lbl_preview_calculo.configure(
                text=f"No se encontró ningún socio que coincida con '{raw_query}'.",
                text_color="#e74c3c"
            )

    def _on_torneo_player_selected(self, choice: str):
        self._update_preview_calculo()

    def _update_preview_calculo(self):
        sel = self.combo_jugadores.get()
        if not sel or sel not in self.jugadores_map:
            self.lbl_preview_calculo.configure(
                text="Selecciona un socio para calcular su variación.",
                text_color="#95a5a6"
            )
            return

        j_data = self.jugadores_map[sel]
        elo_act = j_data[3]

        rc_str = self.torneo_rc_entry.get().strip()
        partidas_str = self.torneo_partidas_entry.get().strip()
        puntos_str = self.torneo_puntos_entry.get().strip()

        if not rc_str or not partidas_str or not puntos_str:
            self.lbl_preview_calculo.configure(
                text=f"Socio: {j_data[1]} {j_data[2]} | ELO actual: {elo_act} | Introduce Rc, partidas y puntos.",
                text_color="#95a5a6"
            )
            return

        try:
            rc = float(rc_str)
            partidas = int(partidas_str)
            puntos = float(puntos_str)

            if partidas <= 0 or not (0 <= puntos <= partidas):
                self.lbl_preview_calculo.configure(
                    text="Partidas debe ser > 0 y los puntos entre 0 y el total de partidas.",
                    text_color="#f39c12"
                )
                return

            k = self.backend.determinar_k_factor()
            pd = self.backend.calculo_Pd(elo_act, rc)
            var = self.backend.calculo_variacion_elo(pd * partidas, puntos, k)
            nuevo = round(elo_act + var)
            perf = self.backend.calcular_performance(rc, puntos, partidas)

            signo = "+" if var >= 0 else ""
            color = "#2ecc71" if var >= 0 else "#e74c3c"
            self.lbl_preview_calculo.configure(
                text=f"Socio: {j_data[1]} {j_data[2]} | ELO: {elo_act} -> {nuevo} ({signo}{var:.1f}) | Performance: {perf} pts",
                text_color=color
            )
        except ValueError:
            self.lbl_preview_calculo.configure(
                text="Introduce números válidos en Rc, partidas y puntos.",
                text_color="#f39c12"
            )

    def _add_participante_torneo(self):
        seleccion = self.combo_jugadores.get()
        if not seleccion or seleccion not in self.jugadores_map:
            messagebox.showerror("Error", "Selecciona un jugador válido.")
            return
        
        j_data = self.jugadores_map[seleccion]
        jid, nom, ape, elo_act = j_data

        # Evitar duplicados
        if any(p["jugador_id"] == jid for p in self.torneo_participantes):
            messagebox.showwarning("Atención", f"El jugador '{nom} {ape}' ya ha sido añadido a este torneo.")
            return

        try:
            rc = float(self.torneo_rc_entry.get().strip())
            partidas = int(self.torneo_partidas_entry.get().strip())
            puntos = float(self.torneo_puntos_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Revisa los campos numéricos (Rc, Partidas y Puntos).")
            return

        if partidas <= 0:
            messagebox.showerror("Error", "El número de partidas debe ser mayor que 0.")
            return
        if not (0 <= puntos <= partidas):
            messagebox.showerror("Error", f"Los puntos deben estar entre 0 y {partidas}.")
            return

        # Cálculo ELO (K=10) y Performance FIDE
        k = self.backend.determinar_k_factor()
        pd = self.backend.calculo_Pd(elo_act, rc)
        var = self.backend.calculo_variacion_elo(pd * partidas, puntos, k)
        nuevo_elo = round(elo_act + var)
        perf = self.backend.calcular_performance(rc, puntos, partidas)

        item = {
            "jugador_id": jid,
            "nombre": f"{nom} {ape}",
            "elo_inicial": elo_act,
            "elo_rivales_medio": rc,
            "num_partidas": partidas,
            "puntos_obtenidos": puntos,
            "variacion_elo": var,
            "k_factor": k,
            "nuevo_elo": nuevo_elo,
            "performance": perf
        }
        self.torneo_participantes.append(item)
        self._refresh_torneo_table()

        # Limpiar campos y devolver foco al buscador de jugador para el siguiente
        self.torneo_search_var.set("")
        self.torneo_rc_entry.delete(0, "end")
        self.torneo_partidas_entry.delete(0, "end")
        self.torneo_puntos_entry.delete(0, "end")
        self.torneo_search_entry.focus_set()

    def _quitar_participante_torneo(self):
        sel = self.tree_torneo.selection()
        if not sel: return
        idx = self.tree_torneo.index(sel[0])
        self.torneo_participantes.pop(idx)
        self._refresh_torneo_table()

    def _refresh_torneo_table(self):
        self.tree_torneo.delete(*self.tree_torneo.get_children())
        for p in self.torneo_participantes:
            pts_str = f"{int(p['puntos_obtenidos']) if p['puntos_obtenidos'].is_integer() else p['puntos_obtenidos']}/{p['num_partidas']}"
            self.tree_torneo.insert("", "end", values=(
                p["jugador_id"], p["nombre"], p["elo_inicial"], f"{p['elo_rivales_medio']:.1f}",
                p["num_partidas"], pts_str, p["performance"], f"{p['variacion_elo']:+.1f}", p["nuevo_elo"]
            ))
        self.lbl_torneo_count.configure(text=f"Participantes: {len(self.torneo_participantes)}")

    def _guardar_torneo_completo(self):
        nombre_torneo = self.torneo_nombre_entry.get().strip()
        fecha_torneo = self.torneo_fecha_entry.get().strip()

        if not nombre_torneo:
            messagebox.showerror("Error", "Introduce el nombre del torneo.")
            return

        try:
            datetime.strptime(fecha_torneo, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Formato de fecha inválido. Usa YYYY-MM-DD.")
            return

        if not self.torneo_participantes:
            messagebox.showwarning("Atención", "No has añadido ningún participante al torneo.")
            return

        if not messagebox.askyesno(
            "Confirmar Guardado", 
            f"Se va a registrar el torneo '{nombre_torneo}' con {len(self.torneo_participantes)} jugadores y actualizar los ELOs.\n\n¿Continuar?"
        ):
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO torneos (nombre, fecha) VALUES (?, ?)", (nombre_torneo, fecha_torneo))
            torneo_id = cursor.lastrowid

            for res in self.torneo_participantes:
                cursor.execute('''
                    INSERT INTO participaciones 
                    (jugador_id, torneo_id, elo_inicial, elo_rivales_medio, num_partidas, puntos_obtenidos, variacion_elo, k_factor, fecha) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (res['jugador_id'], torneo_id, res['elo_inicial'], res['elo_rivales_medio'], res['num_partidas'], res['puntos_obtenidos'], res['variacion_elo'], res['k_factor'], fecha_torneo))
                
                cursor.execute('''
                    UPDATE jugadores 
                    SET elo = ?, num_torneos = num_torneos + 1, fecha_ultimo_torneo = ?, variacion_ultima_lista = variacion_ultima_lista + ? 
                    WHERE id = ?
                ''', (res['nuevo_elo'], fecha_torneo, round(res['variacion_elo']), res['jugador_id']))

        messagebox.showinfo("Éxito", f"Torneo '{nombre_torneo}' guardado y ELOs actualizados.")
        self.torneo_participantes.clear()
        self.torneo_nombre_entry.delete(0, "end")
        self._refresh_torneo_table()
        self.select_view("ranking")

    # =========================================================================
    # VISTA 3: FICHA DEL JUGADOR Y ESTADÍSTICAS
    # =========================================================================
    def _create_ficha_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self, corner_radius=12)
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        # 1. Barra de selección de jugador
        top_bar = ctk.CTkFrame(view, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        top_bar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(top_bar, text="Buscar Jugador:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=(0, 8))

        self.ficha_search_var = tk.StringVar()
        self.ficha_search_var.trace_add("write", lambda *args: self._on_filter_ficha_jugadores())
        
        self.ficha_search_entry = ctk.CTkEntry(
            top_bar, 
            placeholder_text="🔍 Escribe nombre o apellido...", 
            textvariable=self.ficha_search_var,
            height=34,
            width=240
        )
        self.ficha_search_entry.grid(row=0, column=1, padx=(0, 8), sticky="w")
        self.ficha_search_entry.bind("<Return>", lambda e: self.ficha_combo.focus_set())
        self.ficha_search_entry.bind("<Down>", lambda e: self.ficha_combo.focus_set())

        self.ficha_combo = ctk.CTkComboBox(top_bar, height=34, width=300, command=self._on_ficha_player_selected)
        self.ficha_combo.grid(row=0, column=2, sticky="w")

        btn_export_html = ctk.CTkButton(top_bar, text="🌐 Exportar HTML Oficial", height=34, fg_color="#8e44ad", hover_color="#6c3483", command=self._exportar_ficha_html)
        btn_export_html.grid(row=0, column=3, padx=(10, 4))

        btn_export_ficha = ctk.CTkButton(top_bar, text="📄 TXT", width=70, height=34, fg_color="#34495e", hover_color="#2c3e50", command=self._exportar_ficha_actual)
        btn_export_ficha.grid(row=0, column=4, padx=(4, 8))

        if self.escudo_small:
            ctk.CTkLabel(top_bar, image=self.escudo_small, text="").grid(row=0, column=5, padx=(6, 0))

        # 2. Tarjetas de Resumen
        self.cards_frame = ctk.CTkFrame(view, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_f_elo = self._make_stat_box(self.cards_frame, 0, "ELO ACTUAL", "---", "#9b59b6")
        self.card_f_rank = self._make_stat_box(self.cards_frame, 1, "RANKING CLUB", "---", "#3498db")
        self.card_f_peak = self._make_stat_box(self.cards_frame, 2, "PICO MÁXIMO (PEAK)", "---", "#f1c40f")
        self.card_f_perf = self._make_stat_box(self.cards_frame, 3, "MEJOR PERFORMANCE", "---", "#2ecc71")

        # 3. Pestañas interiores: Trayectoria vs Récords
        tabs_ficha = ctk.CTkTabview(view)
        tabs_ficha.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        
        tab_trayectoria = tabs_ficha.add("Trayectoria Torneo a Torneo")
        tab_records = tabs_ficha.add("Detalles y Récords Globales")

        # Tabla en pestaña Trayectoria
        tab_trayectoria.grid_columnconfigure(0, weight=1)
        tab_trayectoria.grid_rowconfigure(0, weight=1)

        cols_f = ("num", "fecha", "torneo", "elo_ini", "rc", "pts", "perf", "var", "nuevo_elo")
        self.tree_ficha = ttk.Treeview(tab_trayectoria, columns=cols_f, show="headings", selectmode="browse")
        self.tree_ficha.heading("num", text="#")
        self.tree_ficha.heading("fecha", text="FECHA")
        self.tree_ficha.heading("torneo", text="TORNEO")
        self.tree_ficha.heading("elo_ini", text="ELO INI")
        self.tree_ficha.heading("rc", text="RIV. MED")
        self.tree_ficha.heading("pts", text="PUNTOS")
        self.tree_ficha.heading("perf", text="PERF.")
        self.tree_ficha.heading("var", text="VAR.")
        self.tree_ficha.heading("nuevo_elo", text="NUEVO ELO")

        self.tree_ficha.column("num", width=40, anchor="center")
        self.tree_ficha.column("fecha", width=100, anchor="center")
        self.tree_ficha.column("torneo", width=300, anchor="w")
        self.tree_ficha.column("elo_ini", width=75, anchor="center")
        self.tree_ficha.column("rc", width=75, anchor="center")
        self.tree_ficha.column("pts", width=75, anchor="center")
        self.tree_ficha.column("perf", width=75, anchor="center")
        self.tree_ficha.column("var", width=75, anchor="center")
        self.tree_ficha.column("nuevo_elo", width=80, anchor="center")

        scr_f = ttk.Scrollbar(tab_trayectoria, orient="vertical", command=self.tree_ficha.yview)
        self.tree_ficha.configure(yscrollcommand=scr_f.set)
        self.tree_ficha.grid(row=0, column=0, sticky="nsew")
        scr_f.grid(row=0, column=1, sticky="ns")

        # Contenido pestaña Récords
        tab_records.grid_columnconfigure(0, weight=1)
        self.txt_records = ctk.CTkTextbox(tab_records, font=ctk.CTkFont(family="Consolas", size=13))
        self.txt_records.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        tab_records.grid_rowconfigure(0, weight=1)

        self.current_ficha_id = None
        return view

    def _make_stat_box(self, parent, col, title, initial_val, color):
        box = ctk.CTkFrame(parent, corner_radius=10)
        box.grid(row=0, column=col, padx=6, pady=4, sticky="ew")
        ctk.CTkLabel(box, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color=color).pack(pady=(8, 2))
        lbl = ctk.CTkLabel(box, text=initial_val, font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(pady=(0, 8))
        return lbl

    def _on_show_ficha(self):
        with self.get_connection() as conn:
            jugadores = conn.cursor().execute("SELECT id, nombre, apellidos FROM jugadores ORDER BY nombre ASC").fetchall()
        
        self.all_ficha_jugadores_map = {f"{j[0]} - {j[1]} {j[2]}": j[0] for j in jugadores}
        self.ficha_jugadores_map = dict(self.all_ficha_jugadores_map)
        self.ficha_search_var.set("")
        self._on_filter_ficha_jugadores()

        if self.current_ficha_id:
            for k, v in self.ficha_jugadores_map.items():
                if v == self.current_ficha_id:
                    self.ficha_combo.set(k)
                    break
            self._cargar_ficha_por_id(self.current_ficha_id)
        elif self.ficha_jugadores_map:
            primero = list(self.ficha_jugadores_map.keys())[0]
            self.ficha_combo.set(primero)
            self._cargar_ficha_por_id(self.ficha_jugadores_map[primero])

    def _on_filter_ficha_jugadores(self):
        if not hasattr(self, "all_ficha_jugadores_map"): return
        raw_query = self.ficha_search_var.get().strip()
        q_norm = self._normalizar_texto(raw_query)
        
        if not q_norm:
            filtered = list(self.all_ficha_jugadores_map.keys())
        else:
            q_words = q_norm.split()
            filtered = []
            for k in self.all_ficha_jugadores_map.keys():
                k_norm = self._normalizar_texto(k)
                if all(word in k_norm for word in q_words):
                    filtered.append(k)
                    
        self.ficha_jugadores_map = {k: self.all_ficha_jugadores_map[k] for k in filtered}
        
        if filtered:
            self.ficha_combo.configure(values=filtered)
            self.ficha_combo.set(filtered[0])
            self._cargar_ficha_por_id(self.ficha_jugadores_map[filtered[0]])
        else:
            self.ficha_combo.configure(values=["No hay coincidencias"])
            self.ficha_combo.set("No hay coincidencias")

    def _on_ficha_player_selected(self, choice: str):
        if choice in self.ficha_jugadores_map:
            self._cargar_ficha_por_id(self.ficha_jugadores_map[choice])

    def _cargar_ficha_por_id(self, jid: int):
        self.current_ficha_id = jid
        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugador = cursor.execute('''
                SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, num_torneos, fecha_ultimo_torneo, fecha_creacion 
                FROM jugadores WHERE id = ?
            ''', (jid,)).fetchone()
            
            if not jugador: return

            j_id, nom, ape, elo_act, tit, var_l, num_torn, fec_ult, fec_crea = jugador
            
            # Ranking
            ranking_list = cursor.execute("SELECT id FROM jugadores ORDER BY elo DESC, num_torneos DESC").fetchall()
            pos = next((i for i, (pid,) in enumerate(ranking_list, 1) if pid == jid), len(ranking_list))

            # Participaciones
            participaciones = cursor.execute('''
                SELECT p.id, t.fecha, t.nombre, p.elo_inicial, p.elo_rivales_medio, 
                       p.num_partidas, p.puntos_obtenidos, p.variacion_elo, p.k_factor
                FROM participaciones p JOIN torneos t ON p.torneo_id = t.id
                WHERE p.jugador_id = ? ORDER BY t.fecha ASC, p.id ASC
            ''', (jid,)).fetchall()

        # Actualizar cajas
        self.card_f_elo.configure(text=str(elo_act))
        self.card_f_rank.configure(text=f"#{pos} de {len(ranking_list)}")

        self.tree_ficha.delete(*self.tree_ficha.get_children())
        self.txt_records.delete("1.0", "end")

        if not participaciones:
            self.card_f_peak.configure(text=str(elo_act))
            self.card_f_perf.configure(text="---")
            self.txt_records.insert("1.0", "Este jugador aún no tiene torneos disputados.")
            return

        puntos_elo = [(participaciones[0][1], participaciones[0][2], participaciones[0][3])]
        for p in participaciones:
            puntos_elo.append((p[1], p[2], round(p[3] + p[7])))

        peak_fecha, peak_torneo, peak_elo = max(puntos_elo, key=lambda x: x[2])
        min_fecha, min_torneo, min_elo = min(puntos_elo, key=lambda x: x[2])
        
        perfs = [(p, self.backend.calcular_performance(p[4], p[6], p[5])) for p in participaciones]
        best_part, best_perf = max(perfs, key=lambda x: x[1])

        max_gain_part = max(participaciones, key=lambda p: p[7])
        max_loss_part = min(participaciones, key=lambda p: p[7])

        tot_partidas = sum(p[5] for p in participaciones)
        tot_puntos = sum(p[6] for p in participaciones)
        efectividad = (tot_puntos / tot_partidas * 100) if tot_partidas > 0 else 0
        elo_rivales_ponderado = (sum(p[4] * p[5] for p in participaciones) / tot_partidas) if tot_partidas > 0 else 0
        balance_elo_total = sum(p[7] for p in participaciones)

        self.card_f_peak.configure(text=f"{peak_elo} pts")
        self.card_f_perf.configure(text=f"{best_perf} pts")

        # Llenar tabla trayectoria
        for i, (pid, t_fecha, t_nombre, elo_ini, r_med, n_part, pts, var, k) in enumerate(participaciones, 1):
            perf_i = self.backend.calcular_performance(r_med, pts, n_part)
            pts_str = f"{int(pts) if pts.is_integer() else pts}/{n_part}"
            nuevo_elo = round(elo_ini + var)
            self.tree_ficha.insert("", "end", values=(
                i, t_fecha, t_nombre, elo_ini, f"{r_med:.1f}", pts_str, perf_i, f"{var:+.1f}", nuevo_elo
            ))

        # Llenar texto de récords
        dias = self.backend.calcular_dias_desde_ultimo_torneo(fec_ult)
        rec_text = f"""================================================================================
FICHA DE DETALLES: {nom.upper()} {ape.upper()} (ID: {j_id})
================================================================================
• Título:                   {tit or 'Sin título'}
• ELO Actual:               {elo_act} (Posición #{pos} de {len(ranking_list)})
• Variación última lista:   {var_l:+d}
• Estado de actividad:      Último torneo el {fec_ult or 'Nunca'} (hace {dias} días)
• Fecha de alta:            {fec_crea[:10] if fec_crea else 'Desconocida'}

RÉCORDS HISTÓRICOS EN EL CLUB:
--------------------------------------------------------------------------------
★ Pico Máximo de ELO (Peak): {peak_elo} pts ({peak_torneo}, {peak_fecha})
▼ Suelo Mínimo de ELO:       {min_elo} pts ({min_torneo}, {min_fecha})
🏆 Mejor Performance (Rp):    {best_perf} pts ({best_part[2]}, {best_part[6]:.1f}/{best_part[5]} pts)
▲ Mayor ganancia en torneo:  {max_gain_part[7]:+.1f} pts ({max_gain_part[2]})
▼ Mayor pérdida en torneo:   {max_loss_part[7]:+.1f} pts ({max_loss_part[2]})

ESTADÍSTICAS GLOBALES:
--------------------------------------------------------------------------------
• Torneos disputados:        {len(participaciones)}
• Partidas disputadas:       {tot_partidas}
• Puntos obtenidos:          {tot_puntos:.1f} / {tot_partidas} ({efectividad:.1f}% efectividad)
• ELO medio de rivales:      {elo_rivales_ponderado:.1f}
• Balance neto acumulado:    {balance_elo_total:+.1f} pts
================================================================================
"""
        self.txt_records.insert("1.0", rec_text)

    def _exportar_ficha_actual(self):
        if not self.current_ficha_id:
            messagebox.showwarning("Atención", "Selecciona un jugador primero.")
            return
        
        content = self.txt_records.get("1.0", "end").strip()
        if not content: return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivos de Texto", "*.txt")],
            initialfile=f"ficha_jugador_{self.current_ficha_id}_{datetime.now().strftime('%Y%m%d')}.txt"
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Exportado", f"Ficha guardada en:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar la ficha: {e}")

    def _exportar_ficha_html(self):
        if not self.current_ficha_id:
            messagebox.showwarning("Atención", "Selecciona un jugador primero.")
            return
        
        archivo_creado = self.backend.exportar_ficha_html(self.current_ficha_id)
        if not archivo_creado:
            messagebox.showerror("Error", "No se pudo generar la ficha HTML.")
            return

        dest = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("Páginas Web HTML", "*.html")],
            initialfile=archivo_creado
        )
        if dest:
            try:
                shutil.move(archivo_creado, dest)
                messagebox.showinfo("Exportado", f"Ficha oficial con escudo guardada correctamente en:\n{dest}")
            except Exception as e:
                messagebox.showinfo("Exportado", f"Ficha oficial generada en: {archivo_creado}")
        else:
            try:
                if os.path.exists(archivo_creado):
                    os.remove(archivo_creado)
            except Exception:
                pass

    # =========================================================================
    # VISTA 4: HISTORIAL DE TORNEOS Y LISTAS
    # =========================================================================
    def _create_historial_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self, corner_radius=12)
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(0, weight=1)

        tabview = ctk.CTkTabview(view)
        tabview.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        # Pestaña A: Torneos Registrados
        tab_torneos = tabview.add("Torneos Registrados")
        tab_torneos.grid_columnconfigure(0, weight=1)
        tab_torneos.grid_rowconfigure(1, weight=1)

        # Botones de control de torneo
        btn_bar = ctk.CTkFrame(tab_torneos, fg_color="transparent")
        btn_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        btn_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(btn_bar, text="Torneos disputados y registrados:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        btn_del_torneo = ctk.CTkButton(
            btn_bar, 
            text="🗑️ Eliminar Torneo y Revertir ELO", 
            fg_color="#c0392b", 
            hover_color="#962d22",
            command=self._accion_eliminar_torneo
        )
        btn_del_torneo.grid(row=0, column=1, sticky="e")

        # Tabla de torneos
        self.tree_historial_torneos = ttk.Treeview(
            tab_torneos, 
            columns=("id", "nombre", "fecha", "jugadores"), 
            show="headings", 
            selectmode="browse"
        )
        self.tree_historial_torneos.heading("id", text="ID")
        self.tree_historial_torneos.heading("nombre", text="NOMBRE DEL TORNEO")
        self.tree_historial_torneos.heading("fecha", text="FECHA")
        self.tree_historial_torneos.heading("jugadores", text="PARTICIPANTES")

        self.tree_historial_torneos.column("id", width=50, anchor="center")
        self.tree_historial_torneos.column("nombre", width=380, anchor="w")
        self.tree_historial_torneos.column("fecha", width=120, anchor="center")
        self.tree_historial_torneos.column("jugadores", width=100, anchor="center")

        scr_ht = ttk.Scrollbar(tab_torneos, orient="vertical", command=self.tree_historial_torneos.yview)
        self.tree_historial_torneos.configure(yscrollcommand=scr_ht.set)
        self.tree_historial_torneos.grid(row=1, column=0, sticky="nsew")
        scr_ht.grid(row=1, column=1, sticky="ns")

        # Pestaña B: Listas Oficiales Anteriores
        tab_listas = tabview.add("Historial Listas Oficiales")
        tab_listas.grid_columnconfigure(0, weight=1)
        tab_listas.grid_rowconfigure(1, weight=1)

        self.tree_listas_anteriores = ttk.Treeview(
            tab_listas,
            columns=("id", "fecha"),
            show="headings",
            selectmode="browse"
        )
        self.tree_listas_anteriores.heading("id", text="ID")
        self.tree_listas_anteriores.heading("fecha", text="FECHA DE GENERACIÓN (OFICIAL)")
        self.tree_listas_anteriores.column("id", width=60, anchor="center")
        self.tree_listas_anteriores.column("fecha", width=300, anchor="center")

        scr_hl = ttk.Scrollbar(tab_listas, orient="vertical", command=self.tree_listas_anteriores.yview)
        self.tree_listas_anteriores.configure(yscrollcommand=scr_hl.set)
        self.tree_listas_anteriores.grid(row=1, column=0, sticky="nsew")
        scr_hl.grid(row=1, column=1, sticky="ns")

        return view

    def _on_show_historial(self):
        # 1. Torneos
        self.tree_historial_torneos.delete(*self.tree_historial_torneos.get_children())
        with self.get_connection() as conn:
            torneos = conn.cursor().execute('''
                SELECT t.id, t.nombre, t.fecha, COUNT(p.id) 
                FROM torneos t LEFT JOIN participaciones p ON t.id = p.torneo_id 
                GROUP BY t.id ORDER BY t.fecha DESC, t.id DESC
            ''').fetchall()

        for tid, nom, fec, count_j in torneos:
            self.tree_historial_torneos.insert("", "end", values=(tid, nom, fec, count_j))

        # 2. Listas
        self.tree_listas_anteriores.delete(*self.tree_listas_anteriores.get_children())
        with self.get_connection() as conn:
            listas = conn.cursor().execute("SELECT id, fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC").fetchall()
        
        for lid, f_gen in listas:
            self.tree_listas_anteriores.insert("", "end", values=(lid, self.backend.utc_to_local_str(f_gen)))

    def _accion_eliminar_torneo(self):
        sel = self.tree_historial_torneos.selection()
        if not sel:
            messagebox.showwarning("Atención", "Selecciona un torneo a eliminar.")
            return

        values = self.tree_historial_torneos.item(sel[0], "values")
        torneo_id = int(values[0])
        nombre_torneo = values[1]
        fecha_torneo = values[2]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            participaciones = cursor.execute(
                'SELECT jugador_id, variacion_elo FROM participaciones WHERE torneo_id = ?', 
                (torneo_id,)
            ).fetchall()

        if not messagebox.askyesno(
            "Confirmar Reversión",
            f"¡Atención!\nSe eliminará el torneo '{nombre_torneo}' ({fecha_torneo}) "
            f"y se revertirán {len(participaciones)} participaciones en el ELO de los jugadores.\n\n¿Confirmar?"
        ):
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for jugador_id, variacion in participaciones:
                cursor.execute(
                    '''UPDATE jugadores 
                       SET elo = elo - ?, num_torneos = num_torneos - 1, 
                           variacion_ultima_lista = variacion_ultima_lista - ? 
                       WHERE id = ?''',
                    (round(variacion), round(variacion), jugador_id)
                )

            cursor.execute('DELETE FROM participaciones WHERE torneo_id = ?', (torneo_id,))
            cursor.execute('DELETE FROM torneos WHERE id = ?', (torneo_id,))

            for jugador_id, _ in participaciones:
                cursor.execute('''
                    SELECT MAX(t.fecha) 
                    FROM participaciones p 
                    JOIN torneos t ON p.torneo_id = t.id 
                    WHERE p.jugador_id = ?
                ''', (jugador_id,))
                res = cursor.fetchone()
                ultima_fecha = res[0] if res and res[0] else None
                cursor.execute('UPDATE jugadores SET fecha_ultimo_torneo = ? WHERE id = ?', (ultima_fecha, jugador_id))

        messagebox.showinfo("Éxito", f"Torneo '{nombre_torneo}' eliminado y ELO revertido.")
        self._on_show_historial()

    # =========================================================================
    # VISTA 5: MANTENIMIENTO Y EXPORTACIÓN
    # =========================================================================
    def _create_mantenimiento_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self, corner_radius=12)
        view.grid_columnconfigure((0, 1), weight=1)
        view.grid_rowconfigure((0, 1), weight=1)

        # Panel 1: Listas Oficiales y Ciclos
        p1 = ctk.CTkFrame(view, corner_radius=10)
        p1.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        ctk.CTkLabel(p1, text="LISTAS OFICIALES", font=ctk.CTkFont(size=14, weight="bold"), text_color="#3498db").pack(pady=(16, 8))
        ctk.CTkLabel(
            p1, 
            text="Generar una nueva lista oficial guarda el ranking histórico\nen la base de datos y resetea las variaciones (+/-) a cero.",
            wraplength=340,
            justify="center",
            text_color="#bdc3c7"
        ).pack(pady=(0, 16), padx=16)
        ctk.CTkButton(p1, text="📋 Generar Nueva Lista Oficial", height=38, fg_color="#2980b9", command=self._accion_generar_nueva_lista).pack(pady=(0, 16))

        # Panel 2: Regulación Anual de ELO
        p2 = ctk.CTkFrame(view, corner_radius=10)
        p2.grid(row=0, column=1, padx=16, pady=16, sticky="nsew")
        ctk.CTkLabel(p2, text="REGULACIÓN ANUAL (1 SEPT.)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f39c12").pack(pady=(16, 8))
        ctk.CTkLabel(
            p2, 
            text="Aplica una deducción de 50 puntos de ELO (suelo en 2000)\na los jugadores inactivos por más de 365 días y actualiza\nsu fecha de último torneo al 1 de septiembre.",
            wraplength=340,
            justify="center",
            text_color="#bdc3c7"
        ).pack(pady=(0, 16), padx=16)
        ctk.CTkButton(p2, text="⚖️ Aplicar Regulación Anual", height=38, fg_color="#d35400", command=self._accion_regulacion_anual).pack(pady=(0, 16))

        # Panel 3: Copias de Seguridad
        p3 = ctk.CTkFrame(view, corner_radius=10)
        p3.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        ctk.CTkLabel(p3, text="COPIAS DE SEGURIDAD (BACKUP)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2ecc71").pack(pady=(16, 8))
        ctk.CTkLabel(
            p3, 
            text="Crea una copia de seguridad fechada de la base de datos\npara proteger los datos ante cualquier imprevisto.",
            wraplength=340,
            justify="center",
            text_color="#bdc3c7"
        ).pack(pady=(0, 16), padx=16)
        ctk.CTkButton(p3, text="💾 Crear Copia de Seguridad Ahora", height=38, fg_color="#27ae60", command=self._crear_backup_manual).pack(pady=(0, 16))

        # Panel 4: Exportaciones
        p4 = ctk.CTkFrame(view, corner_radius=10)
        p4.grid(row=1, column=1, padx=16, pady=(0, 16), sticky="nsew")
        ctk.CTkLabel(p4, text="EXPORTAR RANKING", font=ctk.CTkFont(size=14, weight="bold"), text_color="#9b59b6").pack(pady=(16, 8))
        ctk.CTkLabel(
            p4, 
            text="Exporta la clasificación oficial a archivos listos\npara imprimir, Excel o compartir por WhatsApp.",
            wraplength=340,
            justify="center",
            text_color="#bdc3c7"
        ).pack(pady=(0, 12), padx=16)

        btn_row = ctk.CTkFrame(p4, fg_color="transparent")
        btn_row.pack(pady=(0, 16))

        ctk.CTkButton(btn_row, text="🌐 HTML", width=80, height=36, fg_color="#8e44ad", command=self._export_html).pack(side="left", padx=3)
        ctk.CTkButton(btn_row, text="📊 CSV", width=80, height=36, fg_color="#16a085", command=self._export_csv).pack(side="left", padx=3)
        ctk.CTkButton(btn_row, text="📄 TXT", width=80, height=36, fg_color="#34495e", command=self._export_txt).pack(side="left", padx=3)
        ctk.CTkButton(btn_row, text="📱 WhatsApp", width=105, height=36, fg_color="#25d366", hover_color="#1e8449", text_color="#ffffff", command=self._copiar_ranking_whatsapp).pack(side="left", padx=3)
        ctk.CTkButton(btn_row, text="🌍 Web (index.html)", width=135, height=36, fg_color="#1b3a57", hover_color="#2c5282", text_color="#ffffff", command=self._export_web_interactiva).pack(side="left", padx=3)

        return view

    def _on_show_mantenimiento(self):
        pass

    def _accion_generar_nueva_lista(self):
        if not messagebox.askyesno(
            "Confirmar Generación de Lista", 
            "¿Confirmar la generación de una nueva lista?\n\nEsto guardará el ranking histórico y reseteará las variaciones acumuladas a 0."
        ):
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugadores_actuales = cursor.execute("SELECT nombre, apellidos, elo, num_torneos FROM jugadores ORDER BY elo DESC").fetchall()
            fecha_generacion = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('INSERT INTO listas_elo (fecha_generacion) VALUES (?)', (fecha_generacion,))
            lista_id = cursor.lastrowid
            for nombre, apellidos, elo, num_torneos in jugadores_actuales:
                cursor.execute('INSERT INTO historial_jugadores_lista (lista_id, nombre, apellidos, elo, num_torneos) VALUES (?, ?, ?, ?, ?)', (lista_id, nombre, apellidos, elo, num_torneos))
            cursor.execute('UPDATE jugadores SET variacion_ultima_lista = 0')

        messagebox.showinfo("Éxito", "Nueva lista oficial generada y ranking histórico guardado.")
        self.select_view("ranking")

    def _accion_regulacion_anual(self):
        hoy = datetime.now()
        fecha_actualizacion = hoy.replace(month=9, day=1).strftime("%Y-%m-%d")
        fecha_limite = (hoy - timedelta(days=365)).strftime("%Y-%m-%d")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugadores = cursor.execute(
                'SELECT id, nombre, apellidos, elo FROM jugadores WHERE elo > 2000 AND fecha_ultimo_torneo < ?', 
                (fecha_limite,)
            ).fetchall()

        if not jugadores:
            messagebox.showinfo("Regulación Anual", "No hay jugadores que cumplan los requisitos de inactividad (>365 días y ELO > 2000).")
            return

        msg = f"Se aplicará la deducción de ELO y se actualizará la fecha al {fecha_actualizacion}:\n\n"
        for id_j, nom, ape, elo in jugadores:
            nuevo = max(2000, elo - 50)
            msg += f"• {nom} {ape}: {elo} -> {nuevo}\n"
        msg += "\n¿Confirmar cambios?"

        if messagebox.askyesno("Confirmar Regulación", msg):
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for id_j, _, _, elo in jugadores:
                    nuevo_elo = max(2000, elo - 50)
                    reduccion = elo - nuevo_elo
                    cursor.execute(
                        'UPDATE jugadores SET elo = ?, variacion_ultima_lista = variacion_ultima_lista - ?, fecha_ultimo_torneo = ? WHERE id = ?', 
                        (nuevo_elo, reduccion, fecha_actualizacion, id_j)
                    )
            messagebox.showinfo("Éxito", f"Regulación aplicada a {len(jugadores)} jugadores.")
            self.select_view("ranking")

    def _crear_backup_manual(self):
        if not os.path.exists(self.db_name):
            messagebox.showerror("Error", "No se encontró el archivo de base de datos.")
            return

        backup_name = f"elo_club_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        try:
            shutil.copy2(self.db_name, backup_name)
            messagebox.showinfo("Copia Creada", f"Copia de seguridad guardada como:\n{backup_name}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear la copia: {e}")

    def _export_html(self):
        dest = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("Archivos Web HTML", "*.html")],
            initialfile=f"lista_elo_blitz_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.html"
        )
        if not dest: return
        self._ejecutar_export(self.backend.exportar_lista_html, dest, "HTML")

    def _export_csv(self):
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Archivos CSV", "*.csv")],
            initialfile=f"lista_elo_blitz_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        )
        if not dest: return
        self._ejecutar_export(self.backend.exportar_lista_csv, dest, "CSV")

    def _export_txt(self):
        dest = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto accesible / WhatsApp", "*.txt"), ("Todos los archivos", "*.*")],
            initialfile=f"lista_elo_blitz_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        )
        if not dest: return
        self._ejecutar_export(self.backend.exportar_lista_txt, dest, "TXT")
        # También copiamos automáticamente al portapapeles para conveniencia
        try:
            texto = self.backend.generar_texto_ranking_accesible()
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.update()
        except Exception:
            pass

    def _copiar_ranking_whatsapp(self):
        if not self.backend.hay_jugadores():
            messagebox.showwarning("Atención", "No hay jugadores registrados en la base de datos.")
            return
        try:
            texto = self.backend.generar_texto_ranking_accesible()
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.update()
            messagebox.showinfo(
                "Copiado para WhatsApp", 
                "¡El ranking oficial ha sido copiado al portapapeles!\n\n"
                "✓ Formato accesible para lectores de pantalla.\n"
                "✓ Compatible con el markdown de WhatsApp.\n\n"
                "Ya puedes ir al chat del club y pulsar 'Ctrl + V' para pegarlo."
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo copiar al portapapeles: {e}")

    def _export_web_interactiva(self):
        if not self.backend.hay_jugadores():
            messagebox.showwarning("Atención", "No hay jugadores registrados en la base de datos.")
            return

        dest = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("Página Web Completa", "*.html"), ("Todos los archivos", "*.*")],
            initialfile="index.html"
        )
        if not dest:
            return

        try:
            res = self.backend.exportar_web_interactiva(dest)
            if res:
                if messagebox.askyesno(
                    "Web Interactiva Generada",
                    f"¡Portal web interactivo generado con éxito!\n\nArchivo guardado en:\n{dest}\n\n¿Deseas abrir la página en tu navegador predeterminado ahora?"
                ):
                    webbrowser.open(os.path.abspath(dest))
            else:
                messagebox.showerror("Error", "No se pudo generar la página web interactiva.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al generar la web: {e}")

    def _ejecutar_export(self, func, target_path: str, tipo: str):
        old_files = set(os.listdir("."))
        func()
        new_files = set(os.listdir(".")) - old_files
        
        created = next((f for f in new_files if f.endswith(f".{tipo.lower()}")), None)
        if created:
            try:
                shutil.move(created, target_path)
                messagebox.showinfo("Exportado", f"Archivo {tipo} guardado correctamente en:\n{target_path}")
            except Exception as e:
                messagebox.showinfo("Exportado", f"Archivo generado en: {created}")
        else:
            messagebox.showinfo("Exportado", f"Archivo {tipo} generado en la carpeta actual.")


def main():
    app = ELOClubGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
