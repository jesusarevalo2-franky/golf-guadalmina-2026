from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import database as db
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'golf-guadalmina-2026'


# ── Template filters ───────────────────────────────────────────────────────────

@app.template_filter('format_pts')
def format_pts(v):
    if v is None:
        return '—'
    return str(int(v)) if v == int(v) else str(v)


@app.template_filter('format_fecha')
def format_fecha(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').strftime('%d %b %Y')
    except Exception:
        return s


# ── DB init ────────────────────────────────────────────────────────────────────

@app.before_request
def ensure_db():
    db.init_db()


# ── Ranking ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('ranking'))


@app.route('/ranking')
def ranking():
    ranking_bruto, ranking_neto = db.get_ranking()
    return render_template('ranking.html',
                           ranking_bruto=ranking_bruto,
                           ranking_neto=ranking_neto)


# ── Partidas ───────────────────────────────────────────────────────────────────

@app.route('/partidas')
def partidas():
    lista = db.get_partidas()
    return render_template('partidas.html', partidas=lista)


@app.route('/partidas/<int:partida_id>')
def ver_partida(partida_id):
    partida, resultados = db.get_partida(partida_id)
    if not partida:
        flash('Partida no encontrada', 'danger')
        return redirect(url_for('partidas'))
    return render_template('ver_partida.html', partida=partida, resultados=resultados)


@app.route('/partidas/nueva', methods=['GET', 'POST'])
def nueva_partida():
    jugadores = [dict(j) for j in db.get_jugadores()]
    if request.method == 'POST':
        semana  = request.form.get('semana') or None
        fecha   = request.form.get('fecha')
        campo   = request.form.get('campo', 'Guadalmina Norte')
        hoyos   = request.form.get('hoyos')
        major   = 'es_major' in request.form
        notas   = request.form.get('notas', '')

        jugador_ids = request.form.getlist('jugador_id[]')
        stablefords = request.form.getlist('stableford[]')

        resultados_data = []
        seen_ids = set()
        for jid, sf in zip(jugador_ids, stablefords):
            if jid and sf and jid not in seen_ids:
                try:
                    resultados_data.append((int(jid), int(sf)))
                    seen_ids.add(jid)
                except ValueError:
                    pass

        if not fecha or not hoyos or len(resultados_data) < 2:
            flash('Completa todos los campos y añade al menos 2 jugadores.', 'warning')
        else:
            pid = db.add_partida(semana, fecha, campo, hoyos, major, notas, resultados_data)
            flash('Partida registrada correctamente.', 'success')
            return redirect(url_for('ver_partida', partida_id=pid))

    return render_template('nueva_partida.html', jugadores=jugadores)


@app.route('/partidas/<int:partida_id>/eliminar', methods=['POST'])
def eliminar_partida(partida_id):
    db.delete_partida(partida_id)
    flash('Partida eliminada.', 'info')
    return redirect(url_for('partidas'))


# ── Jugadores ──────────────────────────────────────────────────────────────────

@app.route('/jugadores')
def jugadores():
    lista = db.get_jugadores()
    return render_template('jugadores.html', jugadores=lista)


@app.route('/jugadores/nuevo', methods=['POST'])
def nuevo_jugador():
    nombre = request.form.get('nombre', '').strip()
    hcp    = request.form.get('hcp', '')
    try:
        hcp = float(hcp)
    except ValueError:
        flash('HCP inválido.', 'danger')
        return redirect(url_for('jugadores'))
    if not nombre:
        flash('El nombre no puede estar vacío.', 'danger')
        return redirect(url_for('jugadores'))
    try:
        db.add_jugador(nombre, hcp)
        flash(f'Jugador {nombre} añadido.', 'success')
    except Exception:
        flash('El jugador ya existe o hubo un error.', 'danger')
    return redirect(url_for('jugadores'))


@app.route('/jugadores/<int:jugador_id>/editar', methods=['POST'])
def editar_jugador(jugador_id):
    nombre = request.form.get('nombre', '').strip()
    hcp    = request.form.get('hcp', '')
    try:
        hcp = float(hcp)
    except ValueError:
        flash('HCP inválido.', 'danger')
        return redirect(url_for('jugadores'))
    db.update_jugador(jugador_id, nombre, hcp)
    flash('Jugador actualizado.', 'success')
    return redirect(url_for('jugadores'))


@app.route('/jugadores/<int:jugador_id>/eliminar', methods=['POST'])
def eliminar_jugador(jugador_id):
    db.delete_jugador(jugador_id)
    flash('Jugador eliminado.', 'info')
    return redirect(url_for('jugadores'))


@app.route('/jugadores/<int:jugador_id>')
def perfil_jugador(jugador_id):
    lista = db.get_jugadores()
    jugador = next((j for j in lista if j['id'] == jugador_id), None)
    if not jugador:
        flash('Jugador no encontrado.', 'danger')
        return redirect(url_for('jugadores'))
    historial = db.get_historial_jugador(jugador_id)
    return render_template('perfil_jugador.html', jugador=jugador, historial=historial)


# ── API ────────────────────────────────────────────────────────────────────────

@app.route('/api/ranking')
def api_ranking():
    rb, rn = db.get_ranking()
    return jsonify({'bruto': [dict(r) for r in rb], 'neto': [dict(r) for r in rn]})


if __name__ == '__main__':
    db.init_db()
    # Escucha en todas las interfaces para acceso desde móvil en la misma red WiFi
    app.run(debug=False, host='0.0.0.0', port=5001)
