from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
import requests
from database import get_db_connection, init_db, generar_numero_proforma, obtener_precio_curso
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui_cambiala'
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# URL del Sistema Contable
SISTEMA_CONTABLE_URL = 'http://192.168.0.14:5001'

# Inicializar BD al arrancar
init_db()

# ========== RUTAS PARA LA INTERFAZ WEB ==========

@app.route('/')
def index():
    """Página principal"""
    conn = get_db_connection()
    estudiantes = conn.execute('SELECT * FROM estudiantes ORDER BY fecha_registro DESC').fetchall()
    proformas = conn.execute('''
        SELECT p.*, e.nombre, e.apellido 
        FROM proformas p 
        JOIN estudiantes e ON p.id_estudiante = e.id 
        ORDER BY p.fecha_generacion DESC
    ''').fetchall()
    conn.close()
    
    return render_template('index.html', estudiantes=estudiantes, proformas=proformas)

@app.route('/registro')
def registro():
    """Formulario de registro de estudiante"""
    return render_template('registro.html')

@app.route('/estudiantes', methods=['POST'])
def crear_estudiante():
    """Registrar nuevo estudiante (SIN generar proforma automáticamente)"""
    try:
        codigo_estudiante = request.form['codigo_estudiante']
        cedula = request.form['cedula']
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        curso = request.form['curso']
        email = request.form['email']
        
        conn = get_db_connection()
        
        # Verificar si el código ya existe
        existe = conn.execute(
            'SELECT id FROM estudiantes WHERE codigo_estudiante = ?', 
            (codigo_estudiante,)
        ).fetchone()
        
        if existe:
            flash('❌ El código de estudiante ya existe', 'error')
            conn.close()
            return redirect(url_for('registro'))
        
        # Insertar estudiante
        conn.execute('''
            INSERT INTO estudiantes (codigo_estudiante, cedula, nombre, apellido, curso, email)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (codigo_estudiante, cedula, nombre, apellido, curso, email))
        
        conn.commit()
        conn.close()
        
        flash(f'✅ Estudiante {nombre} {apellido} registrado exitosamente. Ahora puede generar su proforma.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'❌ Error al registrar estudiante: {str(e)}', 'error')
        return redirect(url_for('registro'))

@app.route('/generar-proforma')
def formulario_proforma():
    """Formulario para que el estudiante genere su proforma"""
    conn = get_db_connection()
    
    # Obtener estudiantes que NO tienen proforma pendiente o pagada
    estudiantes = conn.execute('''
        SELECT e.* FROM estudiantes e
        WHERE e.estado_matricula = 'no_matriculado'
        AND NOT EXISTS (
            SELECT 1 FROM proformas p 
            WHERE p.id_estudiante = e.id 
            AND p.estado = 'pendiente'
        )
        ORDER BY e.fecha_registro DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('generar_proforma.html', estudiantes=estudiantes)

@app.route('/obtener-asignaturas/<curso>')
def obtener_asignaturas(curso):
    """API para obtener asignaturas según el curso seleccionado"""
    conn = get_db_connection()
    asignaturas = conn.execute(
        'SELECT * FROM asignaturas WHERE curso = ?',
        (curso,)
    ).fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in asignaturas])

