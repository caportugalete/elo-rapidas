#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import base64
import sqlite3
import csv
import webbrowser
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional
import colorama

# Inicializa colorama para que los colores funcionen en todas las terminales y se reseteen automáticamente.
colorama.init(autoreset=True)

class Colors:
    """Clase para almacenar los códigos de color ANSI y facilitar su uso."""
    RESET = colorama.Style.RESET_ALL
    GREEN = colorama.Fore.GREEN
    RED = colorama.Fore.RED
    YELLOW = colorama.Fore.YELLOW
    BLUE = colorama.Fore.BLUE
    MAGENTA = colorama.Fore.MAGENTA
    CYAN = colorama.Fore.CYAN

class ELOClub:
    """Clase principal que encapsula toda la lógica de la aplicación."""
    def __init__(self, db_name="elo_club.db"):
        """Constructor de la clase. Se ejecuta al crear un objeto ELOClub."""
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        """Devuelve una conexión a la base de datos con claves foráneas activadas."""
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def utc_to_local_str(self, utc_date_str: str) -> str:
        if not utc_date_str: return ""
        try:
            from datetime import timezone
            dt = datetime.strptime(utc_date_str, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return utc_date_str
    
    def init_database(self):
        """Crea todas las tablas necesarias en la base de datos si no existen."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jugadores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, apellidos TEXT NOT NULL,
                    elo INTEGER NOT NULL, titulo TEXT DEFAULT '', variacion_ultima_lista INTEGER DEFAULT 0,
                    num_torneos INTEGER DEFAULT 0, fecha_ultimo_torneo TEXT, fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS torneos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, fecha TEXT NOT NULL,
                    fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS participaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, jugador_id INTEGER, torneo_id INTEGER, elo_inicial INTEGER,
                    elo_rivales_medio REAL, num_partidas INTEGER, puntos_obtenidos REAL, variacion_elo REAL,
                    k_factor REAL, fecha TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (jugador_id) REFERENCES jugadores (id), FOREIGN KEY (torneo_id) REFERENCES torneos (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS listas_elo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_generacion TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historial_jugadores_lista (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, lista_id INTEGER, nombre TEXT, apellidos TEXT,
                    elo INTEGER, num_torneos INTEGER, FOREIGN KEY (lista_id) REFERENCES listas_elo (id)
                )
            ''')

    def calcular_performance(self, elo_rivales_medio: float, puntos: float, partidas: int) -> int:
        if partidas <= 0: return 0
        porcentaje = puntos / partidas
        delta_lookup = {
            1.0: 800, 0.95: 450, 0.9: 350, 0.85: 290, 0.8: 240, 0.75: 202, 0.7: 166, 0.65: 133, 0.6: 102, 0.55: 72, 
            0.5: 0, 0.45: -72, 0.4: -102, 0.35: -133, 0.3: -166, 0.25: -202, 0.2: -240, 0.15: -290, 0.1: -350, 
            0.05: -451, 0.0: -800
        }
        closest_key = min(delta_lookup.keys(), key=lambda k: abs(k - porcentaje))
        return int(elo_rivales_medio + delta_lookup[closest_key])

    def calcular_dias_desde_ultimo_torneo(self, fecha_ultimo_torneo: str) -> int:
        if not fecha_ultimo_torneo: return 0
        try:
            fecha_ultimo = datetime.strptime(fecha_ultimo_torneo, "%Y-%m-%d")
            return (datetime.now() - fecha_ultimo).days
        except ValueError:
            return 0
    
    def calculo_Pd(self, elo_jugador: float, elo_rival_medio: float) -> float:
        return 1 / (1 + 10 ** ((elo_rival_medio - elo_jugador) / 400))
    
    def determinar_k_factor(self) -> float:
        return 10.0
    
    def calculo_variacion_elo(self, resultado_esperado: float, resultado_obtenido: float, k: float) -> float:
        return (resultado_obtenido - resultado_esperado) * k
    
    def crear_jugador(self):
        print(f"\n{Colors.YELLOW}=== CREAR NUEVO JUGADOR ==={Colors.RESET}")
        while not (nombre := input("Nombre: ").strip()):
            print(f"{Colors.RED}El nombre no puede estar vacío.{Colors.RESET}")
        while not (apellidos := input("Apellidos: ").strip()):
            print(f"{Colors.RED}Los apellidos no pueden estar vacíos.{Colors.RESET}")
        elo = 2000
        while True:
            try:
                elo_input = input("ELO inicial (Enter para 2000): ").strip()
                if elo_input: elo = int(elo_input)
                break
            except ValueError:
                print(f"{Colors.RED}Por favor, introduce un número válido.{Colors.RESET}")
        titulo = input("Título (opcional): ").strip()
        with self.get_connection() as conn:
            conn.cursor().execute('INSERT INTO jugadores (nombre, apellidos, elo, titulo) VALUES (?, ?, ?, ?)', (nombre, apellidos, elo, titulo))
        print(f"\n{Colors.GREEN}✓ Jugador {nombre} {apellidos} creado exitosamente.{Colors.RESET}")

    def modificar_jugador(self):
        self.listar_jugadores()
        if not self.hay_jugadores(): return
        try:
            jugador_id = int(input("\nID del jugador a modificar: "))
        except ValueError:
            print(f"{Colors.RED}ID no válido.{Colors.RESET}")
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugador = cursor.execute('SELECT nombre, apellidos, elo, titulo FROM jugadores WHERE id = ?', (jugador_id,)).fetchone()
            if not jugador:
                print(f"{Colors.RED}Jugador no encontrado.{Colors.RESET}")
                return
                
            nombre_actual, apellidos_actual, elo_actual, titulo_actual = jugador
            print(f"\n{Colors.YELLOW}=== MODIFICAR JUGADOR: {nombre_actual} {apellidos_actual} ==={Colors.RESET}")
            print("(Presiona Enter para mantener el valor actual)")
            
            nuevo_nombre = input(f"Nombre ({nombre_actual}): ").strip() or nombre_actual
            nuevos_apellidos = input(f"Apellidos ({apellidos_actual}): ").strip() or apellidos_actual
            try:
                nuevo_elo_input = input(f"ELO ({elo_actual}): ").strip()
                nuevo_elo = int(nuevo_elo_input) if nuevo_elo_input else elo_actual
            except ValueError:
                print(f"{Colors.RED}ELO no válido. Se mantiene el valor actual.{Colors.RESET}")
                nuevo_elo = elo_actual
            
            nuevo_titulo_input = input(f"Título ({titulo_actual}) [escribe 'borrar' para eliminar]: ").strip()
            if nuevo_titulo_input.lower() == 'borrar': nuevo_titulo = ""
            elif nuevo_titulo_input == "": nuevo_titulo = titulo_actual
            else: nuevo_titulo = nuevo_titulo_input
                
            confirmacion = input(f"\n{Colors.YELLOW}¿Confirmar cambios? (s/N): {Colors.RESET}")
            if confirmacion.lower() == 's':
                cursor.execute('UPDATE jugadores SET nombre = ?, apellidos = ?, elo = ?, titulo = ? WHERE id = ?',
                               (nuevo_nombre, nuevos_apellidos, nuevo_elo, nuevo_titulo, jugador_id))
                print(f"\n{Colors.GREEN}✓ Jugador modificado exitosamente.{Colors.RESET}")
            else:
                print(f"{Colors.RED}Cambios descartados.{Colors.RESET}")

    def listar_jugadores(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            last_list_date_result = cursor.execute("SELECT fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC LIMIT 1").fetchone()
            last_list_date_str = f"Lista generada el: {self.utc_to_local_str(last_list_date_result[0])}" if last_list_date_result else "Aún no se ha generado ninguna lista"
            jugadores = cursor.execute('SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, num_torneos, fecha_ultimo_torneo FROM jugadores ORDER BY elo DESC, num_torneos DESC').fetchall()
            media_elo_result = cursor.execute("SELECT AVG(elo) FROM jugadores").fetchone()
            media_elo = media_elo_result[0] if media_elo_result and media_elo_result[0] is not None else 0
        
        if not jugadores:
            print(f"\n{Colors.YELLOW}No hay jugadores registrados.{Colors.RESET}")
            return
        
        print(f"\n{Colors.CYAN}{'='*120}{Colors.RESET}")
        print(f"{Colors.YELLOW}{last_list_date_str.center(120)}{Colors.RESET}")
        print(f"{Colors.CYAN}{'ID':<3} {'NOMBRE':<35} {'ELO':<6} {'TÍTULO':<8} {'VAR.':<6} {'TORN.':<6} {'ÚLT.TORNEO':<12} {'DÍAS INACTIVO':<15}{Colors.RESET}")
        print(f"{Colors.CYAN}{'-'*120}{Colors.RESET}")
        
        for id_j, nombre, apellidos, elo, titulo, var_lista, num_torn, fecha_ult in jugadores:
            nombre_completo = f"{nombre} {apellidos}"
            var_color = Colors.GREEN if var_lista > 0 else Colors.RED if var_lista < 0 else Colors.RESET
            var_str = f"{var_color}{var_lista:+d}{Colors.RESET}"
            dias = self.calcular_dias_desde_ultimo_torneo(fecha_ult)
            dias_color = Colors.RED if dias > 365 else Colors.YELLOW if dias > 180 else Colors.RESET
            print(f"{id_j:<3} {nombre_completo:<35} {Colors.MAGENTA}{elo:<6}{Colors.RESET} {titulo:<8} {var_str:<15} {num_torn:<6} {fecha_ult or 'Nunca':<12} {dias_color}{dias:<15}{Colors.RESET}")
        
        print(f"{Colors.CYAN}{'='*120}{Colors.RESET}")
        print(f"MEDIA ELO: {Colors.MAGENTA}{media_elo:.1f}{Colors.RESET} | JUGADORES: {len(jugadores)}")
        print(f"{Colors.CYAN}{'='*120}{Colors.RESET}")

    def eliminar_jugador(self):
        self.listar_jugadores()
        if not self.hay_jugadores(): return
        try:
            jugador_id = int(input("\nID del jugador a eliminar: "))
        except ValueError:
            print(f"{Colors.RED}ID no válido.{Colors.RESET}")
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugador = cursor.execute("SELECT nombre, apellidos FROM jugadores WHERE id = ?", (jugador_id,)).fetchone()
            if not jugador:
                print(f"{Colors.RED}Jugador no encontrado.{Colors.RESET}")
                return
                
            nombre, apellidos = jugador
            confirmacion = input(f"\n{Colors.RED}¿Seguro que quieres eliminar a {nombre} {apellidos}? Esta acción es irreversible. (s/N): {Colors.RESET}")
            if confirmacion.lower() == 's':
                cursor.execute("DELETE FROM participaciones WHERE jugador_id = ?", (jugador_id,))
                cursor.execute("DELETE FROM jugadores WHERE id = ?", (jugador_id,))
                print(f"\n{Colors.GREEN}✓ Jugador eliminado.{Colors.RESET}")
            else:
                print(f"{Colors.RED}Operación cancelada.{Colors.RESET}")

    def hay_jugadores(self) -> bool:
        with self.get_connection() as conn:
            return conn.cursor().execute("SELECT COUNT(*) FROM jugadores").fetchone()[0] > 0

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        """Elimina acentos, diacríticos y pasa a minúsculas para comparaciones insensibles."""
        if not texto:
            return ""
        return ''.join(
            c for c in unicodedata.normalize('NFD', texto) 
            if unicodedata.category(c) != 'Mn'
        ).lower()

    def buscar_jugador(self, entrada: str) -> Optional[int]:
        """Busca un jugador por ID o por coincidencia de nombre o apellidos.
        Soporta acentos o sin ellos, mayúsculas/minúsculas y nombres completos.
        Permite seleccionar si hay varias coincidencias. Devuelve el jugador_id o None."""
        entrada = entrada.strip()
        if not entrada or entrada == "0":
            return None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if entrada.isdigit():
                j = cursor.execute('SELECT id, nombre, apellidos, elo FROM jugadores WHERE id = ?', (int(entrada),)).fetchone()
                if j:
                    print(f"{Colors.GREEN}* Seleccionado: {j[1]} {j[2]} (ELO: {j[3]}, ID: {j[0]}){Colors.RESET}")
                    return j[0]
                print(f"{Colors.RED}Jugador con ID {entrada} no encontrado.{Colors.RESET}")
                return None
            
            norm_q = self._normalizar_texto(entrada)
            q_words = norm_q.split()
            
            jugadores = cursor.execute('SELECT id, nombre, apellidos, elo FROM jugadores ORDER BY elo DESC').fetchall()
            matches = []
            for jid, nom, ape, elo in jugadores:
                nom_norm = self._normalizar_texto(nom)
                ape_norm = self._normalizar_texto(ape)
                full_norm = f"{nom_norm} {ape_norm}"
                
                if all(word in full_norm for word in q_words):
                    matches.append((jid, nom, ape, elo))

            if not matches:
                print(f"{Colors.RED}No se encontró ningún jugador con '{entrada}'.{Colors.RESET}")
                return None
            elif len(matches) == 1:
                jid, nom, ape, elo = matches[0]
                print(f"{Colors.GREEN}* Encontrado: {nom} {ape} (ELO: {elo}, ID: {jid}){Colors.RESET}")
                return jid
            else:
                print(f"\n{Colors.YELLOW}Se encontraron varios jugadores coincidentes ({len(matches)}):{Colors.RESET}")
                for i, (jid, nom, ape, elo) in enumerate(matches, 1):
                    print(f" {i}. {nom} {ape} | ELO: {elo} (ID: {jid})")
                try:
                    sel_str = input(f"\nElige el número (1-{len(matches)}, 0 para cancelar): ").strip()
                    if not sel_str or sel_str == "0": return None
                    sel = int(sel_str)
                    if 1 <= sel <= len(matches):
                        elegido = matches[sel - 1]
                        print(f"{Colors.GREEN}* Seleccionado: {elegido[1]} {elegido[2]} (ELO: {elegido[3]}){Colors.RESET}")
                        return elegido[0]
                    print(f"{Colors.RED}Opción fuera de rango.{Colors.RESET}")
                    return None
                except ValueError:
                    print(f"{Colors.RED}Opción no válida.{Colors.RESET}")
                    return None

    def procesar_torneo(self):
        if not self.hay_jugadores():
            print(f"{Colors.YELLOW}No hay jugadores registrados.{Colors.RESET}")
            return
        
        print(f"\n{Colors.YELLOW}=== PROCESAR TORNEO ==={Colors.RESET}")
        nombre_torneo = input("Nombre del torneo: ").strip()
        if not nombre_torneo:
            print(f"{Colors.RED}Nombre de torneo no puede estar vacío.{Colors.RESET}")
            return

        while True:
            fecha_input = input(f"Fecha del torneo ({Colors.CYAN}YYYY-MM-DD{Colors.RESET}, Enter para hoy): ").strip()
            if not fecha_input:
                fecha_torneo = datetime.now().strftime("%Y-%m-%d")
                break
            try:
                # Validamos que la fecha introducida tiene el formato correcto
                datetime.strptime(fecha_input, "%Y-%m-%d")
                fecha_torneo = fecha_input
                break
            except ValueError:
                print(f"{Colors.RED}Formato de fecha incorrecto. Por favor, usa YYYY-MM-DD.{Colors.RESET}")

        resultados_torneo = []
        while True:
            id_input = input(f"\nJugador a procesar (escribe nombre, apellido o ID | {Colors.GREEN}'fin'{Colors.RESET} para guardar, {Colors.CYAN}'lista'{Colors.RESET} para ver socios, {Colors.RED}'0'{Colors.RESET} para cancelar): ").strip()
            if id_input.lower() == 'fin': break
            if id_input.lower() == 'lista':
                self.listar_jugadores()
                continue
            if id_input == '0':
                print(f"{Colors.RED}Procesamiento de torneo cancelado.{Colors.RESET}")
                return

            jugador_id = self.buscar_jugador(id_input)
            if not jugador_id:
                continue

            if any(r['jugador_id'] == jugador_id for r in resultados_torneo):
                print(f"{Colors.YELLOW}Este jugador ya ha sido añadido a este torneo.{Colors.RESET}")
                continue

            resultado = self._recoger_datos_participacion(jugador_id)
            if resultado:
                resultados_torneo.append(resultado)
                print(f"{Colors.GREEN}* Datos de {resultado['nombre']} {resultado['apellidos']} añadidos ({len(resultados_torneo)} en torneo).{Colors.RESET}")
        
        if not resultados_torneo:
            print(f"{Colors.RED}No se han procesado jugadores. Torneo cancelado.{Colors.RESET}")
            return
            
        confirmacion = input(f"\n{Colors.YELLOW}Se van a guardar los resultados de {len(resultados_torneo)} jugadores para el torneo '{nombre_torneo}'. ¿Confirmar? (s/N): {Colors.RESET}")
        if confirmacion.lower() == 's':
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO torneos (nombre, fecha) VALUES (?, ?)", (nombre_torneo, fecha_torneo))
                torneo_id = cursor.lastrowid
                for res in resultados_torneo:
                    cursor.execute('INSERT INTO participaciones (jugador_id, torneo_id, elo_inicial, elo_rivales_medio, num_partidas, puntos_obtenidos, variacion_elo, k_factor, fecha) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                   (res['jugador_id'], torneo_id, res['elo_inicial'], res['elo_rivales_medio'], res['num_partidas'], res['puntos_obtenidos'], res['variacion_elo'], res['k_factor'], fecha_torneo))
                    cursor.execute('UPDATE jugadores SET elo = ?, num_torneos = num_torneos + 1, fecha_ultimo_torneo = ?, variacion_ultima_lista = variacion_ultima_lista + ? WHERE id = ?',
                                   (res['nuevo_elo'], fecha_torneo, round(res['variacion_elo']), res['jugador_id']))
            print(f"\n{Colors.GREEN}* Torneo '{nombre_torneo}' y todos los resultados guardados exitosamente.{Colors.RESET}")
        else:
            print(f"{Colors.RED}Torneo cancelado. No se ha guardado ningún dato.{Colors.RESET}")
                
    def _recoger_datos_participacion(self, jugador_id: int) -> Optional[dict]:
        with self.get_connection() as conn:
            jugador = conn.cursor().execute('SELECT nombre, apellidos, elo FROM jugadores WHERE id = ?', (jugador_id,)).fetchone()

        if not jugador:
            print(f"{Colors.RED}Jugador no encontrado.{Colors.RESET}")
            return None
        
        nombre, apellidos, elo_actual = jugador
        print(f"\nProcesando: {Colors.YELLOW}{nombre} {apellidos} (ELO actual: {elo_actual}){Colors.RESET}")
        
        try:
            elo_rivales_medio = float(input("ELO medio de los rivales: "))
            while True:
                num_partidas = int(input("Número de partidas (>0): "))
                if num_partidas > 0: break
                print(f"{Colors.RED}El número de partidas debe ser mayor que cero.{Colors.RESET}")
            while True:
                puntos_obtenidos = float(input(f"Puntos obtenidos (0-{num_partidas}): "))
                if 0 <= puntos_obtenidos <= num_partidas: break
                print(f"{Colors.RED}Los puntos deben estar entre 0 y {num_partidas}.{Colors.RESET}")
        except ValueError:
            print(f"{Colors.RED}Valores no válidos. Operación cancelada para este jugador.{Colors.RESET}")
            return None
            
        k, pd = self.determinar_k_factor(), self.calculo_Pd(elo_actual, elo_rivales_medio)
        variacion = self.calculo_variacion_elo(pd * num_partidas, puntos_obtenidos, k)
        
        return {
            "jugador_id": jugador_id, "nombre": nombre, "apellidos": apellidos,
            "elo_inicial": elo_actual, "elo_rivales_medio": elo_rivales_medio,
            "num_partidas": num_partidas, "puntos_obtenidos": puntos_obtenidos, "variacion_elo": variacion,
            "k_factor": k, "nuevo_elo": round(elo_actual + variacion)
        }

    def eliminar_torneo(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            torneos = cursor.execute('SELECT id, nombre, fecha FROM torneos ORDER BY fecha DESC').fetchall()
            if not torneos:
                print(f"\n{Colors.YELLOW}No hay torneos registrados.{Colors.RESET}")
                return
            
            print(f"\n{Colors.BLUE}=== ELIMINAR TORNEO ==={Colors.RESET}")
            for i, (tid, nombre, fecha) in enumerate(torneos, 1):
                print(f"{i}. {nombre} ({fecha})")
            
            try:
                opcion = int(input("\nElige el torneo a eliminar (0 para cancelar): "))
                if opcion == 0: return
                if not (1 <= opcion <= len(torneos)):
                    print(f"{Colors.RED}Opción no válida.{Colors.RESET}")
                    return
                torneo_id, nombre, fecha = torneos[opcion-1]
            except (ValueError, IndexError):
                print(f"{Colors.RED}Opción no válida.{Colors.RESET}")
                return
            
            # Recuperar participaciones para revertir el ELO
            participaciones = cursor.execute(
                'SELECT jugador_id, variacion_elo FROM participaciones WHERE torneo_id = ?', 
                (torneo_id,)
            ).fetchall()
            
            print(f"\n{Colors.RED}¡Atención!{Colors.RESET} Se eliminará el torneo '{nombre}' ({fecha}) "
                  f"y se revertirán {len(participaciones)} participaciones.")
            confirmacion = input(f"{Colors.YELLOW}¿Confirmar? (s/N): {Colors.RESET}")
            if confirmacion.lower() != 's':
                print(f"{Colors.RED}Operación cancelada.{Colors.RESET}")
                return
            
            # Revertir cambios en los jugadores
            for jugador_id, variacion in participaciones:
                cursor.execute(
                    '''UPDATE jugadores 
                       SET elo = elo - ?, num_torneos = num_torneos - 1, 
                           variacion_ultima_lista = variacion_ultima_lista - ? 
                       WHERE id = ?''',
                    (round(variacion), round(variacion), jugador_id)
                )
            
            # Borrar participaciones y torneo
            cursor.execute('DELETE FROM participaciones WHERE torneo_id = ?', (torneo_id,))
            cursor.execute('DELETE FROM torneos WHERE id = ?', (torneo_id,))
            
            # Recalcular fecha_ultimo_torneo para los jugadores afectados
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

            print(f"\n{Colors.GREEN}✓ Torneo '{nombre}' eliminado y ELO revertido.{Colors.RESET}")
    
    def exportar_lista_csv(self):
        if not self.hay_jugadores(): return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            last_list_date = cursor.execute("SELECT fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC LIMIT 1").fetchone()
            fecha_desde = last_list_date[0] if last_list_date else "1970-01-01 00:00:00"
            torneos_computados = cursor.execute("SELECT nombre, fecha FROM torneos WHERE fecha_creacion >= ? ORDER BY fecha ASC", (fecha_desde,)).fetchall()
            jugadores = cursor.execute('SELECT nombre, apellidos, elo, titulo, variacion_ultima_lista, num_torneos, fecha_ultimo_torneo FROM jugadores ORDER BY elo DESC, num_torneos DESC').fetchall()
        
        nombre_archivo = f"lista_elo_blitz_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        try:
            with open(nombre_archivo, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['RANKING', 'NOMBRE', 'APELLIDOS', 'ELO', 'TÍTULO', 'VARIACIÓN', 'TORNEOS', 'ÚLTIMO_TORNEO', 'DÍAS_INACTIVO'])
                for i, (nombre, apellidos, elo, titulo, var_lista, num_torn, fecha_ult) in enumerate(jugadores, 1):
                    writer.writerow([i, nombre, apellidos, elo, titulo, f"{var_lista:+d}", num_torn, fecha_ult or "Nunca", self.calcular_dias_desde_ultimo_torneo(fecha_ult)])
                writer.writerow([])
                writer.writerow(['TORNEOS COMPUTADOS EN ESTA LISTA'])
                if torneos_computados:
                    for nombre, fecha in torneos_computados:
                        writer.writerow([f"({fecha})", nombre])
                else:
                    writer.writerow(["Ninguno"])
            print(f"\n{Colors.GREEN}✓ Lista exportada a: {nombre_archivo}{Colors.RESET}")
        except Exception as e:
            print(f"\n{Colors.RED}Error al exportar: {e}{Colors.RESET}")

    def generar_texto_ranking_accesible(self) -> str:
        """Genera el ranking en texto accesible, optimizado para compartir por WhatsApp y para lectores de pantalla."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            last_list_date = cursor.execute("SELECT fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC LIMIT 1").fetchone()
            fecha_desde = last_list_date[0] if last_list_date else "1970-01-01 00:00:00"
            torneos_computados = cursor.execute("SELECT nombre, fecha FROM torneos WHERE fecha_creacion >= ? ORDER BY fecha ASC", (fecha_desde,)).fetchall()
            jugadores = cursor.execute('SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, num_torneos, fecha_ultimo_torneo FROM jugadores ORDER BY elo DESC, num_torneos DESC').fetchall()
            media_res = cursor.execute("SELECT AVG(elo) FROM jugadores").fetchone()
            media_elo = media_res[0] if media_res and media_res[0] else 0

        hoy = datetime.now()
        fecha_str = hoy.strftime("%d/%m/%Y")

        lineas = []
        lineas.append("🏁 *PORTUGALETEKO XAKE TALDEA*")
        lineas.append("📊 *Ranking Oficial ELO Rápidas*")
        lineas.append(f"📅 *Fecha:* {fecha_str} | *Jugadores:* {len(jugadores)} | *Media ELO:* {media_elo:.1f}")
        lineas.append("")
        lineas.append("🏆 *CLASIFICACIÓN:*")

        for i, (id_j, nombre, apellidos, elo, titulo, var_lista, num_torn, fecha_ult) in enumerate(jugadores, 1):
            tit_str = f" ({titulo})" if titulo else ""
            var_str = f"+{var_lista}" if var_lista > 0 else str(var_lista)
            dias = self.calcular_dias_desde_ultimo_torneo(fecha_ult)
            inact_str = f" [Inactivo: {dias} días]" if dias > 365 else ""
            lineas.append(f"{i}. *{nombre} {apellidos}*{tit_str} — {elo} ELO (Variación: {var_str}){inact_str}")

        lineas.append("")
        lineas.append("📌 *Torneos computados en este ciclo:*")
        if torneos_computados:
            for nombre, fecha in torneos_computados:
                try:
                    f_dt = datetime.strptime(fecha, "%Y-%m-%d")
                    f_formato = f_dt.strftime("%d/%m/%Y")
                except Exception:
                    f_formato = fecha
                lineas.append(f"• {nombre} ({f_formato})")
        else:
            lineas.append("• Ninguno")

        return "\n".join(lineas)

    def exportar_lista_txt(self) -> Optional[str]:
        """Exporta la lista de ELO en formato de texto accesible para WhatsApp y lectores de pantalla."""
        if not self.hay_jugadores(): return None
        texto = self.generar_texto_ranking_accesible()
        nombre_archivo = f"lista_elo_blitz_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        try:
            with open(nombre_archivo, 'w', encoding='utf-8') as f:
                f.write(texto)
            print(f"\n{Colors.GREEN}[OK] Lista exportada en formato accesible (WhatsApp / Lector de pantalla): {nombre_archivo}{Colors.RESET}")
            return nombre_archivo
        except Exception as e:
            print(f"\n{Colors.RED}Error al exportar: {e}{Colors.RESET}")
            return None

    def get_escudo_base64(self) -> str:
        """Devuelve la imagen del escudo codificada en base64 para embeber en documentos HTML autónomos."""
        escudo_path = "EscudoPAPColor_low.jpg"
        if os.path.exists(escudo_path):
            try:
                with open(escudo_path, "rb") as img_f:
                    encoded = base64.b64encode(img_f.read()).decode('utf-8')
                    return f"data:image/jpeg;base64,{encoded}"
            except Exception:
                return ""
        return ""

    def exportar_lista_html(self) -> Optional[str]:
        if not self.hay_jugadores(): return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            last_list_date_result = cursor.execute("SELECT fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC LIMIT 1").fetchone()
            fecha_desde = last_list_date_result[0] if last_list_date_result else "1970-01-01 00:00:00"
            torneos_computados = cursor.execute("SELECT nombre, fecha FROM torneos WHERE fecha_creacion >= ? ORDER BY fecha ASC", (fecha_desde,)).fetchall()
            jugadores = cursor.execute('''
                SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, num_torneos, fecha_ultimo_torneo 
                FROM jugadores ORDER BY elo DESC, num_torneos DESC
            ''').fetchall()
        
        escudo_b64 = self.get_escudo_base64()
        fecha_emision = datetime.now().strftime("%d/%m/%Y")
        hora_emision = datetime.now().strftime("%H:%M")
        nombre_archivo = f"lista_elo_blitz_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.html"

        elo_promedio = round(sum(j[3] for j in jugadores) / len(jugadores), 1) if jugadores else 0
        elo_max = jugadores[0][3] if jugadores else 0
        
        img_tag = f'<img src="{escudo_b64}" alt="Escudo Portugaleteko Xake Taldea" class="escudo-img">' if escudo_b64 else '<div class="escudo-placeholder">♟️</div>'

        filas_jugadores = ""
        for i, (j_id, nombre, apellidos, elo, titulo, var_lista, num_torn, fecha_ult) in enumerate(jugadores, 1):
            dias_inactivo = self.calcular_dias_desde_ultimo_torneo(fecha_ult)
            if var_lista > 0:
                badge_var = f'<span class="badge badge-pos">+{var_lista}</span>'
            elif var_lista < 0:
                badge_var = f'<span class="badge badge-neg">{var_lista}</span>'
            else:
                badge_var = '<span class="badge badge-neutro">0</span>'

            if dias_inactivo == 9999:
                inactivo_txt = '<span class="text-muted">Sin torneos</span>'
            elif dias_inactivo > 365:
                inactivo_txt = f'<span class="badge badge-inactivo-alto">{dias_inactivo} d</span>'
            elif dias_inactivo > 180:
                inactivo_txt = f'<span class="badge badge-inactivo-medio">{dias_inactivo} d</span>'
            else:
                inactivo_txt = f'<span class="text-act">{dias_inactivo} d</span>'

            medalla = ""
            if i == 1: medalla = " 🥇"
            elif i == 2: medalla = " 🥈"
            elif i == 3: medalla = " 🥉"

            filas_jugadores += f"""
            <tr>
                <td class="col-rk"><b>{i}</b>{medalla}</td>
                <td class="col-nombre"><b>{nombre} {apellidos}</b></td>
                <td class="col-elo"><b>{elo}</b></td>
                <td class="col-titulo">{titulo or '-'}</td>
                <td class="col-var">{badge_var}</td>
                <td class="col-torn">{num_torn}</td>
                <td class="col-fecha">{fecha_ult or 'Nunca'}</td>
                <td class="col-inact">{inactivo_txt}</td>
            </tr>"""

        filas_torneos = ""
        if torneos_computados:
            for t_nom, t_fec in torneos_computados:
                filas_torneos += f"<tr><td class='col-t-fec'>{t_fec}</td><td class='col-t-nom'>{t_nom}</td></tr>"
        else:
            filas_torneos = "<tr><td colspan='2' class='text-muted' style='text-align:center;'>No se han registrado nuevos torneos en este ciclo.</td></tr>"

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portugaleteko Xake Taldea - Clasificación Oficial ELO Rápidas</title>
    <style>
        :root {{
            --primary: #1b3a57;
            --primary-light: #2c5282;
            --accent: #d69e2e;
            --bg: #f7fafc;
            --card-bg: #ffffff;
            --text-main: #2d3748;
            --text-muted: #718096;
            --border: #e2e8f0;
            --success: #38a169;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            padding: 25px 15px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1050px;
            margin: 0 auto;
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        .header {{
            background: linear-gradient(135deg, #0d233a 0%, #1b3a57 60%, #285e8e 100%);
            color: white;
            padding: 24px 30px;
            display: flex;
            align-items: center;
            gap: 24px;
            border-bottom: 4px solid var(--accent);
        }}
        .escudo-img {{
            height: 92px;
            width: auto;
            object-fit: contain;
            filter: drop-shadow(0 4px 8px rgba(0,0,0,0.35));
            background: white;
            padding: 4px;
            border-radius: 8px;
        }}
        .header-text h1 {{
            font-size: 24px;
            letter-spacing: 1px;
            margin-bottom: 4px;
            font-weight: 800;
        }}
        .header-text h2 {{
            font-size: 15px;
            color: #e2e8f0;
            font-weight: 400;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}
        .meta-chips {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            font-size: 12px;
        }}
        .chip {{
            background: rgba(255,255,255,0.18);
            padding: 4px 10px;
            border-radius: 20px;
            backdrop-filter: blur(4px);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            padding: 20px 30px 10px 30px;
        }}
        .stat-card {{
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            text-align: center;
        }}
        .stat-title {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }}
        .stat-value {{
            font-size: 22px;
            font-weight: 800;
            color: var(--primary);
            margin-top: 4px;
        }}
        .content-section {{
            padding: 20px 30px 30px 30px;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 2px solid var(--border);
            padding-bottom: 8px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 700;
            color: var(--primary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        table.tabla-ranking {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        table.tabla-ranking th {{
            background: #f1f5f9;
            color: #475569;
            font-weight: 700;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 2px solid var(--border);
            font-size: 11px;
            text-transform: uppercase;
        }}
        table.tabla-ranking td {{
            padding: 10px 12px;
            border-bottom: 1px solid #edf2f7;
            vertical-align: middle;
        }}
        table.tabla-ranking tbody tr:nth-child(even) {{
            background-color: #f8fafc;
        }}
        table.tabla-ranking tbody tr:hover {{
            background-color: #edf2f7;
        }}
        .col-rk {{ text-align: center; width: 55px; }}
        .col-elo {{ color: var(--primary); font-size: 14px; width: 70px; text-align: center; }}
        .col-titulo {{ width: 60px; text-align: center; color: #805ad5; font-weight: 600; }}
        .col-var {{ width: 80px; text-align: center; }}
        .col-torn {{ width: 70px; text-align: center; }}
        .col-fecha {{ width: 105px; text-align: center; font-size: 12px; color: var(--text-muted); }}
        .col-inact {{ width: 95px; text-align: center; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
        }}
        .badge-pos {{ background: #c6f6d5; color: #22543d; }}
        .badge-neg {{ background: #fed7d7; color: #742a2a; }}
        .badge-neutro {{ background: #edf2f7; color: #4a5568; }}
        .badge-inactivo-medio {{ background: #feebc8; color: #7b341e; }}
        .badge-inactivo-alto {{ background: #fed7d7; color: #9b2c2c; }}
        .text-act {{ color: var(--success); font-weight: 600; }}
        .text-muted {{ color: var(--text-muted); font-size: 12px; }}
        .torneos-box {{
            margin-top: 24px;
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
        }}
        .torneos-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .torneos-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
        }}
        .col-t-fec {{ width: 120px; font-weight: 600; color: var(--primary-light); }}
        .footer {{
            background: #edf2f7;
            padding: 16px 30px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .container {{ box-shadow: none; border: none; max-width: 100%; }}
            .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            .stat-card, th {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            {img_tag}
            <div class="header-text">
                <h1>PORTUGALETEKO XAKE TALDEA</h1>
                <h2>CLASIFICACIÓN OFICIAL DE ELO DE RÁPIDAS (K=10)</h2>
                <div class="meta-chips">
                    <span class="chip">📅 Emisión: {fecha_emision} ({hora_emision})</span>
                    <span class="chip">♟️ {len(jugadores)} Socios Clasificados</span>
                    <span class="chip">⚡ {len(torneos_computados)} Torneos en Ciclo</span>
                </div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">Socios Registrados</div>
                <div class="stat-value">{len(jugadores)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">ELO Promedio Club</div>
                <div class="stat-value">{elo_promedio}</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">ELO Máximo Actual</div>
                <div class="stat-value">{elo_max}</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">Torneos en Ciclo</div>
                <div class="stat-value">{len(torneos_computados)}</div>
            </div>
        </div>

        <div class="content-section">
            <div class="section-header">
                <div class="section-title">Ranking Oficial de Socios</div>
            </div>
            <table class="tabla-ranking">
                <thead>
                    <tr>
                        <th class="col-rk">RK</th>
                        <th>Jugador</th>
                        <th class="col-elo">ELO</th>
                        <th class="col-titulo">TÍT.</th>
                        <th class="col-var">VAR.</th>
                        <th class="col-torn">TORN.</th>
                        <th class="col-fecha">ÚLTIMO TORN.</th>
                        <th class="col-inact">INACTIV.</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_jugadores}
                </tbody>
            </table>

            <div class="torneos-box">
                <div class="section-title" style="font-size: 14px; margin-bottom: 10px;">Torneos Computados en esta Lista</div>
                <table class="torneos-table">
                    <tbody>
                        {filas_torneos}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            Portugaleteko Xake Taldea • Sistema de Control ELO de Rápidas FIDE (K=10) • Documento oficial generado automáticamente
        </div>
    </div>
</body>
</html>"""

        try:
            with open(nombre_archivo, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"\n{Colors.GREEN}* Lista HTML oficial exportada a: {nombre_archivo}{Colors.RESET}")
            return nombre_archivo
        except Exception as e:
            print(f"\n{Colors.RED}Error al exportar a HTML: {e}{Colors.RESET}")
            return None

    def exportar_ficha_html(self, jugador_id: int) -> Optional[str]:
        """Genera un informe HTML oficial e imprimible de la ficha de un jugador con el escudo del club."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugador = cursor.execute('''
                SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, 
                       num_torneos, fecha_ultimo_torneo, fecha_creacion 
                FROM jugadores WHERE id = ?
            ''', (jugador_id,)).fetchone()

            if not jugador: return None
            j_id, nombre, apellidos, elo_actual, titulo, var_lista, num_torn, fecha_ult, fecha_creacion = jugador

            ranking_list = cursor.execute('SELECT id FROM jugadores ORDER BY elo DESC, num_torneos DESC').fetchall()
            ranking_pos = next((i for i, (jid,) in enumerate(ranking_list, 1) if jid == j_id), len(ranking_list))
            total_jugadores = len(ranking_list)

            participaciones = cursor.execute('''
                SELECT p.id, t.fecha, t.nombre, p.elo_inicial, p.elo_rivales_medio, 
                       p.num_partidas, p.puntos_obtenidos, p.variacion_elo, p.k_factor
                FROM participaciones p
                JOIN torneos t ON p.torneo_id = t.id
                WHERE p.jugador_id = ?
                ORDER BY t.fecha ASC, p.id ASC
            ''', (j_id,)).fetchall()

        escudo_b64 = self.get_escudo_base64()
        img_tag = f'<img src="{escudo_b64}" alt="Escudo Club" class="escudo-img">' if escudo_b64 else ''

        if participaciones:
            puntos_elo = [(participaciones[0][1], f"Inicio ({participaciones[0][2]})", participaciones[0][3])]
            for pid, t_fecha, t_nombre, elo_ini, r_med, n_part, pts, var, k in participaciones:
                nuevo_elo = round(elo_ini + var)
                puntos_elo.append((t_fecha, t_nombre, nuevo_elo))
            
            peak_fecha, peak_torneo, peak_elo = max(puntos_elo, key=lambda x: x[2])
            min_fecha, min_torneo, min_elo = min(puntos_elo, key=lambda x: x[2])
            perfs = [(p, self.calcular_performance(p[4], p[6], p[5])) for p in participaciones]
            best_part, best_perf = max(perfs, key=lambda x: x[1])
            max_gain_part = max(participaciones, key=lambda p: p[7])
            max_loss_part = min(participaciones, key=lambda p: p[7])

            tot_partidas = sum(p[5] for p in participaciones)
            tot_puntos = sum(p[6] for p in participaciones)
            efectividad = round(tot_puntos / tot_partidas * 100, 1) if tot_partidas > 0 else 0
            elo_rivales_ponderado = round(sum(p[4] * p[5] for p in participaciones) / tot_partidas, 1) if tot_partidas > 0 else 0
            balance_elo_total = round(sum(p[7] for p in participaciones), 1)

            filas_part = ""
            for i, (pid, t_fec, t_nom, elo_ini, r_med, n_part, pts, var, k) in enumerate(participaciones, 1):
                p_perf = self.calcular_performance(r_med, pts, n_part)
                var_badge = f'<span class="badge badge-pos">+{var:.1f}</span>' if var > 0 else f'<span class="badge badge-neg">{var:.1f}</span>' if var < 0 else '<span class="badge badge-neutro">0.0</span>'
                pts_str = f"{int(pts) if pts.is_integer() else pts}/{n_part}"
                filas_part += f"""
                <tr>
                    <td style="text-align:center;">{i}</td>
                    <td>{t_fec}</td>
                    <td><b>{t_nom}</b></td>
                    <td style="text-align:center;">{elo_ini}</td>
                    <td style="text-align:center;">{r_med:.1f}</td>
                    <td style="text-align:center;"><b>{pts_str}</b></td>
                    <td style="text-align:center; color:#2b6cb0;"><b>{p_perf}</b></td>
                    <td style="text-align:center;">{var_badge}</td>
                    <td style="text-align:center; font-weight:bold;">{round(elo_ini + var)}</td>
                </tr>"""
        else:
            peak_elo, peak_torneo, peak_fecha = elo_actual, "Sin torneos", "-"
            min_elo, min_torneo, min_fecha = elo_actual, "Sin torneos", "-"
            best_perf = "-"
            tot_partidas, tot_puntos, efectividad, elo_rivales_ponderado, balance_elo_total = 0, 0, 0, 0, 0
            filas_part = "<tr><td colspan='9' style='text-align:center; padding:20px; color:#718096;'>El jugador no tiene torneos registrados todavía.</td></tr>"

        nombre_archivo = f"ficha_jugador_{j_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Ficha de Jugador - {nombre} {apellidos} | Portugaleteko Xake Taldea</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:#f7fafc; color:#2d3748; padding:25px 15px; margin:0; }}
        .container {{ max-width: 950px; margin:0 auto; background:#fff; border-radius:12px; box-shadow:0 4px 20px rgba(0,0,0,0.08); overflow:hidden; border:1px solid #e2e8f0; }}
        .header {{ background:linear-gradient(135deg, #0d233a 0%, #1b3a57 60%, #285e8e 100%); color:#fff; padding:24px 30px; display:flex; align-items:center; gap:20px; border-bottom:4px solid #d69e2e; }}
        .escudo-img {{ height:85px; width:auto; background:#fff; padding:4px; border-radius:8px; filter:drop-shadow(0 4px 6px rgba(0,0,0,0.3)); }}
        .header-text h1 {{ font-size:22px; margin:0 0 4px 0; }}
        .header-text h2 {{ font-size:15px; color:#e2e8f0; font-weight:normal; margin:0; }}
        .grid-4 {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:14px; padding:20px 30px; }}
        .card {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px; text-align:center; }}
        .card-title {{ font-size:11px; font-weight:700; color:#718096; text-transform:uppercase; }}
        .card-val {{ font-size:24px; font-weight:800; color:#1b3a57; margin-top:4px; }}
        .content {{ padding:0 30px 30px 30px; }}
        .section-title {{ font-size:15px; font-weight:700; color:#1b3a57; text-transform:uppercase; margin-bottom:12px; border-bottom:2px solid #e2e8f0; padding-bottom:6px; }}
        table {{ width:100%; border-collapse:collapse; font-size:13px; }}
        th {{ background:#f1f5f9; color:#475569; font-weight:700; text-align:left; padding:10px 8px; font-size:11px; text-transform:uppercase; border-bottom:2px solid #e2e8f0; }}
        td {{ padding:9px 8px; border-bottom:1px solid #edf2f7; }}
        tr:nth-child(even) {{ background:#f8fafc; }}
        .badge {{ display:inline-block; padding:2px 7px; border-radius:10px; font-size:11px; font-weight:700; }}
        .badge-pos {{ background:#c6f6d5; color:#22543d; }}
        .badge-neg {{ background:#fed7d7; color:#742a2a; }}
        .badge-neutro {{ background:#edf2f7; color:#4a5568; }}
        .footer {{ background:#edf2f7; padding:14px; text-align:center; font-size:12px; color:#718096; }}
        @media print {{ body {{ background:#fff; padding:0; }} .container {{ border:none; box-shadow:none; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            {img_tag}
            <div class="header-text">
                <h1>{nombre} {apellidos}</h1>
                <h2>Ficha Oficial de Socio • Portugaleteko Xake Taldea</h2>
                <div style="font-size:12px; margin-top:8px; opacity:0.9;">
                    <span>ID: {j_id}</span> | <span>Título: {titulo or 'Ninguno'}</span> | <span>Ranking Club: #{ranking_pos} de {total_jugadores}</span>
                </div>
            </div>
        </div>
        <div class="grid-4">
            <div class="card"><div class="card-title">ELO Actual</div><div class="card-val">{elo_actual}</div></div>
            <div class="card"><div class="card-title">Pico Máximo (Peak)</div><div class="card-val" style="color:#b7791f;">{peak_elo}</div></div>
            <div class="card"><div class="card-title">Mejor Performance</div><div class="card-val" style="color:#2f855a;">{best_perf}</div></div>
            <div class="card"><div class="card-title">Efectividad Global</div><div class="card-val" style="color:#2b6cb0;">{efectividad}%</div></div>
        </div>
        <div class="content">
            <div class="section-title">Trayectoria Torneo a Torneo ({len(participaciones)} torneos disputados)</div>
            <table>
                <thead>
                    <tr>
                        <th style="text-align:center;">#</th>
                        <th>Fecha</th>
                        <th>Torneo</th>
                        <th style="text-align:center;">ELO Ini</th>
                        <th style="text-align:center;">Rc Riv.</th>
                        <th style="text-align:center;">Puntos</th>
                        <th style="text-align:center;">Perf.</th>
                        <th style="text-align:center;">Var.</th>
                        <th style="text-align:center;">Nuevo ELO</th>
                    </tr>
                </thead>
                <tbody>{filas_part}</tbody>
            </table>
        </div>
        <div class="footer">Portugaleteko Xake Taldea • Documento oficial de socio generado automáticamente</div>
    </div>
</body>
</html>"""
        try:
            with open(nombre_archivo, "w", encoding="utf-8") as f:
                f.write(html)
            return nombre_archivo
        except Exception:
            return None

    def exportar_web_interactiva(self, ruta_destino: str = "index.html") -> Optional[str]:
        """Genera un portal web interactivo (index.html) autónomo con ranking y fichas individuales."""
        try:
            from web_generator import generar_html_web_interactiva
            res = generar_html_web_interactiva(self.db_name, ruta_destino)
            print(f"\n{Colors.GREEN}[OK] Web interactiva generada con exito en: {res}{Colors.RESET}")
            return res
        except Exception as e:
            print(f"\n{Colors.RED}Error al generar la web interactiva: {e}{Colors.RESET}")
            return None

    def _opcion_exportar_web(self):
        """Opcion del menu para generar y opcionalmente abrir la web interactiva."""
        ruta = self.exportar_web_interactiva("index.html")
        if ruta:
            abrir = input(f"\n{Colors.YELLOW}¿Deseas abrir la web en tu navegador predeterminado ahora? (S/n): {Colors.RESET}").strip().lower()
            if abrir in ('', 's', 'si', 'y'):
                try:
                    import webbrowser
                    webbrowser.open(os.path.abspath(ruta))
                except Exception as e:
                    print(f"{Colors.RED}No se pudo abrir automaticamente el navegador: {e}{Colors.RESET}")

    def generar_nueva_lista(self):
        if not self.hay_jugadores(): return
        confirmacion = input(f"\n{Colors.YELLOW}¿Confirmar la generación de una nueva lista? (Esto guardará el ranking actual y reseteará las variaciones): (s/N): {Colors.RESET}")
        if confirmacion.lower() != 's':
            print(f"{Colors.RED}Operación cancelada.{Colors.RESET}")
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
        print(f"{Colors.GREEN}✓ Nueva lista generada y ranking histórico guardado.{Colors.RESET}")

    def ver_historial_torneo(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            torneos = cursor.execute('SELECT id, nombre, fecha FROM torneos ORDER BY fecha DESC').fetchall()
            if not torneos:
                print(f"\n{Colors.YELLOW}No hay torneos registrados.{Colors.RESET}")
                return
            
            print(f"\n{Colors.BLUE}=== HISTORIAL DETALLADO DE TORNEOS ==={Colors.RESET}")
            for torneo_id, torneo_nombre, torneo_fecha in torneos:
                print(f"\n{Colors.CYAN}{torneo_nombre} ({torneo_fecha}){Colors.RESET}")
                print(f"{Colors.YELLOW}{'JUGADOR':<25} | {'PUNTOS':<8} | {'VARIACIÓN ELO':<15} | {'PERFORMANCE':<11}{Colors.RESET}")
                print("-" * 65)
                participaciones = cursor.execute('SELECT j.nombre, j.apellidos, p.puntos_obtenidos, p.num_partidas, p.variacion_elo, p.elo_rivales_medio FROM participaciones p JOIN jugadores j ON p.jugador_id = j.id WHERE p.torneo_id = ? ORDER BY p.puntos_obtenidos DESC', (torneo_id,)).fetchall()
                if not participaciones:
                    print("  - Sin participantes registrados.")
                else:
                    for nombre, apellidos, puntos, partidas, variacion, elo_rival_medio in participaciones:
                        var_color = Colors.GREEN if variacion > 0 else Colors.RED if variacion < 0 else Colors.RESET
                        puntos_str = f"{int(puntos) if puntos == int(puntos) else puntos}/{int(partidas)}"
                        var_str = f"{var_color}{variacion:+.1f}{Colors.RESET}"
                        performance = self.calcular_performance(elo_rival_medio, puntos, partidas)
                        print(f"{f'{nombre} {apellidos}':<25} | {puntos_str:<8} | {var_str:<25} | {Colors.MAGENTA}{performance}{Colors.RESET}")

    def eliminar_jugadores_muy_inactivos(self):
        DIAS_MAX = 1000
        fecha_limite = (datetime.now() - timedelta(days=DIAS_MAX)).strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugadores = cursor.execute('SELECT id, nombre, apellidos, fecha_ultimo_torneo FROM jugadores WHERE fecha_ultimo_torneo < ?', (fecha_limite,)).fetchall()
            if not jugadores:
                print(f"\n{Colors.GREEN}No se encontraron jugadores con más de {DIAS_MAX} días de inactividad.{Colors.RESET}")
                return
            
            print(f"\n{Colors.RED}Los siguientes jugadores serán ELIMINADOS por inactividad:{Colors.RESET}")
            for id_j, nombre, apellidos, fecha in jugadores:
                print(f"  - ID: {id_j}, {nombre} {apellidos} (Últ. torneo: {fecha})")
            
            confirmacion = input(f"\n{Colors.RED}Esta acción es IRREVERSIBLE. Escribe 'eliminar' para confirmar: {Colors.RESET}")
            if confirmacion.lower() == 'eliminar':
                ids_a_eliminar = [j[0] for j in jugadores]
                for jugador_id in ids_a_eliminar:
                    cursor.execute("DELETE FROM participaciones WHERE jugador_id = ?", (jugador_id,))
                    cursor.execute("DELETE FROM jugadores WHERE id = ?", (jugador_id,))
                print(f"\n{Colors.GREEN}✓ Se han eliminado {len(jugadores)} jugadores.{Colors.RESET}")
            else:
                print(f"{Colors.RED}Operación cancelada.{Colors.RESET}")

    def aplicar_regulacion_anual_elo(self):
        print(f"\n{Colors.YELLOW}=== REGULACIÓN ANUAL DE ELO ==={Colors.RESET}")
        hoy = datetime.now()
        fecha_actualizacion = hoy.replace(month=9, day=1).strftime("%Y-%m-%d")
        fecha_limite = (hoy - timedelta(days=365)).strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugadores = cursor.execute('SELECT id, nombre, apellidos, elo FROM jugadores WHERE elo > 2000 AND fecha_ultimo_torneo < ?', (fecha_limite,)).fetchall()
            if not jugadores:
                print(f"\n{Colors.GREEN}No hay jugadores que cumplan los requisitos para la regulación.{Colors.RESET}")
                return
            
            print(f"\n{Colors.YELLOW}Se aplicará la siguiente regulación de ELO (actualizando fecha a {fecha_actualizacion}):{Colors.RESET}")
            for id_j, nombre, apellidos, elo in jugadores:
                print(f"  - {nombre} {apellidos}: {elo} -> {Colors.MAGENTA}{max(2000, elo - 50)}{Colors.RESET}")
            
            confirmacion = input(f"\n{Colors.YELLOW}¿Confirmar la aplicación de estos cambios? (s/N): {Colors.RESET}")
            if confirmacion.lower() == 's':
                for id_j, _, _, elo in jugadores:
                    nuevo_elo = max(2000, elo - 50)
                    reduccion = elo - nuevo_elo
                    cursor.execute('''
                        UPDATE jugadores 
                        SET elo = ?, variacion_ultima_lista = variacion_ultima_lista - ?, fecha_ultimo_torneo = ? 
                        WHERE id = ?
                    ''', (nuevo_elo, reduccion, fecha_actualizacion, id_j))
                print(f"\n{Colors.GREEN}✓ Se ha aplicado la regulación a {len(jugadores)} jugadores.{Colors.RESET}")
            else:
                print(f"{Colors.RED}Operación cancelada.{Colors.RESET}")

    def ver_listas_anteriores(self):
        print(f"\n{Colors.BLUE}=== HISTORIAL DE LISTAS GENERADAS ==={Colors.RESET}")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            listas = cursor.execute("SELECT id, fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC").fetchall()
            if not listas:
                print(f"\n{Colors.YELLOW}No se ha generado ninguna lista todavía.{Colors.RESET}")
                return
            
            print("Selecciona una lista para ver su ranking y torneos del ciclo:")
            for i, (id_lista, fecha) in enumerate(listas):
                print(f" {i+1}. Lista del {self.utc_to_local_str(fecha)}")
            
            try:
                opcion_input = input("\nElige una opción (0 para cancelar): ").strip()
                if not opcion_input or opcion_input == "0": return
                opcion = int(opcion_input)
                if not (1 <= opcion <= len(listas)):
                    print(f"{Colors.RED}Opción no válida.{Colors.RESET}")
                    return
            except ValueError:
                print(f"{Colors.RED}Opción no válida.{Colors.RESET}")
                return
                
            lista_seleccionada_id, fecha_fin_ciclo = listas[opcion-1]
            fecha_fin_ciclo_local = self.utc_to_local_str(fecha_fin_ciclo)
            print(f"\n{Colors.CYAN}--- RANKING ELO DE LA LISTA DEL {fecha_fin_ciclo_local} ---{Colors.RESET}")
            print(f"{Colors.YELLOW}{'RANK':<5} {'NOMBRE':<35} {'ELO':<6} {'TORNEOS JUGADOS'}{Colors.RESET}")
            print("-" * 65)
            jugadores_historial = cursor.execute("SELECT nombre, apellidos, elo, num_torneos FROM historial_jugadores_lista WHERE lista_id = ? ORDER BY elo DESC", (lista_seleccionada_id,)).fetchall()
            if not jugadores_historial:
                print("No hay datos de jugadores guardados para esta lista.")
            else:
                for i, (nombre, apellidos, elo, num_torneos) in enumerate(jugadores_historial, 1):
                    print(f"{i:<5} {f'{nombre} {apellidos}':<35} {elo:<6} {num_torneos}")
            
            fecha_inicio_ciclo = listas[opcion][1] if opcion < len(listas) else "1970-01-01 00:00:00"
            fecha_inicio_ciclo_local = self.utc_to_local_str(fecha_inicio_ciclo)
            print(f"\n{Colors.CYAN}--- TORNEOS COMPUTADOS EN ESE CICLO ---{Colors.RESET}")
            print(f"(Torneos jugados entre {fecha_inicio_ciclo_local} y {fecha_fin_ciclo_local})")
            print("-" * 65)
            torneos_ciclo = cursor.execute("SELECT nombre, fecha FROM torneos WHERE fecha_creacion > ? AND fecha_creacion <= ? ORDER BY fecha ASC", (fecha_inicio_ciclo, fecha_fin_ciclo)).fetchall()
            if not torneos_ciclo:
                print("  - No se computaron torneos en este ciclo.")
            else:
                for nombre, fecha in torneos_ciclo:
                    print(f"  - {nombre} ({fecha})")

    def ver_ficha_jugador(self):
        """Muestra una ficha detallada del jugador con récords, estadísticas globales y trayectoria."""
        if not self.hay_jugadores():
            print(f"\n{Colors.YELLOW}No hay jugadores registrados.{Colors.RESET}")
            return
        
        print(f"\n{Colors.BLUE}=== FICHA DETALLADA Y ESTADÍSTICAS DEL JUGADOR ==={Colors.RESET}")
        busqueda = input("Introduce ID o nombre/apellidos (Enter o 'lista' para ver socios, 0 para cancelar): ").strip()
        if busqueda == "0":
            return
        if not busqueda or busqueda.lower() == "lista":
            self.listar_jugadores()
            busqueda = input("\nIntroduce ID o nombre/apellidos del jugador (0 para cancelar): ").strip()
            if not busqueda or busqueda == "0":
                return

        jugador_id = self.buscar_jugador(busqueda)
        if not jugador_id:
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            jugador = cursor.execute('''
                SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, 
                       num_torneos, fecha_ultimo_torneo, fecha_creacion 
                FROM jugadores WHERE id = ?
            ''', (jugador_id,)).fetchone()
            
            if not jugador:
                print(f"{Colors.RED}Jugador no encontrado.{Colors.RESET}")
                return
            
            j_id, nombre, apellidos, elo_actual, titulo, var_lista, num_torn, fecha_ult, fecha_creacion = jugador
            nombre_completo = f"{nombre} {apellidos}"
            
            ranking_list = cursor.execute('SELECT id FROM jugadores ORDER BY elo DESC, num_torneos DESC').fetchall()
            ranking_pos = next((i for i, (jid,) in enumerate(ranking_list, 1) if jid == j_id), len(ranking_list))
            total_jugadores = len(ranking_list)
            
            participaciones = cursor.execute('''
                SELECT p.id, t.fecha, t.nombre, p.elo_inicial, p.elo_rivales_medio, 
                       p.num_partidas, p.puntos_obtenidos, p.variacion_elo, p.k_factor
                FROM participaciones p
                JOIN torneos t ON p.torneo_id = t.id
                WHERE p.jugador_id = ?
                ORDER BY t.fecha ASC, p.id ASC
            ''', (j_id,)).fetchall()
            
            dias_inactivo = self.calcular_dias_desde_ultimo_torneo(fecha_ult)
            if not fecha_ult:
                estado_str = "Sin torneos disputados"
                estado_color = Colors.RESET
            elif dias_inactivo <= 180:
                estado_str = f"Activo (último torneo: {fecha_ult}, hace {dias_inactivo} días)"
                estado_color = Colors.GREEN
            elif dias_inactivo <= 365:
                estado_str = f"Alerta (último torneo: {fecha_ult}, hace {dias_inactivo} días)"
                estado_color = Colors.YELLOW
            else:
                estado_str = f"Inactivo (último torneo: {fecha_ult}, hace {dias_inactivo} días)"
                estado_color = Colors.RED
            
            var_color = Colors.GREEN if var_lista > 0 else Colors.RED if var_lista < 0 else Colors.RESET
            var_str = f"{var_color}{var_lista:+d}{Colors.RESET}"
            
            SEP = "=" * 90
            SUBSEP = "-" * 90
            
            print(f"\n{Colors.CYAN}{SEP}{Colors.RESET}")
            print(f"{Colors.YELLOW}{f'FICHA DEL JUGADOR: {nombre_completo.upper()}'.center(90)}{Colors.RESET}")
            print(f"{Colors.CYAN}{SEP}{Colors.RESET}")
            print(f"  * ID: {Colors.CYAN}{j_id}{Colors.RESET}                      * Título: {Colors.MAGENTA}{titulo or 'Ninguno'}{Colors.RESET}")
            print(f"  * ELO Actual: {Colors.MAGENTA}{elo_actual}{Colors.RESET}              * Ranking Club: {Colors.YELLOW}#{ranking_pos}{Colors.RESET} de {total_jugadores} jugadores")
            alta_str = self.utc_to_local_str(fecha_creacion)[:10] if fecha_creacion else 'Desconocida'
            print(f"  * Variación última lista: {var_str}      * Alta en club: {alta_str}")
            print(f"  * Estado de actividad: {estado_color}{estado_str}{Colors.RESET}")
            
            if not participaciones:
                print(f"\n{Colors.CYAN}{SUBSEP}{Colors.RESET}")
                print(f"{Colors.YELLOW}  Este jugador aún no tiene torneos registrados en el sistema.{Colors.RESET}")
                print(f"{Colors.CYAN}{SEP}{Colors.RESET}")
                return
            
            puntos_elo = [(participaciones[0][1], f"Inicio (previo a {participaciones[0][2]})", participaciones[0][3])]
            for pid, t_fecha, t_nombre, elo_ini, r_med, n_part, pts, var, k in participaciones:
                nuevo_elo = round(elo_ini + var)
                puntos_elo.append((t_fecha, t_nombre, nuevo_elo))
            
            peak_fecha, peak_torneo, peak_elo = max(puntos_elo, key=lambda x: x[2])
            min_fecha, min_torneo, min_elo = min(puntos_elo, key=lambda x: x[2])
            
            perfs = [(p, self.calcular_performance(p[4], p[6], p[5])) for p in participaciones]
            best_part, best_perf = max(perfs, key=lambda x: x[1])
            
            max_gain_part = max(participaciones, key=lambda p: p[7])
            max_loss_part = min(participaciones, key=lambda p: p[7])
            
            tot_partidas = sum(p[5] for p in participaciones)
            tot_puntos = sum(p[6] for p in participaciones)
            efectividad = (tot_puntos / tot_partidas * 100) if tot_partidas > 0 else 0
            elo_rivales_ponderado = (sum(p[4] * p[5] for p in participaciones) / tot_partidas) if tot_partidas > 0 else 0
            balance_elo_total = sum(p[7] for p in participaciones)
            bal_color = Colors.GREEN if balance_elo_total > 0 else Colors.RED if balance_elo_total < 0 else Colors.RESET
            
            print(f"\n{Colors.CYAN}{SUBSEP}{Colors.RESET}")
            print(f"{Colors.BLUE}{'RÉCORDS HISTÓRICOS EN EL CLUB'.center(90)}{Colors.RESET}")
            print(f"{Colors.CYAN}{SUBSEP}{Colors.RESET}")
            print(f"  * {Colors.YELLOW}Pico Máximo de ELO (Peak):{Colors.RESET} {Colors.MAGENTA}{peak_elo}{Colors.RESET} pts  ({peak_torneo[:42]}, {peak_fecha})")
            print(f"  * {Colors.CYAN}Suelo Mínimo de ELO:{Colors.RESET}       {Colors.MAGENTA}{min_elo}{Colors.RESET} pts  ({min_torneo[:42]}, {min_fecha})")
            print(f"  * {Colors.GREEN}Mejor Performance (Rp):{Colors.RESET}    {Colors.MAGENTA}{best_perf}{Colors.RESET} pts  ({best_part[2][:35]}, {best_part[6]:.1f}/{best_part[5]} pts)")
            gain_sign = "+" if max_gain_part[7] >= 0 else ""
            loss_sign = "+" if max_loss_part[7] >= 0 else ""
            print(f"  * Mayor ganancia en un torneo: {Colors.GREEN}{gain_sign}{max_gain_part[7]:.1f} pts{Colors.RESET} ({max_gain_part[2][:45]})")
            print(f"  * Mayor pérdida en un torneo:  {Colors.RED}{loss_sign}{max_loss_part[7]:.1f} pts{Colors.RESET} ({max_loss_part[2][:45]})")
            
            print(f"\n{Colors.CYAN}{SUBSEP}{Colors.RESET}")
            print(f"{Colors.BLUE}{'ESTADÍSTICAS GLOBALES DE RENDIMIENTO'.center(90)}{Colors.RESET}")
            print(f"{Colors.CYAN}{SUBSEP}{Colors.RESET}")
            print(f"  - Torneos disputados:   {len(participaciones)} torneos")
            print(f"  - Partidas disputadas:  {tot_partidas} partidas")
            print(f"  - Puntos obtenidos:     {tot_puntos:.1f} / {tot_partidas} ({efectividad:.1f}% de efectividad)")
            print(f"  - ELO medio de rivales: {elo_rivales_ponderado:.1f}")
            print(f"  - Balance neto de ELO:  {bal_color}{balance_elo_total:+.1f} pts{Colors.RESET} (desde el primer torneo registrado)")
            
            print(f"\n{Colors.CYAN}{SUBSEP}{Colors.RESET}")
            print(f"{Colors.BLUE}{'TRAYECTORIA TORNEO A TORNEO'.center(90)}{Colors.RESET}")
            print(f"{Colors.CYAN}{SUBSEP}{Colors.RESET}")
            print(f"{Colors.CYAN}{'#':<3} {'FECHA':<11} {'TORNEO':<32} {'ELO.I':<6} {'RIV.M':<7} {'PTS':<7} {'PERF':<6} {'VAR':<8} {'N.ELO':<6}{Colors.RESET}")
            print(f"{Colors.CYAN}{'-'*90}{Colors.RESET}")
            
            for i, (pid, t_fecha, t_nombre, elo_ini, r_med, n_part, pts, var, k) in enumerate(participaciones, 1):
                perf_i = self.calcular_performance(r_med, pts, n_part)
                var_col = Colors.GREEN if var > 0 else Colors.RED if var < 0 else Colors.RESET
                pts_str = f"{int(pts) if pts == int(pts) else pts}/{int(n_part)}"
                nuevo_i = round(elo_ini + var)
                nombre_t_trunc = (t_nombre[:29] + '..') if len(t_nombre) > 31 else t_nombre
                print(f"{i:<3} {t_fecha:<11} {nombre_t_trunc:<32} {elo_ini:<6} {r_med:<7.1f} {pts_str:<7} {perf_i:<6} {var_col}{var:+.1f}{Colors.RESET}   {Colors.MAGENTA}{nuevo_i:<6}{Colors.RESET}")
            
            print(f"{Colors.CYAN}{SEP}{Colors.RESET}")
            
            exportar = input(f"\n{Colors.YELLOW}¿Deseas exportar esta ficha a un archivo de texto? (s/N): {Colors.RESET}").strip().lower()
            if exportar == 's':
                clean_name = "".join(c for c in f"{nombre}_{apellidos}".replace(" ", "_") if c.isalnum() or c in ('_', '-'))
                filename = f"ficha_{clean_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("=" * 90 + "\n")
                        f.write(f"FICHA DEL JUGADOR: {nombre_completo.upper()}\n")
                        f.write("=" * 90 + "\n")
                        f.write(f"  * ID: {j_id}                      * Título: {titulo or 'Ninguno'}\n")
                        f.write(f"  * ELO Actual: {elo_actual}              * Ranking Club: #{ranking_pos} de {total_jugadores}\n")
                        f.write(f"  * Variación última lista: {var_lista:+d}      * Alta: {alta_str}\n")
                        f.write(f"  * Estado: {estado_str}\n\n")
                        f.write("-" * 90 + "\n")
                        f.write("RÉCORDS HISTÓRICOS EN EL CLUB\n")
                        f.write("-" * 90 + "\n")
                        f.write(f"  * Pico Máximo de ELO (Peak): {peak_elo} pts ({peak_torneo}, {peak_fecha})\n")
                        f.write(f"  * Suelo Mínimo de ELO:       {min_elo} pts ({min_torneo}, {min_fecha})\n")
                        f.write(f"  * Mejor Performance (Rp):    {best_perf} pts ({best_part[2]}, {best_part[6]:.1f}/{best_part[5]} pts)\n")
                        f.write(f"  * Mayor ganancia en un torneo: {gain_sign}{max_gain_part[7]:.1f} pts ({max_gain_part[2]})\n")
                        f.write(f"  * Mayor pérdida en un torneo:  {loss_sign}{max_loss_part[7]:.1f} pts ({max_loss_part[2]})\n\n")
                        f.write("-" * 90 + "\n")
                        f.write("ESTADÍSTICAS GLOBALES\n")
                        f.write("-" * 90 + "\n")
                        f.write(f"  - Torneos disputados:   {len(participaciones)}\n")
                        f.write(f"  - Partidas disputadas:  {tot_partidas}\n")
                        f.write(f"  - Puntos obtenidos:     {tot_puntos:.1f} / {tot_partidas} ({efectividad:.1f}% efectividad)\n")
                        f.write(f"  - ELO medio de rivales: {elo_rivales_ponderado:.1f}\n")
                        f.write(f"  - Balance neto de ELO:  {balance_elo_total:+.1f} pts\n\n")
                        f.write("-" * 90 + "\n")
                        f.write("TRAYECTORIA TORNEO A TORNEO\n")
                        f.write("-" * 90 + "\n")
                        f.write(f"{'#':<3} {'FECHA':<11} {'TORNEO':<36} {'ELO.I':<7} {'RIV.M':<7} {'PTS':<8} {'PERF':<6} {'VAR':<8} {'N.ELO':<6}\n")
                        f.write("-" * 90 + "\n")
                        for i, (pid, t_fecha, t_nombre, elo_ini, r_med, n_part, pts, var, k) in enumerate(participaciones, 1):
                            perf_i = self.calcular_performance(r_med, pts, n_part)
                            pts_str = f"{int(pts) if pts == int(pts) else pts}/{int(n_part)}"
                            nuevo_i = round(elo_ini + var)
                            t_n_trunc = (t_nombre[:33] + '..') if len(t_nombre) > 35 else t_nombre
                            f.write(f"{i:<3} {t_fecha:<11} {t_n_trunc:<36} {elo_ini:<7} {r_med:<7.1f} {pts_str:<8} {perf_i:<6} {var:+7.1f}  {nuevo_i:<6}\n")
                        f.write("=" * 90 + "\n")
                    print(f"\n{Colors.GREEN}✓ Ficha exportada correctamente a: {filename}{Colors.RESET}")
                except Exception as e:
                    print(f"\n{Colors.RED}Error al exportar ficha: {e}{Colors.RESET}")

    def abrir_interfaz_grafica(self):
        """Abre la aplicación de escritorio gráfica moderna."""
        try:
            from elo_club_gui import ELOClubGUI
            print(f"\n{Colors.GREEN}Iniciando interfaz gráfica de escritorio...{Colors.RESET}")
            app = ELOClubGUI(db_name=self.db_name)
            app.mainloop()
        except Exception as e:
            print(f"\n{Colors.RED}Error al abrir la interfaz gráfica: {e}{Colors.RESET}")

    def menu_principal(self):
        """Bucle principal del programa que muestra el menú y gestiona las opciones del usuario."""
        while True:
            self.listar_jugadores()
            print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
            print(f"{Colors.BLUE}{'MENÚ PRINCIPAL'.center(60)}{Colors.RESET}")
            print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
            print(f"{Colors.YELLOW}--- Gestión de Jugadores ---{Colors.RESET}")
            print("1. Crear jugador | 2. Modificar jugador | 3. Eliminar jugador")
            print(f"\n{Colors.YELLOW}--- Torneos y ELO ---{Colors.RESET}")
            print("4. Procesar torneo | 5. Eliminar torneo | 6. Generar nueva lista | 7. Historial torneos")
            print(f"\n{Colors.YELLOW}--- Mantenimiento e Historial ---{Colors.RESET}")
            print("8. Ver listas anteriores | 9. Regulación anual | 10. Purgar inactivos")
            print(f"\n{Colors.YELLOW}--- Estadísticas y Consultas ---{Colors.RESET}")
            print("14. Ficha y estadísticas del jugador")
            print(f"\n{Colors.YELLOW}--- Exportar ---{Colors.RESET}")
            print("11. Exportar a TXT | 12. Exportar a CSV | 13. Exportar a HTML")
            print(f"{Colors.GREEN}16. Generar Web Interactiva (index.html) | Fichas y Ranking online{Colors.RESET}")
            print(f"\n{Colors.YELLOW}--- Modo Visual ---{Colors.RESET}")
            print(f"{Colors.CYAN}15. Abrir Aplicación de Escritorio (Ventana){Colors.RESET}")
            print(f"{Colors.RED}0. Salir{Colors.RESET}")
            print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
            
            opcion = input("Selecciona una opción: ").strip().lower()
            
            opciones = {
                "1": self.crear_jugador, "2": self.modificar_jugador, "3": self.eliminar_jugador,
                "4": self.procesar_torneo, "5": self.eliminar_torneo, "6": self.generar_nueva_lista, 
                "7": self.ver_historial_torneo, "8": self.ver_listas_anteriores, 
                "9": self.aplicar_regulacion_anual_elo, "10": self.eliminar_jugadores_muy_inactivos, 
                "11": self.exportar_lista_txt, "12": self.exportar_lista_csv, "13": self.exportar_lista_html,
                "14": self.ver_ficha_jugador, "f": self.ver_ficha_jugador, "ficha": self.ver_ficha_jugador,
                "15": self.abrir_interfaz_grafica, "gui": self.abrir_interfaz_grafica, "ventana": self.abrir_interfaz_grafica,
                "16": self._opcion_exportar_web, "web": self._opcion_exportar_web,
            }
            
            if opcion == "0":
                print(f"{Colors.CYAN}¡Hasta luego!{Colors.RESET}")
                break
            elif opcion in opciones:
                opciones[opcion]()
                input(f"\n{Colors.YELLOW}Presiona Enter para continuar...{Colors.RESET}")
            else:
                print(f"{Colors.RED}Opción no válida.{Colors.RESET}")


def main():
    """Función principal que inicia la aplicación."""
    import sys
    try:
        if "--gui" in sys.argv:
            from elo_club_gui import ELOClubGUI
            app = ELOClubGUI()
            app.mainloop()
        else:
            elo_app = ELOClub()
            elo_app.menu_principal()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.RED}Programa interrumpido. ¡Hasta luego!{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.RED}Error inesperado: {e}{Colors.RESET}")

# Este es el punto de entrada del script. Si se ejecuta este fichero, se llama a la función main().
if __name__ == "__main__":
    main()