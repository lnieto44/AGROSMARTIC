import os
import requests

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'agrosmart_secret'

# Configuración de la API de OpenWeatherMap
API_KEY = "0a64ba73c0802da4dcf17504d0b8b53b"  # Sustituir por tu clave real
BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"

# Función para conectar a la base de datos
def conectar_db():
    conn = sqlite3.connect("database.db")
    return conn

# Crear tablas si no existen
def init_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            contraseña TEXT NOT NULL
        )
    ''')
    # Crear tabla de cultivos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cultivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre_cultivo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            tipo_producto TEXT NOT NULL,
            parcela TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Crear tabla alertas (si no existe)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cultivo_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            fecha DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (cultivo_id) REFERENCES cultivos (id)
        )
    ''')

    # Crear tabla demanda (si no existe)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS demanda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_producto TEXT NOT NULL,
            region TEXT NOT NULL,
            recomendaciones TEXT NOT NULL
        )
    ''')
    # Tabla para registrar tráfico
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trafico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE DEFAULT CURRENT_DATE,
            hora TIME DEFAULT CURRENT_TIME,
            ip TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

#generar alertas
def generar_alertas():
    conn = conectar_db()
    cursor = conn.cursor()
    hoy = datetime.now()
    proximos_7_dias = hoy + timedelta(days=7)

    # Seleccionar cultivos cuya cosecha está cerca
    cursor.execute(
        "SELECT id, nombre_cultivo, fecha_cosecha, parcela FROM cultivos WHERE fecha_cosecha BETWEEN ? AND ?",
        (hoy.date(), proximos_7_dias.date())
    )
    cultivos = cursor.fetchall()

    for cultivo in cultivos:
        cultivo_id, nombre_cultivo, fecha_cosecha, parcela = cultivo

        # Obtener datos climáticos
        params = {
            "q": parcela,  # Cambiar a la ubicación del cultivo
            "appid": API_KEY,
            "units": "metric",
            "cnt": 7
        }
        try:
            respuesta = requests.get(BASE_URL, params=params)
            datos_clima = respuesta.json()

            for dia in datos_clima["list"]:
                fecha_clima = datetime.fromtimestamp(dia["dt"]).date()
                if fecha_clima == datetime.strptime(fecha_cosecha, "%Y-%m-%d").date():
                    clima = dia["weather"][0]["main"]
                    mensaje = f"Cuidado: Se espera {clima} el día de la cosecha del cultivo {nombre_cultivo}."
                    
                    # Guardar alerta en la base de datos
                    cursor.execute(
                        "INSERT INTO alertas (cultivo_id, tipo, mensaje) VALUES (?, ?, ?)",
                        (cultivo_id, "Climática", mensaje)
                    )
                    break
        except Exception as e:
            print(f"Error al obtener datos climáticos: {e}")

    conn.commit()
    conn.close()


@app.route('/demanda', methods=['GET', 'POST'])
def demanda():
    resultados = []
    mensaje = None

    if request.method == 'POST':
        region = request.form['region']  # Región seleccionada por el usuario
        conn = conectar_db()
        cursor = conn.cursor()

        # Consultar datos de la tabla demanda para la región seleccionada
        cursor.execute('''
            SELECT tipo_producto, region, recomendaciones
            FROM demanda
            WHERE region = ?
        ''', (region,))
        resultados = cursor.fetchall()

        if not resultados:
            mensaje = "No hay demandas registradas para esta región."

        conn.close()

    return render_template('demanda.html', resultados=resultados, mensaje=mensaje)

def insertar_datos_prueba():
    conn = conectar_db()
    cursor = conn.cursor()
    
    datos_demanda = [
        ("Maíz", "Andina", "Sembrar entre abril y junio. Riego moderado."),
        ("Arroz", "Caribe", "Sembrar en temporada de lluvias. Evitar suelos con alta salinidad."),
        ("Café", "Orinoquía", "Evitar heladas. Altitud ideal entre 1200 y 1800 metros.")
    ]

    for tipo_producto, region, recomendaciones in datos_demanda:
        cursor.execute('''
            INSERT OR IGNORE INTO demanda (tipo_producto, region, recomendaciones)
            VALUES (?, ?, ?)
        ''', (tipo_producto, region, recomendaciones))
    
    conn.commit()
    conn.close()



# calendadrio de cosecha
@app.route("/calendario")
def calendario():
    if "usuario_id" not in session:
        flash("Por favor, inicia sesión para acceder al calendario.", "danger")
        return redirect(url_for("login"))

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_cultivo, fecha_cosecha FROM cultivos WHERE usuario_id = ?", (session["usuario_id"],))
    cosechas = cursor.fetchall()
    conn.close()
    return render_template("calendario.html", cosechas=cosechas)

@app.route("/productos")
def productos():
    if "usuario_id" not in session:
        flash("Por favor, inicia sesión para acceder a los productos.", "danger")
        return redirect(url_for("login"))

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.nombre_cultivo, c.tipo_producto, c.cantidad, c.fecha_cosecha, d.region, d.recomendaciones
        FROM cultivos c
        LEFT JOIN demanda d ON c.tipo_producto = d.tipo_producto
        WHERE c.usuario_id = ?
    ''', (session["usuario_id"],))
    productos = cursor.fetchall()
    conn.close()
    return render_template("productos.html", productos=productos)