@app.route('/proformas', methods=['POST'])
def crear_proforma():
    """Generar proforma con asignaturas seleccionadas"""
    try:
        id_estudiante = request.form['id_estudiante']
        asignaturas_ids = request.form.getlist('asignaturas[]')
        
        if not asignaturas_ids:
            flash('❌ Debe seleccionar al menos una asignatura', 'error')
            return redirect(url_for('formulario_proforma'))
        
        conn = get_db_connection()
        
        # Obtener datos del estudiante
        estudiante = conn.execute(
            'SELECT * FROM estudiantes WHERE id = ?',
            (id_estudiante,)
        ).fetchone()
        
        if not estudiante:
            flash('❌ Estudiante no encontrado', 'error')
            conn.close()
            return redirect(url_for('formulario_proforma'))
        
        # Obtener precio según el curso
        monto = obtener_precio_curso(estudiante['curso'])
        numero_proforma = generar_numero_proforma()
        
        # Insertar proforma
        cursor = conn.execute('''
            INSERT INTO proformas (numero_proforma, id_estudiante, codigo_estudiante, curso, monto)
            VALUES (?, ?, ?, ?, ?)
        ''', (numero_proforma, id_estudiante, estudiante['codigo_estudiante'], estudiante['curso'], monto))
        
        id_proforma = cursor.lastrowid
        
        # Insertar asignaturas seleccionadas
        for asignatura_id in asignaturas_ids:
            asignatura = conn.execute(
                'SELECT * FROM asignaturas WHERE id = ?',
                (asignatura_id,)
            ).fetchone()
            
            conn.execute('''
                INSERT INTO proforma_asignaturas (id_proforma, id_asignatura, nombre_asignatura)
                VALUES (?, ?, ?)
            ''', (id_proforma, asignatura['id'], asignatura['nombre']))
        
        conn.commit()
        conn.close()
        
        # ========== COMUNICACIÓN CON SISTEMA CONTABLE ==========
        print("=" * 70)
        print(f"🔄 INICIANDO COMUNICACIÓN CON SISTEMA CONTABLE")
        print(f"📍 URL: {SISTEMA_CONTABLE_URL}/api/pagos/registrar-proforma")
        
        datos_enviar = {
            'numero_proforma': numero_proforma,
            'codigo_estudiante': estudiante['codigo_estudiante'],
            'nombre_completo': f"{estudiante['nombre']} {estudiante['apellido']}",
            'curso': estudiante['curso'],
            'monto': monto
        }
        print(f"📦 Datos a enviar: {datos_enviar}")
        
        try:
            response = requests.post(
                f'{SISTEMA_CONTABLE_URL}/api/pagos/registrar-proforma',
                json=datos_enviar,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            print(f"✅ Código de respuesta: {response.status_code}")
            print(f"📄 Respuesta: {response.text}")
            print("=" * 70)
            
            if response.status_code == 200:
                flash(f'✅ Proforma {numero_proforma} generada exitosamente y notificada a contabilidad', 'success')
            else:
                flash(f'✅ Proforma {numero_proforma} generada, pero hubo un problema al notificar a contabilidad', 'warning')
                
        except requests.exceptions.ConnectionError:
            print(f"❌ ERROR DE CONEXIÓN")
            print("=" * 70)
            flash(f'⚠️ Proforma {numero_proforma} generada, pero no se pudo conectar con el sistema contable', 'warning')
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            print("=" * 70)
            flash(f'⚠️ Proforma {numero_proforma} generada, pero hubo un error al notificar: {str(e)}', 'warning')
        
        return redirect(url_for('ver_proforma', numero_proforma=numero_proforma))
        
    except Exception as e:
        flash(f'❌ Error al generar proforma: {str(e)}', 'error')
        return redirect(url_for('formulario_proforma'))

@app.route('/proforma/<numero_proforma>')
def ver_proforma(numero_proforma):
    """Ver detalles de una proforma con sus asignaturas"""
    conn = get_db_connection()
    
    proforma = conn.execute('''
        SELECT p.*, e.nombre, e.apellido, e.cedula, e.curso, e.email
        FROM proformas p
        JOIN estudiantes e ON p.id_estudiante = e.id
        WHERE p.numero_proforma = ?
    ''', (numero_proforma,)).fetchone()
    
    if not proforma:
        flash('❌ Proforma no encontrada', 'error')
        conn.close()
        return redirect(url_for('index'))
    
    # Obtener asignaturas de la proforma
    asignaturas = conn.execute('''
        SELECT pa.nombre_asignatura, a.descripcion
        FROM proforma_asignaturas pa
        LEFT JOIN asignaturas a ON pa.id_asignatura = a.id
        WHERE pa.id_proforma = ?
    ''', (proforma['id'],)).fetchall()
    
    conn.close()
    
    return render_template('ver_proforma.html', proforma=proforma, asignaturas=asignaturas)

# ========== API PARA COMUNICACIÓN CON SISTEMA CONTABLE ==========

@app.route('/api/estudiantes/<int:id>/matricular', methods=['PUT'])
def matricular_estudiante(id):
    """
    Endpoint para que el Sistema Contable actualice el estado de matrícula
    cuando se registre un pago
    """
    try:
        data = request.get_json()
        numero_proforma = data.get('numero_proforma')
        numero_comprobante = data.get('numero_comprobante')
        
        if not numero_proforma or not numero_comprobante:
            return jsonify({'error': 'Faltan datos requeridos'}), 400
        
        conn = get_db_connection()
        
        # Verificar que la proforma existe y está pendiente
        proforma = conn.execute(
            'SELECT * FROM proformas WHERE id_estudiante = ? AND numero_proforma = ? AND estado = "pendiente"',
            (id, numero_proforma)
        ).fetchone()
        
        if not proforma:
            conn.close()
            return jsonify({'error': 'Proforma no encontrada o ya procesada'}), 404
        
        # Actualizar estado del estudiante a matriculado
        conn.execute(
            'UPDATE estudiantes SET estado_matricula = "matriculado" WHERE id = ?',
            (id,)
        )
        
        # Actualizar estado de la proforma
        conn.execute(
            'UPDATE proformas SET estado = "pagado" WHERE id = ?',
            (proforma['id'],)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'mensaje': 'Estudiante matriculado exitosamente',
            'id_estudiante': id,
            'numero_proforma': numero_proforma,
            'numero_comprobante': numero_comprobante
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proformas/<numero_proforma>', methods=['GET'])
def consultar_proforma(numero_proforma):
    """Consultar información de una proforma"""
    try:
        conn = get_db_connection()
        proforma = conn.execute('''
            SELECT p.*, e.nombre, e.apellido, e.cedula, e.curso 
            FROM proformas p
            JOIN estudiantes e ON p.id_estudiante = e.id
            WHERE p.numero_proforma = ?
        ''', (numero_proforma,)).fetchone()
        conn.close()
        
        if not proforma:
            return jsonify({'error': 'Proforma no encontrada'}), 404
        
        return jsonify(dict(proforma)), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)