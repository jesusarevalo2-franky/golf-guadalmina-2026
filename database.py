import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = (os.environ.get('DATABASE_URL') or '').strip()

PTS_18H = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
PTS_9H  = [12.5, 9, 7.5, 6, 5, 4, 3, 2, 1, 0.5]


def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jugadores (
                    id     SERIAL PRIMARY KEY,
                    nombre TEXT NOT NULL UNIQUE,
                    hcp    REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS partidas (
                    id       SERIAL PRIMARY KEY,
                    semana   INTEGER,
                    fecha    TEXT NOT NULL,
                    campo    TEXT NOT NULL DEFAULT 'Guadalmina Norte',
                    hoyos    TEXT NOT NULL CHECK(hoyos IN ('9 hoyos','18 hoyos')),
                    es_major INTEGER NOT NULL DEFAULT 0,
                    notas    TEXT
                );

                CREATE TABLE IF NOT EXISTS resultados (
                    id         SERIAL PRIMARY KEY,
                    partida_id INTEGER NOT NULL REFERENCES partidas(id) ON DELETE CASCADE,
                    jugador_id INTEGER NOT NULL REFERENCES jugadores(id),
                    hcp        REAL NOT NULL,
                    stableford INTEGER NOT NULL,
                    posicion   INTEGER,
                    puntos     REAL
                );
            """)
        conn.commit()


def calcular_posicion_y_puntos(partida_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT hoyos, es_major FROM partidas WHERE id=%s", (partida_id,))
            partida = cur.fetchone()
            if not partida:
                return

            cur.execute(
                "SELECT id, hcp, stableford FROM resultados WHERE partida_id=%s ORDER BY stableford DESC, hcp ASC",
                (partida_id,)
            )
            resultados = cur.fetchall()

            tabla_pts = PTS_18H if partida['hoyos'] == '18 hoyos' else PTS_9H
            multiplicador = 1.5 if partida['es_major'] else 1.0

            for pos, r in enumerate(resultados, start=1):
                pts = tabla_pts[min(pos, len(tabla_pts)) - 1] * multiplicador
                cur.execute(
                    "UPDATE resultados SET posicion=%s, puntos=%s WHERE id=%s",
                    (pos, pts, r['id'])
                )
        conn.commit()


def get_ranking():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, nombre, hcp FROM jugadores ORDER BY nombre")
            jugadores = cur.fetchall()

        ranking = []
        for j in jugadores:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT r.puntos FROM resultados r
                    JOIN partidas p ON p.id = r.partida_id
                    WHERE r.jugador_id=%s AND p.hoyos='9 hoyos'
                    ORDER BY r.puntos DESC
                """, (j['id'],))
                res_9h = cur.fetchall()

                cur.execute("""
                    SELECT r.puntos FROM resultados r
                    JOIN partidas p ON p.id = r.partida_id
                    WHERE r.jugador_id=%s AND p.hoyos='18 hoyos'
                    ORDER BY r.puntos DESC
                """, (j['id'],))
                res_18h = cur.fetchall()

            mejores_9h  = [r['puntos'] for r in res_9h[:4]]
            mejores_18h = [r['puntos'] for r in res_18h[:8]]
            total_bruto = sum(r['puntos'] for r in res_9h) + sum(r['puntos'] for r in res_18h)
            jugadas     = len(res_9h) + len(res_18h)

            tiene_min = len(res_9h) >= 4 and (len(res_18h) >= 8 or len(res_18h) == 0)
            total_neto = (sum(mejores_9h) + sum(mejores_18h)) if tiene_min else None

            ranking.append({
                'jugador_id':  j['id'],
                'nombre':      j['nombre'],
                'hcp':         j['hcp'],
                'jugadas':     jugadas,
                'jugadas_9h':  len(res_9h),
                'jugadas_18h': len(res_18h),
                'total_bruto': total_bruto,
                'total_neto':  total_neto,
                'media':       round(total_bruto / jugadas, 2) if jugadas else 0,
                'mejor':       max([r['puntos'] for r in res_9h] + [r['puntos'] for r in res_18h], default=0),
            })

        ranking_bruto = sorted([r for r in ranking if r['jugadas'] > 0],
                               key=lambda x: (-x['total_bruto'], x['hcp']))
        ranking_neto  = sorted([r for r in ranking if r['total_neto'] is not None],
                               key=lambda x: (-x['total_neto'], x['hcp']))
        return ranking_bruto, ranking_neto


def get_partidas():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, COUNT(r.id) as num_jugadores
                FROM partidas p
                LEFT JOIN resultados r ON r.partida_id = p.id
                GROUP BY p.id ORDER BY p.fecha DESC
            """)
            return cur.fetchall()


def get_partida(partida_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM partidas WHERE id=%s", (partida_id,))
            p = cur.fetchone()
            cur.execute("""
                SELECT r.*, j.nombre, j.hcp as hcp_actual
                FROM resultados r
                JOIN jugadores j ON j.id = r.jugador_id
                WHERE r.partida_id=%s ORDER BY r.posicion
            """, (partida_id,))
            rs = cur.fetchall()
        return p, rs


def get_jugadores():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM jugadores ORDER BY hcp ASC")
            return cur.fetchall()


def add_jugador(nombre, hcp):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO jugadores (nombre, hcp) VALUES (%s,%s)", (nombre, hcp))
        conn.commit()


def update_jugador(jugador_id, nombre, hcp):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE jugadores SET nombre=%s, hcp=%s WHERE id=%s", (nombre, hcp, jugador_id))
        conn.commit()


def delete_jugador(jugador_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jugadores WHERE id=%s", (jugador_id,))
        conn.commit()


def add_partida(semana, fecha, campo, hoyos, es_major, notas, resultados_data):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO partidas (semana,fecha,campo,hoyos,es_major,notas) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (semana or None, fecha, campo, hoyos, 1 if es_major else 0, notas)
            )
            partida_id = cur.fetchone()[0]
            for jugador_id, stableford in resultados_data:
                cur.execute("SELECT hcp FROM jugadores WHERE id=%s", (jugador_id,))
                hcp = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO resultados (partida_id,jugador_id,hcp,stableford) VALUES (%s,%s,%s,%s)",
                    (partida_id, jugador_id, hcp, stableford)
                )
        conn.commit()
    calcular_posicion_y_puntos(partida_id)
    return partida_id


def delete_partida(partida_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM partidas WHERE id=%s", (partida_id,))
        conn.commit()


def get_historial_jugador(jugador_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT r.*, p.fecha, p.campo, p.hoyos, p.es_major, p.semana
                FROM resultados r
                JOIN partidas p ON p.id = r.partida_id
                WHERE r.jugador_id=%s ORDER BY p.fecha DESC
            """, (jugador_id,))
            return cur.fetchall()
