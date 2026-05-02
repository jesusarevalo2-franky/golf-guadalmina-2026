import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'golf.db')

MESES = {
    'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
    'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
    'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
}

PTS_18H = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
PTS_9H  = [12.5, 9, 7.5, 6, 5, 4, 3, 2, 1, 0.5]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jugadores (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                hcp  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS partidas (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                semana   INTEGER,
                fecha    TEXT NOT NULL,
                campo    TEXT NOT NULL DEFAULT 'Guadalmina Norte',
                hoyos    TEXT NOT NULL CHECK(hoyos IN ('9 hoyos','18 hoyos')),
                es_major INTEGER NOT NULL DEFAULT 0,
                notas    TEXT
            );

            CREATE TABLE IF NOT EXISTS resultados (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                partida_id  INTEGER NOT NULL REFERENCES partidas(id) ON DELETE CASCADE,
                jugador_id  INTEGER NOT NULL REFERENCES jugadores(id),
                hcp         REAL NOT NULL,
                stableford  INTEGER NOT NULL,
                posicion    INTEGER,
                puntos      REAL
            );
        """)


def calcular_posicion_y_puntos(partida_id):
    with get_conn() as conn:
        partida = conn.execute(
            "SELECT hoyos, es_major FROM partidas WHERE id=?", (partida_id,)
        ).fetchone()
        if not partida:
            return

        resultados = conn.execute(
            "SELECT id, hcp, stableford FROM resultados WHERE partida_id=? ORDER BY stableford DESC, hcp ASC",
            (partida_id,)
        ).fetchall()

        tabla_pts = PTS_18H if partida['hoyos'] == '18 hoyos' else PTS_9H
        multiplicador = 1.5 if partida['es_major'] else 1.0

        for pos, r in enumerate(resultados, start=1):
            if pos <= len(tabla_pts):
                pts = tabla_pts[pos - 1] * multiplicador
            else:
                pts = tabla_pts[-1] * multiplicador
            conn.execute(
                "UPDATE resultados SET posicion=?, puntos=? WHERE id=?",
                (pos, pts, r['id'])
            )


def get_ranking():
    with get_conn() as conn:
        jugadores = conn.execute("SELECT id, nombre, hcp FROM jugadores ORDER BY nombre").fetchall()
        ranking = []
        for j in jugadores:
            res_9h = conn.execute("""
                SELECT r.puntos
                FROM resultados r
                JOIN partidas p ON p.id = r.partida_id
                WHERE r.jugador_id=? AND p.hoyos='9 hoyos'
                ORDER BY r.puntos DESC
            """, (j['id'],)).fetchall()

            res_18h = conn.execute("""
                SELECT r.puntos
                FROM resultados r
                JOIN partidas p ON p.id = r.partida_id
                WHERE r.jugador_id=? AND p.hoyos='18 hoyos'
                ORDER BY r.puntos DESC
            """, (j['id'],)).fetchall()

            mejores_9h  = [r['puntos'] for r in res_9h[:4]]
            mejores_18h = [r['puntos'] for r in res_18h[:8]]

            total_bruto = sum(r['puntos'] for r in res_9h) + sum(r['puntos'] for r in res_18h)
            jugadas = len(res_9h) + len(res_18h)

            tiene_min_9h  = len(res_9h) >= 4
            tiene_min_18h = len(res_18h) >= 8 or len(res_18h) == 0

            if tiene_min_9h and tiene_min_18h:
                total_neto = sum(mejores_9h) + sum(mejores_18h)
            else:
                total_neto = None

            ranking.append({
                'jugador_id': j['id'],
                'nombre': j['nombre'],
                'hcp': j['hcp'],
                'jugadas': jugadas,
                'jugadas_9h': len(res_9h),
                'jugadas_18h': len(res_18h),
                'total_bruto': total_bruto,
                'total_neto': total_neto,
                'media': round(total_bruto / jugadas, 2) if jugadas else 0,
                'mejor': max([r['puntos'] for r in res_9h] + [r['puntos'] for r in res_18h], default=0),
            })

        ranking_bruto = sorted(
            [r for r in ranking if r['jugadas'] > 0],
            key=lambda x: (-x['total_bruto'], x['hcp'])
        )
        ranking_neto = sorted(
            [r for r in ranking if r['total_neto'] is not None],
            key=lambda x: (-x['total_neto'], x['hcp'])
        )
        return ranking_bruto, ranking_neto


def get_partidas():
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.*, COUNT(r.id) as num_jugadores
            FROM partidas p
            LEFT JOIN resultados r ON r.partida_id = p.id
            GROUP BY p.id
            ORDER BY p.fecha DESC
        """).fetchall()


def get_partida(partida_id):
    with get_conn() as conn:
        p = conn.execute("SELECT * FROM partidas WHERE id=?", (partida_id,)).fetchone()
        rs = conn.execute("""
            SELECT r.*, j.nombre, j.hcp as hcp_actual
            FROM resultados r
            JOIN jugadores j ON j.id = r.jugador_id
            WHERE r.partida_id=?
            ORDER BY r.posicion
        """, (partida_id,)).fetchall()
        return p, rs


def get_jugadores():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM jugadores ORDER BY hcp ASC").fetchall()


def add_jugador(nombre, hcp):
    with get_conn() as conn:
        conn.execute("INSERT INTO jugadores (nombre, hcp) VALUES (?,?)", (nombre, hcp))


def update_jugador(jugador_id, nombre, hcp):
    with get_conn() as conn:
        conn.execute("UPDATE jugadores SET nombre=?, hcp=? WHERE id=?", (nombre, hcp, jugador_id))


def delete_jugador(jugador_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM jugadores WHERE id=?", (jugador_id,))


def add_partida(semana, fecha, campo, hoyos, es_major, notas, resultados_data):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO partidas (semana, fecha, campo, hoyos, es_major, notas) VALUES (?,?,?,?,?,?)",
            (semana or None, fecha, campo, hoyos, 1 if es_major else 0, notas)
        )
        partida_id = cur.lastrowid
        for jugador_id, stableford in resultados_data:
            hcp = conn.execute("SELECT hcp FROM jugadores WHERE id=?", (jugador_id,)).fetchone()['hcp']
            conn.execute(
                "INSERT INTO resultados (partida_id, jugador_id, hcp, stableford) VALUES (?,?,?,?)",
                (partida_id, jugador_id, hcp, stableford)
            )
    calcular_posicion_y_puntos(partida_id)
    return partida_id


def delete_partida(partida_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM partidas WHERE id=?", (partida_id,))


def get_historial_jugador(jugador_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.*, p.fecha, p.campo, p.hoyos, p.es_major, p.semana
            FROM resultados r
            JOIN partidas p ON p.id = r.partida_id
            WHERE r.jugador_id=?
            ORDER BY p.fecha DESC
        """, (jugador_id,)).fetchall()