# Ruta principal
@app.route("/")
def home():
    return render_template("index.html")

# Ruta de registro
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        email = request.form.get("email")
        contraseña = request.form.get("contraseña")

        if not nombre or not email or not contraseña:
            return render_template(
                "registro.html",
                mensaje="Por favor, completa todos los campos.",
                tipo="error"
            )

        contraseña_cifrada = generate_password_hash(contraseña)

        conn = conectar_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO usuarios (nombre, email, contraseña) VALUES (?, ?, ?)",
                (nombre, email, contraseña_cifrada),
            )
            conn.commit()
            return render_template(
                "registro.html",
                mensaje="Registro exitoso. Por favor, inicia sesión.",
                tipo="success"
            )
        except sqlite3.IntegrityError:
            return render_template(
                "registro.html",
                mensaje="El correo electrónico ya está registrado.",
                tipo="error"
            )
        finally:
            conn.close()

    return render_template("registro.html")


# Ruta de inicio de sesión

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        contraseña = request.form.get("contraseña")

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
        usuario = cursor.fetchone()

        if usuario and check_password_hash(usuario[3], contraseña):
            # Iniciar sesión del usuario
            session["usuario_id"] = usuario[0]
            session["nombre"] = usuario[1]

            # Registrar visita en la tabla trafico
            ip_usuario = request.remote_addr  # Dirección IP del usuario
            cursor.execute(
                "INSERT INTO trafico (ip) VALUES (?)",
                (ip_usuario,)
            )
            conn.commit()

            flash(f"Bienvenido, {usuario[1]}!", "success")
            conn.close()
            return redirect(url_for("dashboard"))

        else:
            flash("Correo o contraseña incorrectos.", "danger")

    return render_template("login.html")

@app.route("/analitica")
def analitica():
    if "usuario_id" not in session:
        flash("Por favor, inicia sesión para acceder a la analítica.", "danger")
        return redirect(url_for("login"))

    conn = conectar_db()
    cursor = conn.cursor()

    # Total de visitas
    cursor.execute("SELECT COUNT(*) FROM trafico")
    total_visitas = cursor.fetchone()[0]

    # Visitas por día
    cursor.execute('''
        SELECT fecha, COUNT(*) as visitas
        FROM trafico
        GROUP BY fecha
        ORDER BY fecha DESC
        LIMIT 7
    ''')
    visitas_por_dia = cursor.fetchall()

    conn.close()

    return render_template("analitica.html", total_visitas=total_visitas, visitas_por_dia=visitas_por_dia)


# Ruta del Dashboard
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "usuario_id" not in session:
        flash("Por favor, inicia sesión para acceder al panel.", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        nombre_cultivo = request.form.get("nombre_cultivo")
        cantidad = request.form.get("cantidad")
        tipo_producto = request.form.get("tipo_producto")
        parcela = request.form.get("parcela")

        if not nombre_cultivo or not cantidad or not tipo_producto or not parcela:
            flash("Todos los campos son obligatorios.", "danger")
            return redirect(url_for("dashboard"))

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cultivos (usuario_id, nombre_cultivo, cantidad, tipo_producto, parcela) VALUES (?, ?, ?, ?, ?)",
            (session["usuario_id"], nombre_cultivo, cantidad, tipo_producto, parcela),
        )
        conn.commit()
        conn.close()
        flash("Cultivo registrado con éxito.", "success")
        return redirect(url_for("dashboard"))

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nombre_cultivo, cantidad, tipo_producto, parcela FROM cultivos WHERE usuario_id = ?",
        (session["usuario_id"],),
    )
    cultivos = cursor.fetchall()
    conn.close()
    return render_template("dashboard.html", nombre=session["nombre"], cultivos=cultivos)

# Ruta para cerrar sesión
@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada exitosamente.", "info")
    return redirect(url_for("home"))


@app.route('/alertas')
def alertas():
    if "usuario_id" not in session:
        flash("Por favor, inicia sesión para acceder a las alertas.", "danger")
        return redirect(url_for("login"))

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.tipo, a.mensaje, a.fecha, c.nombre_cultivo
        FROM alertas a
        JOIN cultivos c ON a.cultivo_id = c.id
        WHERE c.usuario_id = ?
    ''', (session["usuario_id"],))
    alertas = cursor.fetchall()
    conn.close()

    return render_template('alertas.html', alertas=alertas)



@app.route('/contactanos')
def contactanos():
    return render_template('contactanos.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/quienes_somos')
def quienes_somos():
    return render_template('quienes_somos.html')

if __name__ == "__main__":
    init_db()  # Inicializar la base de datos
    insertar_datos_prueba() #INSERTAR DATOS
    app.run(debug=True)