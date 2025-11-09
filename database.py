import sqlite3
from datetime import datetime

DATABASE = 'academico.db'

def get_db_connection():
    """Establece conexión con la base de datos"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa la base de datos con las tablas necesarias"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla estudiantes (sin carrera, ahora con curso)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estudiantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_estudiante TEXT UNIQUE NOT NULL,
            cedula TEXT NOT NULL,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            curso TEXT NOT NULL,
            email TEXT NOT NULL,
            estado_matricula TEXT DEFAULT 'no_matriculado',
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla proformas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proformas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_proforma TEXT UNIQUE NOT NULL,
            id_estudiante INTEGER NOT NULL,
            codigo_estudiante TEXT NOT NULL,
            curso TEXT NOT NULL,
            monto REAL NOT NULL,
            fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado TEXT DEFAULT 'pendiente',
            FOREIGN KEY (id_estudiante) REFERENCES estudiantes(id)
        )
    ''')
    
    # Tabla asignaturas (asignaturas disponibles por curso)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asignaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            curso TEXT NOT NULL,
            descripcion TEXT
        )
    ''')
    
    # Tabla relacional: asignaturas seleccionadas en cada proforma
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proforma_asignaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_proforma INTEGER NOT NULL,
            id_asignatura INTEGER NOT NULL,
            nombre_asignatura TEXT NOT NULL,
            FOREIGN KEY (id_proforma) REFERENCES proformas(id),
            FOREIGN KEY (id_asignatura) REFERENCES asignaturas(id)
        )
    ''')
    
    conn.commit()
    
    # Insertar asignaturas por defecto si no existen
    insertar_asignaturas_default(conn)
    
    conn.close()
    print("✅ Base de datos inicializada correctamente")

def insertar_asignaturas_default(conn):
    """Inserta asignaturas por defecto para cada curso"""
    cursor = conn.cursor()
    
    # Verificar si ya existen asignaturas
    cursor.execute('SELECT COUNT(*) as total FROM asignaturas')
    if cursor.fetchone()['total'] > 0:
        return
    
    asignaturas = [
        # Primer Curso
        ('Matemáticas I', 'Primer Curso', 'Fundamentos de álgebra y cálculo'),
        ('Lenguaje y Comunicación', 'Primer Curso', 'Gramática y redacción'),
        ('Ciencias Naturales', 'Primer Curso', 'Biología y química básica'),
        ('Estudios Sociales', 'Primer Curso', 'Historia y geografía'),
        ('Inglés Básico', 'Primer Curso', 'Inglés nivel principiante'),
        
        # Segundo Curso
        ('Matemáticas II', 'Segundo Curso', 'Geometría y trigonometría'),
        ('Literatura', 'Segundo Curso', 'Análisis literario'),
        ('Física', 'Segundo Curso', 'Mecánica y termodinámica'),
        ('Química', 'Segundo Curso', 'Química orgánica e inorgánica'),
        ('Inglés Intermedio', 'Segundo Curso', 'Inglés nivel intermedio'),
        
        # Tercer Curso
        ('Cálculo Avanzado', 'Tercer Curso', 'Cálculo diferencial e integral'),
        ('Programación', 'Tercer Curso', 'Fundamentos de programación'),
        ('Física Avanzada', 'Tercer Curso', 'Electromagnetismo y óptica'),
        ('Estadística', 'Tercer Curso', 'Probabilidad y estadística'),
        ('Inglés Avanzado', 'Tercer Curso', 'Inglés nivel avanzado'),
    ]
    
    cursor.executemany('''
        INSERT INTO asignaturas (nombre, curso, descripcion)
        VALUES (?, ?, ?)
    ''', asignaturas)
    
    conn.commit()
    print("✅ Asignaturas por defecto insertadas")

def generar_numero_proforma():
    """Genera un número de proforma único (formato: PROF-YYYYMMDD-XXXX)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fecha_actual = datetime.now().strftime('%Y%m%d')
    
    cursor.execute('''
        SELECT COUNT(*) as total FROM proformas 
        WHERE numero_proforma LIKE ?
    ''', (f'PROF-{fecha_actual}-%',))
    
    total = cursor.fetchone()['total']
    numero_secuencial = str(total + 1).zfill(4)
    
    conn.close()
    
    return f'PROF-{fecha_actual}-{numero_secuencial}'

def obtener_precio_curso(curso):
    """Retorna el precio según el curso"""
    precios = {
        'Primer Curso': 300.00,
        'Segundo Curso': 340.00,
        'Tercer Curso': 450.00
    }
    return precios.get(curso, 0.00)

if __name__ == '__main__':
    init_db()