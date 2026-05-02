#!/bin/bash
cd "$(dirname "$0")"

# Instalar dependencias si faltan
pip3 install flask openpyxl --quiet 2>/dev/null

# Importar Excel si la BD está vacía
python3 -c "
import database as db; db.init_db()
import sqlite3; conn = sqlite3.connect('golf.db')
n = conn.execute('SELECT COUNT(*) FROM jugadores').fetchone()[0]
conn.close()
if n == 0:
    print('Importando datos del Excel...')
    import import_excel; import_excel.run()
"

echo ""
echo "============================================"
echo "  Golf Guadalmina 2026"
echo "============================================"
python3 -c "import socket; s=socket.socket(); s.connect(('8.8.8.8',80)); ip=s.getsockname()[0]; s.close(); print(f'  Local:  http://localhost:5001'); print(f'  Móvil:  http://{ip}:5001')" 2>/dev/null || echo "  http://localhost:5001"
echo ""
echo "  Para acceder desde el móvil, conecta al"
echo "  mismo WiFi y usa la URL de Móvil."
echo "============================================"
echo ""

python3 app.py
