"""
Generador de Portal Web Interactivo para Portugaleteko Xake Taldea.
Genera un único archivo HTML autónomo (index.html) con ranking en tiempo real,
filtros dinámicos, buscador y fichas de historial completas para cada socio.
Zero dependencias externas (funciona 100% offline o alojado en Dropbox / Drive / GitHub Pages).
"""

import os
import sys
import json
import sqlite3
import base64
from datetime import datetime
from typing import Optional


def generar_html_web_interactiva(db_name: str = "elo_club.db", ruta_destino: str = "index.html") -> str:
    """
    Lee la base de datos del club y genera un archivo HTML autónomo con:
    - Escudo del club embebido en base64
    - Ranking actual con buscador en vivo y filtros (Todos, Activos, Inactivos, Podio)
    - Modal/Drawer de Ficha Individual interactiva con:
        - Récords y estadísticas (Peak ELO, mejor performance, efectividad, rivales)
        - Gráfico SVG dinámico de evolución de ELO
        - Tabla completa de trayectoria torneo a torneo
    - Pestaña de Torneos del Ciclo actual
    - Pestaña de Historial de Listas Oficiales
    - Botón de 1-clic para copiar el ranking en formato accesible para WhatsApp
    """
    # 1. Escudo en base64
    escudo_b64 = ""
    escudo_path = "EscudoPAPColor_low.jpg"
    if os.path.exists(escudo_path):
        try:
            with open(escudo_path, "rb") as f:
                escudo_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            escudo_b64 = ""

    # 2. Conexión y extracción de datos
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    last_list_date_res = cursor.execute("SELECT id, fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC LIMIT 1").fetchone()
    fecha_desde = last_list_date_res[1] if last_list_date_res else "1970-01-01 00:00:00"

    torneos_computados = cursor.execute(
        "SELECT id, nombre, fecha FROM torneos WHERE fecha_creacion >= ? ORDER BY fecha ASC", (fecha_desde,)
    ).fetchall()
    total_torneos_hist = cursor.execute("SELECT COUNT(*) FROM torneos").fetchone()[0]

    jugadores_rows = cursor.execute('''
        SELECT id, nombre, apellidos, elo, titulo, variacion_ultima_lista, num_torneos, fecha_ultimo_torneo, fecha_creacion
        FROM jugadores ORDER BY elo DESC, num_torneos DESC
    ''').fetchall()

    hoy = datetime.now()

    delta_lookup = {
        1.0: 800, 0.95: 450, 0.9: 350, 0.85: 290, 0.8: 240, 0.75: 202, 0.7: 166, 0.65: 133, 0.6: 102, 0.55: 72, 
        0.5: 0, 0.45: -72, 0.4: -102, 0.35: -133, 0.3: -166, 0.25: -202, 0.2: -240, 0.15: -290, 0.1: -350, 
        0.05: -450, 0.0: -800
    }
    def calc_perf(r_med, pts, n_part):
        if n_part <= 0: return 0
        p = pts / n_part
        closest_p = min(delta_lookup.keys(), key=lambda x: abs(x - p))
        return round(r_med + delta_lookup[closest_p])

    jugadores_data = []
    for pos, j in enumerate(jugadores_rows, 1):
        jid, nom, ape, elo, tit, var, torn, fec_ult, fec_crea = j

        dias = 9999
        if fec_ult:
            try:
                dias = (hoy - datetime.strptime(fec_ult, "%Y-%m-%d")).days
            except Exception:
                dias = 9999

        parts_rows = cursor.execute('''
            SELECT p.id, t.fecha, t.nombre, p.elo_inicial, p.elo_rivales_medio, 
                   p.num_partidas, p.puntos_obtenidos, p.variacion_elo, p.k_factor
            FROM participaciones p
            JOIN torneos t ON p.torneo_id = t.id
            WHERE p.jugador_id = ?
            ORDER BY t.fecha ASC, p.id ASC
        ''', (jid,)).fetchall()

        trayectoria = []
        puntos_chart = []
        peak_elo = elo
        peak_fecha = fec_ult or "-"
        peak_torneo = "-"
        best_perf = 0
        best_perf_torneo = "-"

        tot_partidas = 0
        tot_puntos = 0.0
        sum_rivales_part = 0.0
        balance_elo = 0.0

        if parts_rows:
            puntos_chart.append({
                "fecha": parts_rows[0][1],
                "torneo": f"Inicio ({parts_rows[0][2]})",
                "elo": parts_rows[0][3]
            })
            peak_elo = parts_rows[0][3]
            peak_fecha = parts_rows[0][1]
            peak_torneo = parts_rows[0][2]

            for p in parts_rows:
                pid, t_fec, t_nom, e_ini, r_med, n_p, pts, v_elo, k = p
                n_elo = round(e_ini + v_elo)
                perf = calc_perf(r_med, pts, n_p)

                tot_partidas += n_p
                tot_puntos += pts
                sum_rivales_part += (r_med * n_p)
                balance_elo += v_elo

                trayectoria.append({
                    "num": len(trayectoria) + 1,
                    "fecha": t_fec,
                    "torneo": t_nom,
                    "elo_inicial": e_ini,
                    "rivales_medio": round(r_med, 1),
                    "partidas": n_p,
                    "puntos": pts,
                    "perf": perf,
                    "variacion": round(v_elo, 1),
                    "nuevo_elo": n_elo
                })

                puntos_chart.append({
                    "fecha": t_fec,
                    "torneo": t_nom,
                    "elo": n_elo
                })

                if n_elo > peak_elo:
                    peak_elo = n_elo
                    peak_fecha = t_fec
                    peak_torneo = t_nom

                if perf > best_perf:
                    best_perf = perf
                    best_perf_torneo = t_nom

        efectividad = round((tot_puntos / tot_partidas * 100), 1) if tot_partidas > 0 else 0.0
        rivales_ponderado = round((sum_rivales_part / tot_partidas), 1) if tot_partidas > 0 else 0.0

        jugadores_data.append({
            "pos": pos,
            "id": jid,
            "nombre": nom,
            "apellidos": ape,
            "nombre_completo": f"{nom} {ape}",
            "elo": elo,
            "titulo": tit or "",
            "variacion": var,
            "num_torneos": torn,
            "fecha_ultimo": fec_ult or "Nunca",
            "dias_inactivo": dias,
            "peak_elo": peak_elo,
            "peak_fecha": peak_fecha,
            "peak_torneo": peak_torneo,
            "best_perf": best_perf,
            "best_perf_torneo": best_perf_torneo,
            "total_partidas": tot_partidas,
            "total_puntos": tot_puntos,
            "efectividad": efectividad,
            "rivales_ponderado": rivales_ponderado,
            "balance_elo": round(balance_elo, 1),
            "trayectoria": trayectoria,
            "puntos_chart": puntos_chart
        })

    torneos_ciclo_data = []
    for tid, tnom, tfec in torneos_computados:
        n_partic = cursor.execute("SELECT COUNT(*) FROM participaciones WHERE torneo_id = ?", (tid,)).fetchone()[0]
        torneos_ciclo_data.append({
            "id": tid,
            "nombre": tnom,
            "fecha": tfec,
            "participantes": n_partic
        })

    listas_rows = cursor.execute("SELECT id, fecha_generacion FROM listas_elo ORDER BY fecha_generacion DESC LIMIT 10").fetchall()
    historial_listas_data = []
    for lid, lfec in listas_rows:
        top3 = cursor.execute('''
            SELECT nombre, apellidos, elo FROM historial_jugadores_lista 
            WHERE lista_id = ? ORDER BY elo DESC LIMIT 3
        ''', (lid,)).fetchall()
        tot = cursor.execute("SELECT COUNT(*) FROM historial_jugadores_lista WHERE lista_id = ?", (lid,)).fetchone()[0]
        historial_listas_data.append({
            "id": lid,
            "fecha": lfec,
            "total_socios": tot,
            "top3": [f"{n} {a} ({e})" for n, a, e in top3]
        })

    media_elo = round(sum(j["elo"] for j in jugadores_data) / len(jugadores_data), 1) if jugadores_data else 0
    elo_max = max(j["elo"] for j in jugadores_data) if jugadores_data else 0

    conn.close()

    payload = {
        "fecha_emision": hoy.strftime("%d/%m/%Y"),
        "hora_emision": hoy.strftime("%H:%M"),
        "stats": {
            "total_socios": len(jugadores_data),
            "media_elo": media_elo,
            "elo_max": elo_max,
            "torneos_ciclo": len(torneos_ciclo_data),
            "total_torneos_hist": total_torneos_hist
        },
        "jugadores": jugadores_data,
        "torneos_ciclo": torneos_ciclo_data,
        "historial_listas": historial_listas_data
    }

    json_data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    img_tag = f'<img src="{escudo_b64}" alt="Escudo Oficial Portugaleteko Xake Taldea" class="escudo-img">' if escudo_b64 else '<div class="escudo-fallback">♟️</div>'

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portugaleteko Xake Taldea - Portal ELO y Fichas de Socios</title>
    <style>
        :root {{
            --primary: #1b3a57;
            --primary-dark: #0d233a;
            --primary-light: #2c5282;
            --accent: #d4af37;
            --accent-hover: #b8972e;
            --bg: #f4f7fb;
            --surface: #ffffff;
            --text-main: #1a202c;
            --text-muted: #718096;
            --border: #e2e8f0;
            --badge-green: #38a169;
            --badge-red: #e53e3e;
            --badge-gray: #a0aec0;
            --shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}

        body {{
            background-color: var(--bg);
            color: var(--text-main);
            line-height: 1.5;
            padding-bottom: 50px;
        }}

        /* Header */
        header {{
            background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
            color: white;
            padding: 24px 16px;
            box-shadow: var(--shadow);
            border-bottom: 4px solid var(--accent);
        }}

        .header-content {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }}

        .escudo-wrap {{
            width: 80px;
            height: 80px;
            background: white;
            border-radius: 12px;
            padding: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            flex-shrink: 0;
        }}

        .escudo-img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }}

        .escudo-fallback {{
            font-size: 40px;
        }}

        .header-text h1 {{
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            margin-bottom: 4px;
        }}

        .header-text p {{
            font-size: 0.95rem;
            opacity: 0.85;
        }}

        .header-actions {{
            margin-left: auto;
            display: flex;
            gap: 10px;
            align-items: center;
        }}

        .btn-action {{
            background-color: var(--accent);
            color: #1a202c;
            border: none;
            padding: 9px 15px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.88rem;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
            text-decoration: none;
        }}

        .btn-action:hover {{
            background-color: var(--accent-hover);
            transform: translateY(-1px);
        }}

        /* Container & Metrics Cards */
        .container {{
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 16px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .stat-card {{
            background: var(--surface);
            padding: 16px 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .stat-icon {{
            width: 48px;
            height: 48px;
            border-radius: 10px;
            background: #ebf4ff;
            color: var(--primary-light);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            flex-shrink: 0;
        }}

        .stat-content .stat-val {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-dark);
            line-height: 1.2;
        }}

        .stat-content .stat-lbl {{
            font-size: 0.82rem;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        /* Nav Tabs */
        .tabs {{
            display: flex;
            gap: 8px;
            border-bottom: 2px solid var(--border);
            margin-bottom: 20px;
        }}

        .tab-btn {{
            background: none;
            border: none;
            padding: 10px 18px;
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }}

        .tab-btn:hover {{
            color: var(--primary);
        }}

        .tab-btn.active {{
            color: var(--primary);
            border-bottom-color: var(--accent);
        }}

        /* Toolbar Controls */
        .toolbar {{
            background: var(--surface);
            padding: 16px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            align-items: center;
            justify-content: space-between;
        }}

        .search-box {{
            flex: 1 1 280px;
            position: relative;
        }}

        .search-box input {{
            width: 100%;
            padding: 10px 14px 10px 38px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 0.92rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .search-box input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(27, 58, 87, 0.15);
        }}

        .search-icon {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 16px;
        }}

        .filter-buttons {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}

        .btn-filter {{
            background: #f1f5f9;
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 7px 14px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-filter:hover {{
            background: #e2e8f0;
        }}

        .btn-filter.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        /* Table Card */
        .table-card {{
            background: var(--surface);
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            overflow: hidden;
        }}

        .table-responsive {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.92rem;
        }}

        th {{
            background-color: #f8fafc;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 14px 16px;
            border-bottom: 2px solid var(--border);
            white-space: nowrap;
            user-select: none;
            cursor: pointer;
        }}

        th:hover {{
            color: var(--primary);
        }}

        th.sort-asc::after {{
            content: " ▲";
            font-size: 0.7rem;
        }}

        th.sort-desc::after {{
            content: " ▼";
            font-size: 0.7rem;
        }}

        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}

        tr.player-row {{
            cursor: pointer;
            transition: background-color 0.15s;
        }}

        tr.player-row:hover {{
            background-color: #f1f7fe;
        }}

        .pos-badge {{
            display: inline-block;
            width: 28px;
            height: 28px;
            line-height: 28px;
            text-align: center;
            border-radius: 50%;
            font-weight: 700;
            font-size: 0.85rem;
            background: #e2e8f0;
            color: #4a5568;
        }}

        .pos-1 {{ background: #fef08a; color: #854d0e; box-shadow: 0 0 6px rgba(234, 179, 8, 0.4); }}
        .pos-2 {{ background: #e2e8f0; color: #475569; }}
        .pos-3 {{ background: #fed7aa; color: #9a3412; }}

        .player-name {{
            font-weight: 600;
            color: var(--primary);
        }}

        .player-title {{
            display: inline-block;
            background: #fed7aa;
            color: #9a3412;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 4px;
            margin-right: 6px;
        }}

        .elo-cell {{
            font-weight: 700;
            font-size: 1.05rem;
            color: var(--primary-dark);
        }}

        .var-badge {{
            display: inline-block;
            font-weight: 600;
            font-size: 0.82rem;
            padding: 2px 7px;
            border-radius: 12px;
            white-space: nowrap;
        }}

        .var-pos {{ background: #def7ec; color: #03543f; }}
        .var-neg {{ background: #fde8e8; color: #9b1c1c; }}
        .var-zero {{ background: #f3f4f6; color: #6b7280; }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 0.78rem;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 9999px;
            white-space: nowrap;
        }}

        .status-act {{ background: #def7ec; color: #03543f; }}
        .status-inact {{ background: #fde8e8; color: #9b1c1c; }}

        .dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
        }}
        .dot-green {{ background: #31c48d; }}
        .dot-red {{ background: #f98080; }}

        .btn-view-ficha {{
            background: #ebf4ff;
            color: var(--primary-light);
            border: 1px solid #c3ddfd;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }}

        .btn-view-ficha:hover {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        /* Modal / Ficha Viewer */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(13, 35, 58, 0.6);
            backdrop-filter: blur(3px);
            z-index: 1000;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 16px;
            opacity: 0;
            transition: opacity 0.2s ease-in-out;
        }}

        .modal-overlay.open {{
            display: flex;
            opacity: 1;
        }}

        .modal-card {{
            background: var(--surface);
            border-radius: 16px;
            box-shadow: var(--shadow-lg);
            width: 100%;
            max-width: 900px;
            max-height: 90vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            animation: modalSlide 0.25s ease-out;
        }}

        @keyframes modalSlide {{
            from {{ transform: translateY(20px); opacity: 0; }}
            to {{ transform: translateY(0); opacity: 1; }}
        }}

        .modal-header {{
            background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
            color: white;
            padding: 20px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid var(--accent);
        }}

        .modal-header h2 {{
            font-size: 1.35rem;
            margin-bottom: 2px;
        }}

        .modal-header p {{
            font-size: 0.85rem;
            opacity: 0.85;
        }}

        .modal-close {{
            background: rgba(255, 255, 255, 0.15);
            border: none;
            color: white;
            width: 34px;
            height: 34px;
            border-radius: 50%;
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }}

        .modal-close:hover {{
            background: rgba(255, 255, 255, 0.3);
        }}

        .modal-body {{
            padding: 24px;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }}

        .ficha-badges {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }}

        .ficha-stat-box {{
            background: #f8fafc;
            border: 1px solid var(--border);
            padding: 12px 14px;
            border-radius: 10px;
        }}

        .ficha-stat-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
        }}

        .ficha-stat-value {{
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--primary-dark);
        }}

        .ficha-stat-sub {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        .section-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--primary-dark);
            margin: 20px 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        /* SVG Evolution Chart */
        .chart-box {{
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 24px;
            position: relative;
        }}

        .chart-svg {{
            width: 100%;
            height: 220px;
            overflow: visible;
        }}

        .chart-tooltip {{
            position: absolute;
            background: rgba(13, 35, 58, 0.95);
            color: white;
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 0.78rem;
            pointer-events: none;
            display: none;
            transform: translate(-50%, -120%);
            white-space: nowrap;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            z-index: 10;
        }}

        /* Trajectory Table */
        .modal-body table th {{
            background-color: #f1f5f9;
        }}

        /* Footer */
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.82rem;
            margin-top: 40px;
            padding: 0 16px;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .header-content {{
                flex-direction: column;
                text-align: center;
            }}
            .header-actions {{
                margin-left: 0;
                width: 100%;
                justify-content: center;
            }}
            .escudo-wrap {{
                margin: 0 auto;
            }}
            .toolbar {{
                flex-direction: column;
                align-items: stretch;
            }}
            .filter-buttons {{
                justify-content: center;
            }}
        }}
    </style>
</head>
<body>

    <!-- Header Oficial -->
    <header>
        <div class="header-content">
            <div class="escudo-wrap">
                {img_tag}
            </div>
            <div class="header-text">
                <h1>Portugaleteko Xake Taldea</h1>
                <p>Portal Oficial de Clasificación y Fichas de Socios • Rápidas FIDE (K=10)</p>
            </div>
            <div class="header-actions">
                <button class="btn-action" onclick="copiarWhatsApp()" title="Copiar resumen optimizado para WhatsApp y lectores de pantalla">
                    <span>📱</span> Copiar WhatsApp
                </button>
            </div>
        </div>
    </header>

    <div class="container">

        <!-- Métricas Rápidas -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-content">
                    <div class="stat-val" id="stat-socios">{len(jugadores_data)}</div>
                    <div class="stat-lbl">Socios Registrados</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⚡</div>
                <div class="stat-content">
                    <div class="stat-val" id="stat-media">{media_elo}</div>
                    <div class="stat-lbl">ELO Medio Activo</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">👑</div>
                <div class="stat-content">
                    <div class="stat-val" id="stat-max">{elo_max}</div>
                    <div class="stat-lbl">ELO Más Alto</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🏆</div>
                <div class="stat-content">
                    <div class="stat-val" id="stat-torneos">{len(torneos_ciclo_data)} <span style="font-size:0.9rem; font-weight:normal; color:#718096">({total_torneos_hist} hist.)</span></div>
                    <div class="stat-lbl">Torneos en Ciclo</div>
                </div>
            </div>
        </div>

        <!-- Pestañas de Navegación -->
        <div class="tabs">
            <button class="tab-btn active" onclick="cambiarTab('ranking')">♟️ Ranking Oficial</button>
            <button class="tab-btn" onclick="cambiarTab('torneos')">🏆 Torneos del Ciclo ({len(torneos_ciclo_data)})</button>
            <button class="tab-btn" onclick="cambiarTab('historial')">📜 Historial de Listas</button>
        </div>

        <!-- VISTA 1: RANKING -->
        <div id="view-ranking">
            <!-- Barra de Filtros y Búsqueda -->
            <div class="toolbar">
                <div class="search-box">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="buscador" placeholder="Buscar por socio, apellido o título..." oninput="filtrarTabla()">
                </div>
                <div class="filter-buttons">
                    <button class="btn-filter active" data-filter="todos" onclick="setFiltro('todos')">Todos ({len(jugadores_data)})</button>
                    <button class="btn-filter" data-filter="activos" onclick="setFiltro('activos')">Activos (&le;365d)</button>
                    <button class="btn-filter" data-filter="inactivos" onclick="setFiltro('inactivos')">Inactivos (&gt;365d)</button>
                    <button class="btn-filter" data-filter="podio" onclick="setFiltro('podio')">🏆 Top 3 Podio</button>
                </div>
            </div>

            <!-- Tabla de Ranking -->
            <div class="table-card">
                <div class="table-responsive">
                    <table id="tabla-ranking">
                        <thead>
                            <tr>
                                <th style="width: 60px; text-align: center;" onclick="ordenarPor('pos')">#</th>
                                <th onclick="ordenarPor('nombre')">Socio / Jugador</th>
                                <th style="text-align: center;" onclick="ordenarPor('elo')">ELO Actual</th>
                                <th style="text-align: center;" onclick="ordenarPor('var')">Var. Ciclo</th>
                                <th style="text-align: center;" onclick="ordenarPor('torneos')">Torneos</th>
                                <th onclick="ordenarPor('ultimo')">Último Torneo</th>
                                <th style="text-align: center;">Estado</th>
                                <th style="text-align: center;">Acción</th>
                            </tr>
                        </thead>
                        <tbody id="ranking-body">
                            <!-- Inyectado por JS -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- VISTA 2: TORNEOS DEL CICLO -->
        <div id="view-torneos" style="display: none;">
            <div class="table-card">
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 60px; text-align: center;">#</th>
                                <th>Fecha</th>
                                <th>Nombre del Torneo</th>
                                <th style="text-align: center;">Participantes Computados</th>
                            </tr>
                        </thead>
                        <tbody id="torneos-body">
                            <!-- Inyectado por JS -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- VISTA 3: HISTORIAL DE LISTAS -->
        <div id="view-historial" style="display: none;">
            <div class="table-card">
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 70px; text-align: center;">Lista ID</th>
                                <th>Fecha de Generación Oficial</th>
                                <th style="text-align: center;">Total Socios</th>
                                <th>Podio / Top 3</th>
                            </tr>
                        </thead>
                        <tbody id="historial-body">
                            <!-- Inyectado por JS -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

    </div>

    <!-- MODAL DE FICHA INDIVIDUAL DE SOCIO -->
    <div class="modal-overlay" id="modal-ficha" onclick="cerrarFicha(event)">
        <div class="modal-card" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div>
                    <h2 id="modal-nombre">Nombre del Jugador</h2>
                    <p id="modal-sub">ID: 0 • Título: - • Registrado en el club</p>
                </div>
                <button class="modal-close" onclick="cerrarFichaDirecto()">✕</button>
            </div>
            <div class="modal-body">

                <!-- Métricas Principales del Jugador -->
                <div class="ficha-badges">
                    <div class="ficha-stat-box">
                        <div class="ficha-stat-label">ELO Actual</div>
                        <div class="ficha-stat-value" id="modal-elo">0</div>
                        <div class="ficha-stat-sub" id="modal-var-badge">Variación: +0</div>
                    </div>
                    <div class="ficha-stat-box">
                        <div class="ficha-stat-label">Pico Máximo (Peak ELO)</div>
                        <div class="ficha-stat-value" id="modal-peak">0</div>
                        <div class="ficha-stat-sub" id="modal-peak-fecha">-</div>
                    </div>
                    <div class="ficha-stat-box">
                        <div class="ficha-stat-label">Mejor Performance (Rp)</div>
                        <div class="ficha-stat-value" id="modal-perf">0</div>
                        <div class="ficha-stat-sub" id="modal-perf-torneo">-</div>
                    </div>
                    <div class="ficha-stat-box">
                        <div class="ficha-stat-label">Efectividad Global</div>
                        <div class="ficha-stat-value" id="modal-efectividad">0%</div>
                        <div class="ficha-stat-sub" id="modal-pts-part">0 pts / 0 part.</div>
                    </div>
                </div>

                <!-- Gráfico de Evolución de ELO -->
                <div class="section-title">
                    <span>📈</span> Evolución de ELO en el Club
                </div>
                <div class="chart-box" id="chart-container">
                    <svg class="chart-svg" id="chart-svg" viewBox="0 0 800 220" preserveAspectRatio="none">
                        <!-- Generado dinámicamente -->
                    </svg>
                    <div class="chart-tooltip" id="chart-tooltip"></div>
                </div>

                <!-- Tabla de Trayectoria Torneo a Torneo -->
                <div class="section-title">
                    <span>♟️</span> Trayectoria Torneo a Torneo
                </div>
                <div class="table-card">
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th style="width: 40px; text-align: center;">#</th>
                                    <th>Fecha</th>
                                    <th>Torneo</th>
                                    <th style="text-align: center;">ELO Ini</th>
                                    <th style="text-align: center;">Riv. Med</th>
                                    <th style="text-align: center;">Pts / Part</th>
                                    <th style="text-align: center;">Perf.</th>
                                    <th style="text-align: center;">Var.</th>
                                    <th style="text-align: center;">Nuevo ELO</th>
                                </tr>
                            </thead>
                            <tbody id="modal-trayectoria-body">
                                <!-- Filas inyectadas por JS -->
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <footer>
        Portugaleteko Xake Taldea • Portal interactivo de clasificación de ajedrez rápido • Generado el {hoy.strftime("%d/%m/%Y")} a las {hoy.strftime("%H:%M")}
    </footer>

    <!-- DATOS EMBEBIDOS JSON -->
    <script id="club-data" type="application/json">
{json_data}
    </script>

    <!-- LÓGICA INTERACTIVA CLIENTE -->
    <script>
        const CLUB_DATA = JSON.parse(document.getElementById("club-data").textContent);
        let currentFilter = "todos";
        let sortKey = "pos";
        let sortAsc = true;

        function escapeHtml(str) {{
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }}

        document.addEventListener("DOMContentLoaded", () => {{
            renderRanking();
            renderTorneos();
            renderHistorial();
        }});

        function cambiarTab(tab) {{
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.getElementById("view-ranking").style.display = tab === 'ranking' ? 'block' : 'none';
            document.getElementById("view-torneos").style.display = tab === 'torneos' ? 'block' : 'none';
            document.getElementById("view-historial").style.display = tab === 'historial' ? 'block' : 'none';

            if (tab === 'ranking') event.target.classList.add("active");
            if (tab === 'torneos') event.target.classList.add("active");
            if (tab === 'historial') event.target.classList.add("active");
        }}

        function setFiltro(tipo) {{
            currentFilter = tipo;
            document.querySelectorAll(".btn-filter").forEach(b => {{
                b.classList.toggle("active", b.dataset.filter === tipo);
            }});
            renderRanking();
        }}

        function filtrarTabla() {{
            renderRanking();
        }}

        function ordenarPor(key) {{
            if (sortKey === key) {{
                sortAsc = !sortAsc;
            }} else {{
                sortKey = key;
                sortAsc = (key === 'pos' || key === 'nombre') ? true : false;
            }}
            updateHeaderSortIcons();
            renderRanking();
        }}

        function updateHeaderSortIcons() {{
            const ths = document.querySelectorAll("#tabla-ranking th");
            ths.forEach(th => {{
                th.classList.remove("sort-asc", "sort-desc");
            }});
            const activeTh = Array.from(ths).find(th => th.getAttribute("onclick") && th.getAttribute("onclick").includes(`'${{sortKey}}'`));
            if (activeTh) {{
                activeTh.classList.add(sortAsc ? "sort-asc" : "sort-desc");
            }}
        }}

        function renderRanking() {{
            const tbody = document.getElementById("ranking-body");
            const busqueda = (document.getElementById("buscador").value || "").toLowerCase().trim();

            let filtrados = CLUB_DATA.jugadores.filter(j => {{
                const matchTexto = j.nombre_completo.toLowerCase().includes(busqueda) || 
                                   (j.titulo && j.titulo.toLowerCase().includes(busqueda));
                if (!matchTexto) return false;

                if (currentFilter === 'activos') return j.dias_inactivo <= 365;
                if (currentFilter === 'inactivos') return j.dias_inactivo > 365;
                if (currentFilter === 'podio') return j.pos <= 3;
                return true;
            }});

            // Ordenación
            filtrados.sort((a, b) => {{
                let valA = a[sortKey];
                let valB = b[sortKey];

                if (sortKey === 'nombre') {{
                    valA = a.apellidos + ' ' + a.nombre;
                    valB = b.apellidos + ' ' + b.nombre;
                }} else if (sortKey === 'var') {{
                    valA = a.variacion;
                    valB = b.variacion;
                }} else if (sortKey === 'torneos') {{
                    valA = a.num_torneos;
                    valB = b.num_torneos;
                }} else if (sortKey === 'ultimo') {{
                    valA = a.fecha_ultimo === 'Nunca' ? '0000-00-00' : a.fecha_ultimo;
                    valB = b.fecha_ultimo === 'Nunca' ? '0000-00-00' : b.fecha_ultimo;
                }}

                if (valA < valB) return sortAsc ? -1 : 1;
                if (valA > valB) return sortAsc ? 1 : -1;
                return 0;
            }});

            if (filtrados.length === 0) {{
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 30px; color:#718096">No se encontraron socios que coincidan con la búsqueda.</td></tr>`;
                return;
            }}

            tbody.innerHTML = filtrados.map(j => {{
                const posClass = j.pos === 1 ? 'pos-1' : j.pos === 2 ? 'pos-2' : j.pos === 3 ? 'pos-3' : '';
                const tituloTag = j.titulo ? `<span class="player-title">${{escapeHtml(j.titulo)}}</span>` : '';
                
                const varSign = j.variacion > 0 ? `+${{j.variacion}}` : (j.variacion < 0 ? `${{j.variacion}}` : `=`);
                const varClass = j.variacion > 0 ? 'var-pos' : (j.variacion < 0 ? 'var-neg' : 'var-zero');

                const esActivo = j.dias_inactivo <= 365;
                const statusTag = esActivo 
                    ? `<span class="status-badge status-act"><span class="dot dot-green"></span>Activo</span>` 
                    : `<span class="status-badge status-inact"><span class="dot dot-red"></span>Inactivo</span>`;

                return `
                    <tr class="player-row" onclick="abrirFicha(${{j.id}})">
                        <td style="text-align: center;"><span class="pos-badge ${{posClass}}">${{j.pos}}</span></td>
                        <td>
                            ${{tituloTag}}<span class="player-name">${{escapeHtml(j.apellidos)}}, ${{escapeHtml(j.nombre)}}</span>
                        </td>
                        <td style="text-align: center;"><span class="elo-cell">${{j.elo}}</span></td>
                        <td style="text-align: center;"><span class="var-badge ${{varClass}}">${{varSign}}</span></td>
                        <td style="text-align: center; color: #4a5568; font-weight: 500;">${{j.num_torneos}}</td>
                        <td style="color: #718096; font-size: 0.88rem;">${{j.fecha_ultimo}}</td>
                        <td style="text-align: center;">${{statusTag}}</td>
                        <td style="text-align: center;">
                            <button class="btn-view-ficha" onclick="event.stopPropagation(); abrirFicha(${{j.id}})">Ver Ficha</button>
                        </td>
                    </tr>
                `;
            }}).join("");
        }}

        function renderTorneos() {{
            const tbody = document.getElementById("torneos-body");
            if (!CLUB_DATA.torneos_ciclo || CLUB_DATA.torneos_ciclo.length === 0) {{
                tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 24px; color: #718096">No hay torneos registrados en el ciclo actual desde la última lista oficial.</td></tr>`;
                return;
            }}
            tbody.innerHTML = CLUB_DATA.torneos_ciclo.map((t, idx) => `
                <tr>
                    <td style="text-align: center; font-weight: bold; color: var(--text-muted);">${{idx + 1}}</td>
                    <td style="font-weight: 600; color: var(--primary);">${{escapeHtml(t.fecha)}}</td>
                    <td><strong>${{escapeHtml(t.nombre)}}</strong></td>
                    <td style="text-align: center;"><span class="pos-badge">${{t.participantes}}</span></td>
                </tr>
            `).join("");
        }}

        function renderHistorial() {{
            const tbody = document.getElementById("historial-body");
            if (!CLUB_DATA.historial_listas || CLUB_DATA.historial_listas.length === 0) {{
                tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 24px; color: #718096">No hay registros de listas anteriores generadas aún.</td></tr>`;
                return;
            }}
            tbody.innerHTML = CLUB_DATA.historial_listas.map(l => `
                <tr>
                    <td style="text-align: center; font-weight: bold; color: var(--primary);">#${{l.id}}</td>
                    <td style="font-weight: 600;">${{escapeHtml(l.fecha)}}</td>
                    <td style="text-align: center;"><span class="pos-badge">${{l.total_socios}}</span></td>
                    <td style="font-size: 0.88rem; color: #4a5568;">${{escapeHtml(l.top3.join(" • ") || "Sin datos")}}</td>
                </tr>
            `).join("");
        }}

        /* Ficha y Gráfico Modal */
        function abrirFicha(jugadorId) {{
            const j = CLUB_DATA.jugadores.find(item => item.id === jugadorId);
            if (!j) return;

            document.getElementById("modal-nombre").textContent = `${{j.nombre}} ${{j.apellidos}}`;
            document.getElementById("modal-sub").textContent = `ID Socio: #${{j.id}} • Título: ${{j.titulo || 'Ninguno'}} • Ranking Club: #${{j.pos}} de ${{CLUB_DATA.jugadores.length}}`;
            document.getElementById("modal-elo").textContent = j.elo;
            
            const varSign = j.variacion > 0 ? `+${{j.variacion}}` : (j.variacion < 0 ? `${{j.variacion}}` : `0`);
            document.getElementById("modal-var-badge").textContent = `Variación ciclo: ${{varSign}} pts`;

            document.getElementById("modal-peak").textContent = `${{j.peak_elo}} pts`;
            document.getElementById("modal-peak-fecha").textContent = j.peak_torneo !== '-' ? `${{j.peak_torneo}} (${{j.peak_fecha}})` : '-';

            document.getElementById("modal-perf").textContent = j.best_perf > 0 ? `${{j.best_perf}} pts` : '-';
            document.getElementById("modal-perf-torneo").textContent = j.best_perf_torneo !== '-' ? j.best_perf_torneo : '-';

            document.getElementById("modal-efectividad").textContent = `${{j.efectividad}}%`;
            document.getElementById("modal-pts-part").textContent = `${{j.total_puntos}} pts en ${{j.total_partidas}} part. (Rivales: ${{j.rivales_ponderado}})`;

            // Render Gráfico SVG
            renderChart(j.puntos_chart);

            // Render Trayectoria
            const tbodyTray = document.getElementById("modal-trayectoria-body");
            if (!j.trayectoria || j.trayectoria.length === 0) {{
                tbodyTray.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 20px; color:#718096">Este socio aún no tiene torneos disputados en el sistema.</td></tr>`;
            }} else {{
                tbodyTray.innerHTML = j.trayectoria.map(t => {{
                    const varS = t.variacion > 0 ? `+${{t.variacion}}` : `${{t.variacion}}`;
                    const varC = t.variacion > 0 ? 'var-pos' : (t.variacion < 0 ? 'var-neg' : 'var-zero');
                    return `
                        <tr>
                            <td style="text-align: center; color: var(--text-muted);">${{t.num}}</td>
                            <td style="white-space: nowrap; font-size: 0.85rem;">${{escapeHtml(t.fecha)}}</td>
                            <td><strong>${{escapeHtml(t.torneo)}}</strong></td>
                            <td style="text-align: center;">${{t.elo_inicial}}</td>
                            <td style="text-align: center;">${{t.rivales_medio}}</td>
                            <td style="text-align: center; font-weight: 600;">${{t.puntos}} / ${{t.partidas}}</td>
                            <td style="text-align: center; font-weight: 700; color: var(--primary);">${{t.perf}}</td>
                            <td style="text-align: center;"><span class="var-badge ${{varC}}">${{varS}}</span></td>
                            <td style="text-align: center; font-weight: 700;">${{t.nuevo_elo}}</td>
                        </tr>
                    `;
                }}).join("");
            }}

            const modal = document.getElementById("modal-ficha");
            modal.classList.add("open");
            document.body.style.overflow = "hidden";
        }}

        function cerrarFicha(e) {{
            if (e.target.id === 'modal-ficha') {{
                cerrarFichaDirecto();
            }}
        }}

        function cerrarFichaDirecto() {{
            const modal = document.getElementById("modal-ficha");
            modal.classList.remove("open");
            document.body.style.overflow = "";
        }}

        document.addEventListener("keydown", (e) => {{
            if (e.key === "Escape") cerrarFichaDirecto();
        }});

        function renderChart(puntos) {{
            const svg = document.getElementById("chart-svg");
            const tooltip = document.getElementById("chart-tooltip");
            svg.innerHTML = "";

            if (!puntos || puntos.length <= 1) {{
                svg.innerHTML = `<text x="400" y="110" text-anchor="middle" fill="#a0aec0" font-size="14">No hay suficientes torneos registrados para trazar la gráfica evolutiva</text>`;
                return;
            }}

            const elos = puntos.map(p => p.elo);
            const minElo = Math.min(...elos) - 30;
            const maxElo = Math.max(...elos) + 30;
            const rangeElo = maxElo - minElo || 1;

            const paddingLeft = 60;
            const paddingRight = 40;
            const paddingTop = 25;
            const paddingBottom = 35;
            const width = 800;
            const height = 220;

            const plotW = width - paddingLeft - paddingRight;
            const plotH = height - paddingTop - paddingBottom;

            // Grid lines (3 horizontal lines)
            let gridHtml = "";
            for (let i = 0; i <= 3; i++) {{
                const yVal = minElo + (rangeElo / 3) * i;
                const yPos = paddingTop + plotH - ((yVal - minElo) / rangeElo) * plotH;
                gridHtml += `
                    <line x1="${{paddingLeft}}" y1="${{yPos}}" x2="${{width - paddingRight}}" y2="${{yPos}}" stroke="#e2e8f0" stroke-dasharray="4" />
                    <text x="${{paddingLeft - 10}}" y="${{yPos + 4}}" text-anchor="end" fill="#718096" font-size="11" font-weight="600">${{Math.round(yVal)}}</text>
                `;
            }}

            const coords = puntos.map((p, idx) => {{
                const x = paddingLeft + (idx / (puntos.length - 1)) * plotW;
                const y = paddingTop + plotH - ((p.elo - minElo) / rangeElo) * plotH;
                return {{ x, y, data: p }};
            }});

            const polylinePoints = coords.map(c => `${{c.x.toFixed(1)}},${{c.y.toFixed(1)}}`).join(" ");

            // Fill area under line
            const areaPoints = `${{paddingLeft}},${{paddingTop + plotH}} ` + polylinePoints + ` ${{width - paddingRight}},${{paddingTop + plotH}}`;

            const gradientDef = `
                <defs>
                    <linearGradient id="chartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#1b3a57" stop-opacity="0.3" />
                        <stop offset="100%" stop-color="#1b3a57" stop-opacity="0.0" />
                    </linearGradient>
                </defs>
            `;

            let dotsHtml = coords.map((c, i) => `
                <circle cx="${{c.x}}" cy="${{c.y}}" r="5" fill="#d4af37" stroke="#1b3a57" stroke-width="2.5" 
                        style="cursor: pointer; transition: transform 0.15s;"
                        onmouseover="mostrarTooltip(event, '${{c.data.torneo}}', '${{c.data.fecha}}', ${{c.data.elo}})"
                        onmouseout="ocultarTooltip()" />
            `).join("");

            svg.innerHTML = `
                ${{gradientDef}}
                ${{gridHtml}}
                <polygon points="${{areaPoints}}" fill="url(#chartGradient)" />
                <polyline fill="none" stroke="#1b3a57" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${{polylinePoints}}" />
                ${{dotsHtml}}
            `;
        }}

        function mostrarTooltip(e, torneo, fecha, elo) {{
            const tooltip = document.getElementById("chart-tooltip");
            const box = document.getElementById("chart-container").getBoundingClientRect();
            const x = e.clientX - box.left;
            const y = e.clientY - box.top;

            tooltip.style.left = `${{x}}px`;
            tooltip.style.top = `${{y}}px`;
            tooltip.innerHTML = `<strong>${{elo}} pts</strong><br><span style="color:#d4af37">${{escapeHtml(torneo)}}</span><br><small style="color:#a0aec0">${{escapeHtml(fecha)}}</small>`;
            tooltip.style.display = "block";
        }}

        function ocultarTooltip() {{
            document.getElementById("chart-tooltip").style.display = "none";
        }}

        /* Generador de texto para WhatsApp */
        function copiarWhatsApp() {{
            let txt = `*PORTUGALETEKO XAKE TALDEA*\\n`;
            txt += `*CLASIFICACIÓN ELO RÁPIDAS FIDE (K=10)*\\n`;
            txt += `📅 Emisión: ${{CLUB_DATA.fecha_emision}} a las ${{CLUB_DATA.hora_emision}}\\n`;
            txt += `👥 Total socios: ${{CLUB_DATA.jugadores.length}} | ⚡ ELO medio: ${{CLUB_DATA.stats.media_elo}}\\n\\n`;
            txt += `*LISTADO OFICIAL DE ELO*\\n`;
            txt += `-----------------------------------------\\n`;

            CLUB_DATA.jugadores.forEach(j => {{
                const titulo = j.titulo ? `${{j.titulo}} ` : '';
                const varStr = j.variacion > 0 ? `(+${{j.variacion}})` : (j.variacion < 0 ? `(${{j.variacion}})` : `(=)`);
                const estado = j.dias_inactivo > 365 ? ' (Inactivo)' : '';
                txt += `${{j.pos}}. ${{titulo}}${{j.apellidos}}, ${{j.nombre}} | ${{j.elo}} pts ${{varStr}}${{estado}}\\n`;
            }});

            if (CLUB_DATA.torneos_ciclo && CLUB_DATA.torneos_ciclo.length > 0) {{
                txt += `\\n*TORNEOS EN ESTE CICLO (${{CLUB_DATA.torneos_ciclo.length}}):*\\n`;
                CLUB_DATA.torneos_ciclo.forEach(t => {{
                    txt += `• ${{t.nombre}} (${{t.fecha}})\\n`;
                }});
            }}

            navigator.clipboard.writeText(txt).then(() => {{
                alert("¡Ranking copiado al portapapeles con formato accesible para WhatsApp! Ya puedes pegarlo con Ctrl+V.");
            }}).catch(err => {{
                prompt("Copia manualmente el texto para WhatsApp:", txt);
            }});
        }}
    </script>
</body>
</html>
"""

    with open(ruta_destino, "w", encoding="utf-8") as f:
        f.write(html)
    return ruta_destino
