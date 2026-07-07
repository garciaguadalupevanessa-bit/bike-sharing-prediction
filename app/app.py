import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import base64
import joblib
import json
import re
import hashlib
import secrets
import math
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import calendar
import folium
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from branca.element import Element
from streamlit_folium import st_folium


load_dotenv()
API_KEY = os.getenv("AEMET_API_KEY")
CLAVE_EMPLEADO_GESTION = os.getenv("CLAVE_EMPLEADO_GESTION") or "1234"


st.set_page_config(page_title="BiciMAD Predictor", page_icon="🚴", layout="wide")


# --- FONDO Y ESTILOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USUARIOS_GESTION_PATH = Path(BASE_DIR).parent / "data" / "usuarios_gestion.json"
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_HELP = "Mínimo 6 caracteres, al menos una letra, una mayúscula y un número."
PASSWORD_HASHER = PasswordHasher()


def normalizar_email(email):
    return email.strip().lower()


def cargar_usuarios_gestion():
    if not USUARIOS_GESTION_PATH.exists():
        return {"usuarios": {}}

    try:
        with open(USUARIOS_GESTION_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"usuarios": {}}

    if not isinstance(datos, dict) or not isinstance(datos.get("usuarios"), dict):
        return {"usuarios": {}}

    return datos


def guardar_usuarios_gestion(datos):
    USUARIOS_GESTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USUARIOS_GESTION_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)


def validar_email(email):
    return bool(EMAIL_REGEX.match(normalizar_email(email)))


def validar_password(password):
    errores = []

    if len(password) < 6:
        errores.append("La contraseña debe tener al menos 6 caracteres.")
    if not any(c.isalpha() for c in password):
        errores.append("La contraseña debe incluir al menos una letra.")
    if not any(c.isupper() for c in password):
        errores.append("La contraseña debe incluir al menos una mayúscula.")
    if not any(c.isdigit() for c in password):
        errores.append("La contraseña debe incluir al menos un número.")

    return errores


def hash_codigo_recuperacion(codigo):
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def registrar_usuario_gestion(email, password, password_repetida, clave_empleado):
    email = normalizar_email(email)
    errores_password = validar_password(password)

    if not CLAVE_EMPLEADO_GESTION:
        return False, "Falta configurar CLAVE_EMPLEADO_GESTION en el archivo .env."
    if not validar_email(email):
        return False, "Introduce un correo válido con @ y punto."
    if password != password_repetida:
        return False, "Las contraseñas no coinciden."
    if errores_password:
        return False, " ".join(errores_password)
    if not secrets.compare_digest(clave_empleado, CLAVE_EMPLEADO_GESTION):
        return False, "La clave empleado no es correcta."

    datos = cargar_usuarios_gestion()
    if email in datos["usuarios"]:
        return False, "Ya existe una cuenta de gestión con ese correo."

    datos["usuarios"][email] = {
        "password_hash": PASSWORD_HASHER.hash(password),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "reset_token_hash": None,
        "reset_expires_at": None,
    }
    guardar_usuarios_gestion(datos)
    return True, "Cuenta de gestión creada correctamente."


def verificar_usuario_gestion(email, password):
    email = normalizar_email(email)

    if not validar_email(email):
        return False, "Introduce un correo válido con @ y punto."

    datos = cargar_usuarios_gestion()
    usuario = datos["usuarios"].get(email)
    if not usuario:
        return False, "Correo o contraseña incorrectos."

    try:
        PASSWORD_HASHER.verify(usuario["password_hash"], password)
    except (InvalidHashError, VerificationError, VerifyMismatchError, KeyError):
        return False, "Correo o contraseña incorrectos."

    return True, "Sesión iniciada correctamente."


def generar_codigo_recuperacion(email):
    email = normalizar_email(email)

    if not validar_email(email):
        return False, "Introduce un correo válido con @ y punto.", None

    datos = cargar_usuarios_gestion()
    usuario = datos["usuarios"].get(email)
    if not usuario:
        return False, "No existe una cuenta de gestión con ese correo.", None

    codigo = str(secrets.randbelow(900000) + 100000)
    usuario["reset_token_hash"] = hash_codigo_recuperacion(codigo)
    usuario["reset_expires_at"] = (datetime.now() + timedelta(minutes=15)).isoformat(timespec="seconds")
    guardar_usuarios_gestion(datos)

    return True, "Código temporal generado. En la demo se muestra en pantalla.", codigo


def cambiar_password_con_codigo(email, codigo, password, password_repetida):
    email = normalizar_email(email)
    errores_password = validar_password(password)

    if not validar_email(email):
        return False, "Introduce un correo válido con @ y punto."
    if password != password_repetida:
        return False, "Las contraseñas no coinciden."
    if errores_password:
        return False, " ".join(errores_password)

    datos = cargar_usuarios_gestion()
    usuario = datos["usuarios"].get(email)
    if not usuario or not usuario.get("reset_token_hash") or not usuario.get("reset_expires_at"):
        return False, "Solicita primero un código de recuperación."

    try:
        expira = datetime.fromisoformat(usuario["reset_expires_at"])
    except ValueError:
        return False, "El código de recuperación no es válido."

    if datetime.now() > expira:
        usuario["reset_token_hash"] = None
        usuario["reset_expires_at"] = None
        guardar_usuarios_gestion(datos)
        return False, "El código ha caducado. Solicita uno nuevo."

    if not secrets.compare_digest(hash_codigo_recuperacion(codigo.strip()), usuario["reset_token_hash"]):
        return False, "El código de recuperación no es correcto."

    usuario["password_hash"] = PASSWORD_HASHER.hash(password)
    usuario["reset_token_hash"] = None
    usuario["reset_expires_at"] = None
    guardar_usuarios_gestion(datos)

    return True, "Contraseña actualizada correctamente."


def cerrar_sesion_gestion():
    st.session_state["gestion_autenticada"] = False
    st.session_state["gestion_email"] = None


def mostrar_acceso_gestion():
    st.markdown("### Acceso a Gestión BiciMAD")
    st.caption("La zona de gestión requiere cuenta de empleado.")

    tab_login, tab_registro, tab_recuperar = st.tabs(["Iniciar sesión", "Crear cuenta", "Recuperar contraseña"])

    with tab_login:
        with st.form("form_login_gestion"):
            email = st.text_input("Correo empleado")
            password = st.text_input("Contraseña", type="password")
            st.caption(PASSWORD_HELP)
            submit_login = st.form_submit_button("Entrar")

        if submit_login:
            ok, mensaje = verificar_usuario_gestion(email, password)
            if ok:
                st.session_state["gestion_autenticada"] = True
                st.session_state["gestion_email"] = normalizar_email(email)
                st.success(mensaje)
                st.rerun()
            else:
                st.error(mensaje)

    with tab_registro:
        with st.form("form_registro_gestion"):
            email = st.text_input("Correo empleado", key="registro_email")
            password = st.text_input("Crear contraseña", type="password", key="registro_password")
            st.caption(PASSWORD_HELP)
            password_repetida = st.text_input("Repetir contraseña", type="password", key="registro_password_repetida")
            clave_empleado = st.text_input("Clave empleado", type="password")
            submit_registro = st.form_submit_button("Crear cuenta")

        if submit_registro:
            ok, mensaje = registrar_usuario_gestion(email, password, password_repetida, clave_empleado)
            if ok:
                st.success(mensaje)
            else:
                st.error(mensaje)

    with tab_recuperar:
        with st.form("form_generar_codigo"):
            email_recuperacion = st.text_input("Correo empleado", key="recuperar_email")
            submit_codigo = st.form_submit_button("Generar código demo")

        if submit_codigo:
            ok, mensaje, codigo = generar_codigo_recuperacion(email_recuperacion)
            if ok:
                st.success(mensaje)
                st.code(codigo)
            else:
                st.error(mensaje)

        with st.form("form_cambiar_password"):
            email_cambio = st.text_input("Correo empleado", key="cambio_email")
            codigo = st.text_input("Código temporal")
            nueva_password = st.text_input("Nueva contraseña", type="password")
            st.caption(PASSWORD_HELP)
            nueva_password_repetida = st.text_input("Repetir nueva contraseña", type="password")
            submit_cambio = st.form_submit_button("Actualizar contraseña")

        if submit_cambio:
            ok, mensaje = cambiar_password_con_codigo(email_cambio, codigo, nueva_password, nueva_password_repetida)
            if ok:
                st.success(mensaje)
            else:
                st.error(mensaje)


@st.cache_data(show_spinner=False)
def cargar_imagen_base64(ruta_imagen, fecha_modificacion):
    with open(ruta_imagen, "rb") as f:
        return base64.b64encode(f.read()).decode()


def set_background(ruta_imagen):
    fecha_modificacion = os.path.getmtime(ruta_imagen)
    img_base64 = cargar_imagen_base64(ruta_imagen, fecha_modificacion)


    st.markdown(
        f"""
        <style>
        /* 1. BLINDAJE DEL FONDO */
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{img_base64}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-color: transparent !important;
        }}
        [data-testid="stHeader"], [data-testid="stMain"], .main {{
            background-color: transparent !important;
        }}
        :root {{
            color-scheme: light !important;
        }}

        /* 2. CONTENEDORES: fondo blanco translúcido, sin bordes ni sombras */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: rgba(255, 255, 255, 0.85) !important;
            border-radius: 12px !important;
            padding: 1rem !important;
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div,
        div[data-testid="stVerticalBlockBorderWrapper"] > div > div,
        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="column"],
        div[data-testid="stElementContainer"],
        div[data-testid="stForm"],
        div[data-testid="stForm"] > div {{
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
        }}

        /* 3. TEXTOS GENERALES Y ETIQUETAS */
        h1, h2, h3, h4, h5, h6, p, span, li {{
            color: #000000 !important;
        }}
        label, [data-testid="stWidgetLabel"] p {{
            color: #000000 !important;
            font-weight: bold !important;
            font-size: 18px !important;
        }}
        button[data-baseweb="tab"] p {{
            color: #000000 !important;
        }}
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{
            color: #000000 !important;
        }}

        /* 4. ALERTAS: color y tamaño de letra */
        div[data-testid="stNotification"] p,
        div[data-testid="stNotification"] span,
        div[data-testid="stNotification"] div,
        div.stAlert p,
        div.stAlert span,
        div.stAlert div {{
            color: #000000 !important;
            font-weight: bold !important;
            font-size: 18px !important;
        }}

        /* 4b. ALERTAS: ajustar ancho al contenido, no a toda la barra */
        div[data-testid="stNotification"],
        div.stAlert {{
            width: fit-content !important;
            max-width: 100% !important;
        }}

        /* 5. SELECTBOX: fondo blanco, tamaño y centrado */
        div[data-baseweb="select"] > div {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #d0d0d0 !important;
        }}
        div[data-baseweb="popover"] ul {{
            background-color: #ffffff !important;
            color: #000000 !important;
        }}
        div[data-testid="stSelectbox"], div[data-testid="stNumberInput"] {{
            max-width: 200px;
            margin-left: auto;
            margin-right: auto;
        }}

        /* 5c. CAMPOS DE TEXTO Y CONTRASEÑA: legibles en modo claro y oscuro */
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextInput"] input:focus,
        div[data-baseweb="input"] input,
        div[data-baseweb="input"] input:focus,
        input[type="text"],
        input[type="password"],
        textarea {{
            background-color: #ffffff !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            caret-color: #000000 !important;
            border-color: #d0d0d0 !important;
            font-size: 18px !important;
        }}
        div[data-testid="stTextInput"] input::placeholder,
        div[data-baseweb="input"] input::placeholder,
        textarea::placeholder {{
            color: #666666 !important;
            -webkit-text-fill-color: #666666 !important;
            opacity: 1 !important;
        }}
        div[data-baseweb="input"] > div {{
            background-color: #ffffff !important;
            border-color: #d0d0d0 !important;
        }}
        div[data-testid="stTextInput"] div[data-baseweb="input"],
        div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
        div[data-testid="stTextInput"] div[data-baseweb="input"] > div > div,
        div[data-testid="stTextInput"] div[data-baseweb="input"] span,
        div[data-testid="stTextInput"] div[data-baseweb="input"] button {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border-color: #d0d0d0 !important;
            box-shadow: none !important;
        }}
        div[data-baseweb="input"] button,
        div[data-baseweb="input"] button:hover,
        div[data-baseweb="input"] button:focus,
        div[data-baseweb="input"] [role="button"],
        div[data-baseweb="input"] svg {{
            background-color: #ffffff !important;
            color: #000000 !important;
            fill: #000000 !important;
            stroke: #000000 !important;
        }}

        /* 5b. BOTÓN DE ENVÍO DEL FORMULARIO */
        div[data-testid="stFormSubmitButton"] button,
        div[data-testid="stButton"] button {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #d0d0d0 !important;
            box-shadow: none !important;
            max-width: 200px;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }}
        div[data-testid="stFormSubmitButton"] button:hover,
        div[data-testid="stFormSubmitButton"] button:focus,
        div[data-testid="stButton"] button:hover,
        div[data-testid="stButton"] button:focus {{
            background-color: #f2f2f2 !important;
            color: #000000 !important;
            border-color: #a6a6a6 !important;
        }}
        div[data-testid="stFormSubmitButton"] button p,
        div[data-testid="stFormSubmitButton"] button span,
        div[data-testid="stButton"] button p,
        div[data-testid="stButton"] button span {{
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
        }}

        /* 6. TAMAÑO DE LETRA EN RESULTADOS (st.metric) */
        [data-testid="stMetricLabel"] p {{
            font-size: 22px !important;
        }}
        [data-testid="stMetricValue"] {{
            font-size: 42px !important;
        }}

        /* 7. SUBTÍTULO PRINCIPAL Y TÍTULO DEL MAPA: ajustados al texto */
        .subtitulo-app {{
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            background-color: rgba(255, 255, 255, 0.85) !important;
            border-radius: 8px !important;
            padding: 0.25rem 0.6rem !important;
            font-size: 20px !important;
            font-weight: 600 !important;
            display: inline-block;
            width: fit-content;
        }}
        .titulo-mapa {{
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            font-size: 20px !important;
            font-weight: 700 !important;
            display: inline-block;
            width: fit-content;
        }}

        /* 8. NUMBER INPUT: fondo blanco SOLO en la caja del número, etiqueta sin caja */
        div[data-testid="stNumberInput"] {{
            background-color: transparent !important;
        }}
        div[data-testid="stNumberInput"] > div {{
            background-color: #ffffff !important;
            border: 1px solid #d0d0d0 !important;
        }}
        div[data-testid="stNumberInput"] input {{
            background-color: #ffffff !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            caret-color: #000000 !important;
            font-size: 18px !important;
        }}
        div[data-testid="stNumberInput"] button {{
            background-color: #ffffff !important;
        }}

        /* 9. TEXTO INTERNO DE LOS SELECTBOX AL MISMO TAMAÑO QUE LAS ETIQUETAS */
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] div[data-baseweb="input"],
        div[data-baseweb="select"] span {{
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            font-size: 18px !important;
        }}
        div[data-baseweb="popover"] li {{
            color: #000000 !important;
            background-color: #ffffff !important;
            font-size: 18px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


ruta_fondo = os.path.join(BASE_DIR, "assets", "fondo_bicimad.png")
set_background(ruta_fondo)


st.title("🚴 BiciMAD Predictor")
st.markdown('<div class="subtitulo-app">Plataforma predictiva impulsada por Machine Learning.</div>', unsafe_allow_html=True)


# --- CARGAR EL MODELO ---
@st.cache_resource
def cargar_modelo():
    ruta = "models/modelo_final_definitivo_random_forest.joblib"
    if not os.path.exists(ruta):
        st.error(f"⚠️ No se encontró el archivo del modelo en: {ruta}")
        return None
    try:
        return joblib.load(ruta)
    except Exception as e:
        st.error(f"⚠️ Error al cargar el modelo: {e}")
        return None


modelo_rf = cargar_modelo()


# --- DATOS DE LAS ESTACIONES ---
estaciones_data = {
    "1 - Puerta del Sol A": {"id": 1, "lat": 40.4172137, "lon": -3.7018341, "capacity": 30},
    "2 - Puerta del Sol B": {"id": 2, "lat": 40.41731271011562, "lon": -3.701602938060457, "capacity": 30},
    "3 - Miguel Moya": {"id": 3, "lat": 40.4205886, "lon": -3.7058415, "capacity": 24},
    "4 - Plaza Conde Suchil": {"id": 4, "lat": 40.4302937, "lon": -3.7069171, "capacity": 18},
    "5 - Malasaña": {"id": 5, "lat": 40.4285524, "lon": -3.7025875, "capacity": 24},
    "6 - Fuencarral": {"id": 6, "lat": 40.42852, "lon": -3.70205, "capacity": 27},
    "7 - Colegio Arquitectos": {"id": 7, "lat": 40.424148, "lon": -3.698447, "capacity": 24},
    "8 - Hortaleza": {"id": 8, "lat": 40.4251906, "lon": -3.6977715, "capacity": 21},
    "9 - Alonso Martínez": {"id": 9, "lat": 40.4278682, "lon": -3.6954403, "capacity": 24},
    "10 - Plaza de San Miguel": {"id": 10, "lat": 40.4156057, "lon": -3.7095084, "capacity": 24},
    "11 - Marqués de la Ensenada": {"id": 11, "lat": 40.42533, "lon": -3.69214, "capacity": 24},
    "12 - San Andrés": {"id": 12, "lat": 40.4269483, "lon": -3.7035918, "capacity": 24},
    "13 - San Hermenegildo": {"id": 13, "lat": 40.4284246, "lon": -3.7061931, "capacity": 24},
    "14 - Conde Duque": {"id": 14, "lat": 40.4273264, "lon": -3.7104417, "capacity": 24},
    "15 - Ventura Rodríguez": {"id": 15, "lat": 40.4260957, "lon": -3.713479, "capacity": 24},
    "16 - San Vicente Ferrer": {"id": 16, "lat": 40.4262383, "lon": -3.7074453, "capacity": 21},
    "17 - San Bernardo": {"id": 17, "lat": 40.4230721, "lon": -3.7075065, "capacity": 21},
    "18 - Carlos Cambronero": {"id": 18, "lat": 40.4232649, "lon": -3.7038312, "capacity": 24},
    "19 - Plaza de Pedro Zerolo": {"id": 19, "lat": 40.4207773, "lon": -3.6996502, "capacity": 24},
    "20 - Prim": {"id": 20, "lat": 40.4218616, "lon": -3.6954983, "capacity": 24},
    "21 - Banco de España A": {"id": 21, "lat": 40.4192342, "lon": -3.6954615, "capacity": 30},
    "25 - Jacometrezo": {"id": 25, "lat": 40.4200783, "lon": -3.7065376, "capacity": 24},
    "26 - Santo Domingo": {"id": 26, "lat": 40.4202834, "lon": -3.7081246, "capacity": 24},
    "27 - Palacio de Oriente": {"id": 27, "lat": 40.417908, "lon": -3.710692, "capacity": 24},
    "28 - Plaza de Celenque A": {"id": 28, "lat": 40.4173703, "lon": -3.7057791, "capacity": 24},
    "29 - Plaza de Celenque B": {"id": 29, "lat": 40.4172781, "lon": -3.7063837, "capacity": 24},
    "30 - Plaza de las Salesas": {"id": 30, "lat": 40.423855, "lon": -3.694475, "capacity": 24},
    "31 - Huertas": {"id": 31, "lat": 40.4132798, "lon": -3.6956178, "capacity": 24},
    "32 - Sevilla": {"id": 32, "lat": 40.4181518, "lon": -3.6984368, "capacity": 24},
    "33 - Marqués de Cubas": {"id": 33, "lat": 40.4162619, "lon": -3.6957355, "capacity": 24},
    "34 - San Quintín": {"id": 34, "lat": 40.4192095, "lon": -3.711504, "capacity": 27},
    "35 - Calle Mayor": {"id": 35, "lat": 40.4163638, "lon": -3.7068969, "capacity": 27},
    "36 - Plaza de la Provincia": {"id": 36, "lat": 40.4150099, "lon": -3.7061032, "capacity": 18},
    "37 - Carretas": {"id": 37, "lat": 40.4165039, "lon": -3.7030833, "capacity": 21},
    "38 - Jacinto Benavente": {"id": 38, "lat": 40.4146755, "lon": -3.7036825, "capacity": 24},
    "39 - Plaza del Cordón": {"id": 39, "lat": 40.4141931, "lon": -3.7103285, "capacity": 24},
    "40 - Plaza Ramales": {"id": 40, "lat": 40.4168, "lon": -3.71183, "capacity": 24},
    "41 - Plaza de San Francisco": {"id": 41, "lat": 40.4108, "lon": -3.714113, "capacity": 24},
    "42 - Plaza de los Carros": {"id": 42, "lat": 40.4114041, "lon": -3.7114762, "capacity": 24},
    "43 - Plaza de la Cebada": {"id": 43, "lat": 40.4112744, "lon": -3.7088337, "capacity": 27},
    "44 - Conde de Romanones": {"id": 44, "lat": 40.4138846, "lon": -3.7049407, "capacity": 24},
    "45 - Antón Martín": {"id": 45, "lat": 40.4122047, "lon": -3.6991147, "capacity": 18},
    "46 - Santa Isabel": {"id": 46, "lat": 40.4107085, "lon": -3.6982318, "capacity": 24},
    "47 - Jesús y María": {"id": 47, "lat": 40.4101564, "lon": -3.7025024, "capacity": 24},
    "48 - Plaza de Nelson Mandela": {"id": 48, "lat": 40.4097617, "lon": -3.7040666, "capacity": 21},
    "49 - Puerta de Toledo": {"id": 49, "lat": 40.4070358, "lon": -3.7110513, "capacity": 21},
    "50 - Ribera de Curtidores": {"id": 50, "lat": 40.4053153, "lon": -3.7071259, "capacity": 24},
    "51 - Embajadores 1": {"id": 51, "lat": 40.4047851, "lon": -3.7028265, "capacity": 24},
    "52 - Embajadores 2": {"id": 52, "lat": 40.4056107, "lon": -3.7022591, "capacity": 24},
    "53 - Casa Encendida": {"id": 53, "lat": 40.4060941, "lon": -3.6992759, "capacity": 24},
    "54 - Museo Reina Sofía": {"id": 54, "lat": 40.4083684, "lon": -3.6933463, "capacity": 24},
    "55 - Ronda de Atocha": {"id": 55, "lat": 40.4075606, "lon": -3.6935205, "capacity": 27},
    "56 - Plaza de Santa Ana": {"id": 56, "lat": 40.4144226, "lon": -3.7007164, "capacity": 24},
    "57 - Plaza de Lavapiés": {"id": 57, "lat": 40.4083061, "lon": -3.7007111, "capacity": 24},
    "58 - Barceló": {"id": 58, "lat": 40.4266828, "lon": -3.700423, "capacity": 21},
    "59 - Plaza de San Ildefonso": {"id": 59, "lat": 40.4239757, "lon": -3.7020842, "capacity": 24},
    "60 - Plaza del Carmen ": {"id": 60, "lat": 40.4184192, "lon": -3.7032414, "capacity": 24},
    "61 - Santa Cruz del Marcenado": {"id": 61, "lat": 40.4295658, "lon": -3.7126299, "capacity": 24},
    "62 - Augusto Figueroa": {"id": 62, "lat": 40.4222862, "lon": -3.697895, "capacity": 24},
    "63 - Plaza de Juan Pujol": {"id": 63, "lat": 40.4255495, "lon": -3.7043418, "capacity": 21},
    "64 - Plaza de la Independencia": {"id": 64, "lat": 40.419752, "lon": -3.688398, "capacity": 24},
    "65 - Narváez": {"id": 65, "lat": 40.4213983, "lon": -3.6752045, "capacity": 24},
    "66 - O'Donnell": {"id": 66, "lat": 40.4213148, "lon": -3.6724968, "capacity": 24},
    "67 - Ibiza": {"id": 67, "lat": 40.4179237, "lon": -3.6708959, "capacity": 24},
    "69 - Antonio Maura": {"id": 69, "lat": 40.4166834, "lon": -3.6894193, "capacity": 24},
    "71 - Almadén": {"id": 71, "lat": 40.4108472, "lon": -3.693225, "capacity": 24},
    "72 - Espalter": {"id": 72, "lat": 40.4128372, "lon": -3.6912023, "capacity": 21},
    "73 - Puerta del Ángel Caído": {"id": 73, "lat": 40.409808, "lon": -3.688822, "capacity": 27},
    "74 - Puerta del Doce de Octubre": {"id": 74, "lat": 40.4153053, "lon": -3.6779232, "capacity": 24},
    "75 - Doce de Octubre": {"id": 75, "lat": 40.4159569, "lon": -3.6738865, "capacity": 24},
    "76 - Sainz de Baranda": {"id": 76, "lat": 40.4157413, "lon": -3.6691838, "capacity": 24},
    "77 - Plaza de los Astros": {"id": 77, "lat": 40.4114475, "lon": -3.6689089, "capacity": 24},
    "78 - Puerta del Pacífico ": {"id": 78, "lat": 40.4117627, "lon": -3.6766813, "capacity": 24},
    "79 - Menéndez Pelayo": {"id": 79, "lat": 40.4082805, "lon": -3.6784838, "capacity": 24},
    "80 - Puerta de Mariano de Cavia": {"id": 80, "lat": 40.4071304, "lon": -3.6751352, "capacity": 24},
    "81 - Conde de Casal": {"id": 81, "lat": 40.40635, "lon": -3.670422, "capacity": 22},
    "82 - Pedro Bosch": {"id": 82, "lat": 40.400789, "lon": -3.6744, "capacity": 24},
    "83 - Puerta de Granada": {"id": 83, "lat": 40.4051451, "lon": -3.6803874, "capacity": 24},
    "84 - Atocha A": {"id": 84, "lat": 40.4075685, "lon": -3.6902255, "capacity": 24},
    "85 - Atocha B": {"id": 85, "lat": 40.4074902, "lon": -3.6901234, "capacity": 27},
    "86 - Cuesta de Moyano": {"id": 86, "lat": 40.409297, "lon": -3.691987, "capacity": 24},
    "87 - Niño Jesús": {"id": 87, "lat": 40.4084556, "lon": -3.6697526, "capacity": 24},
    "88 - Pío Baroja": {"id": 88, "lat": 40.4132995, "lon": -3.6745323, "capacity": 24},
    "89 - Valderribas": {"id": 89, "lat": 40.4032501, "lon": -3.6726019, "capacity": 24},
    "90 - Puerta de Madrid": {"id": 90, "lat": 40.421501, "lon": -3.680008, "capacity": 27},
    "91 - Cibeles": {"id": 91, "lat": 40.4186516, "lon": -3.6933498, "capacity": 21},
    "92 - Ayala": {"id": 92, "lat": 40.427736, "lon": -3.6832566, "capacity": 24},
    "93 - Embajada de Italia": {"id": 93, "lat": 40.4313576, "lon": -3.6838303, "capacity": 24},
    "94 - Conde Peñalver": {"id": 94, "lat": 40.4272582, "lon": -3.6752024, "capacity": 24},
    "95 - General Pardiñas": {"id": 95, "lat": 40.4250361, "lon": -3.6837876, "capacity": 30},
    "96 - Príncipe de Vergara": {"id": 96, "lat": 40.426134, "lon": -3.6787441, "capacity": 24},
    "97 - Claudio Coello": {"id": 97, "lat": 40.4262945, "lon": -3.6865463, "capacity": 24},
    "98 - Plaza de Colón": {"id": 98, "lat": 40.4257046, "lon": -3.6893698, "capacity": 24},
    "99 - Biblioteca Nacional": {"id": 99, "lat": 40.4232153, "lon": -3.690756, "capacity": 21},
    "100 - Villanueva": {"id": 100, "lat": 40.4226584, "lon": -3.6870548, "capacity": 24},
    "101 - Castelló": {"id": 101, "lat": 40.422064, "lon": -3.6821793, "capacity": 27},
    "102 - Alcalá": {"id": 102, "lat": 40.4222969, "lon": -3.6805189, "capacity": 27},
    "103 - Plaza de Felipe II": {"id": 103, "lat": 40.4239447, "lon": -3.6758383, "capacity": 24},
    "104 - Alcántara": {"id": 104, "lat": 40.4261851, "lon": -3.6738714, "capacity": 24},
    "105 - Palacio de Deportes": {"id": 105, "lat": 40.42478, "lon": -3.67384, "capacity": 24},
    "106 - Jorge Juan": {"id": 106, "lat": 40.4231526, "lon": -3.6691524, "capacity": 24},
    "107 - Velázquez": {"id": 107, "lat": 40.4211802, "lon": -3.6840229, "capacity": 24},
    "108 - Ortega y Gasset": {"id": 108, "lat": 40.43037, "lon": -3.68653, "capacity": 24},
    "109 - Castellana": {"id": 109, "lat": 40.42677, "lon": -3.68958, "capacity": 21},
    "110 - Serrano": {"id": 110, "lat": 40.42699, "lon": -3.68745, "capacity": 24},
    "111 - Colón A": {"id": 111, "lat": 40.4251002, "lon": -3.6877227, "capacity": 18},
    "112 - Colón B": {"id": 112, "lat": 40.424963, "lon": -3.687745, "capacity": 18},
    "113 - Columela": {"id": 113, "lat": 40.4215246, "lon": -3.6884369, "capacity": 24},
    "114 - Mártires Concepcionistas": {"id": 114, "lat": 40.4273005, "lon": -3.6706024, "capacity": 27},
    "115 - Marqués de Salamanca": {"id": 115, "lat": 40.4300481, "lon": -3.6816402, "capacity": 24},
    "116 - Moncloa": {"id": 116, "lat": 40.4347895, "lon": -3.7200845, "capacity": 24},
    "117 - Arcipreste de Hita A": {"id": 117, "lat": 40.4337322, "lon": -3.7175435, "capacity": 24},
    "118 - Arcipreste de Hita B": {"id": 118, "lat": 40.4341006, "lon": -3.7179687, "capacity": 24},
    "119 - Paseo de Moret": {"id": 119, "lat": 40.4325991, "lon": -3.7246532, "capacity": 24},
    "120 - Pintor Rosales": {"id": 120, "lat": 40.427657, "lon": -3.7205129, "capacity": 24},
    "121 - Quintana": {"id": 121, "lat": 40.4277456, "lon": -3.7174158, "capacity": 24},
    "122 - Ferraz": {"id": 122, "lat": 40.4253944, "lon": -3.7170448, "capacity": 24},
    "123 - Plaza de España A": {"id": 123, "lat": 40.42402, "lon": -3.711603, "capacity": 24},
    "124 - Plaza de España B": {"id": 124, "lat": 40.42412, "lon": -3.711703, "capacity": 24},
    "125 - Altamirano": {"id": 125, "lat": 40.4309797, "lon": -3.7188898, "capacity": 24},
    "126 - Juan Martín": {"id": 126, "lat": 40.400781, "lon": -3.6882407, "capacity": 24},
    "127 - Méndez Álvaro": {"id": 127, "lat": 40.4013216, "lon": -3.6863218, "capacity": 24},
    "128 - Palos de la Frontera": {"id": 128, "lat": 40.4032208, "lon": -3.6944768, "capacity": 24},
    "129 - Santa María de la Cabeza": {"id": 129, "lat": 40.4017926, "lon": -3.6987665, "capacity": 24},
    "130 - Santa Engracia 14": {"id": 130, "lat": 40.4291992, "lon": -3.6967169, "capacity": 24},
    "131 - Guzmán el Bueno": {"id": 131, "lat": 40.4306458, "lon": -3.7133412, "capacity": 24},
    "132 - Paseo de la Florida": {"id": 132, "lat": 40.4219665, "lon": -3.7224983, "capacity": 27},
    "133 - Metro Pirámides": {"id": 133, "lat": 40.4034076, "lon": -3.7108108, "capacity": 24},
    "134 - Paseo de la Esperanza": {"id": 134, "lat": 40.4035988, "lon": -3.7064516, "capacity": 21},
    "135 - Entrada Matadero": {"id": 135, "lat": 40.3928821, "lon": -3.6975708, "capacity": 27},
    "136 - Paseo de las Delicias": {"id": 136, "lat": 40.3972616, "lon": -3.6945025, "capacity": 24},
    "137 - Castellana 164": {"id": 137, "lat": 40.4591366, "lon": -3.6894151, "capacity": 24},
    "138 - Alberto Alcocer": {"id": 138, "lat": 40.4585318, "lon": -3.684715, "capacity": 24},
    "139 - San Germán 57": {"id": 139, "lat": 40.4572824, "lon": -3.7009675, "capacity": 24},
    "140 - Sor Ángela de la Cruz": {"id": 140, "lat": 40.4592351, "lon": -3.691533, "capacity": 24},
    "141 - Orense 36": {"id": 141, "lat": 40.4548456, "lon": -3.6946218, "capacity": 24},
    "142 - General Perón 1": {"id": 142, "lat": 40.4527164, "lon": -3.6990077, "capacity": 24},
    "143 - General Perón con Poeta Joan Maragall": {"id": 143, "lat": 40.4522454, "lon": -3.693085, "capacity": 24},
    "144 - Serrano 210": {"id": 144, "lat": 40.4510188, "lon": -3.6817962, "capacity": 24},
    "145 - Orense 12": {"id": 145, "lat": 40.4489101, "lon": -3.6952943, "capacity": 24},
    "146 - Paseo de la Habana 42": {"id": 146, "lat": 40.4498613, "lon": -3.6881689, "capacity": 24},
    "147 - Castellana frente a Hermanos Pinzón": {"id": 147, "lat": 40.4488924, "lon": -3.6905604, "capacity": 24},
    "148 - Doctor Arce 45": {"id": 148, "lat": 40.4483269, "lon": -3.6797296, "capacity": 24},
    "149 - Glorieta de los Cuatro Caminos": {"id": 149, "lat": 40.4463667, "lon": -3.7036675, "capacity": 24},
    "150 - Raimundo Fernández": {"id": 150, "lat": 40.447125, "lon": -3.7001669, "capacity": 24},
    "151 - Castellana 106": {"id": 151, "lat": 40.4453307, "lon": -3.690861, "capacity": 24},
    "152 - Plaza de la República Argentina": {"id": 152, "lat": 40.445411, "lon": -3.6853312, "capacity": 24},
    "153 - Agustín de Betancourt": {"id": 153, "lat": 40.4440297, "lon": -3.6956047, "capacity": 24},
    "154 - Paseo de la Castellana con Raimundo Fernández": {"id": 154, "lat": 40.4457414, "lon": -3.6917932, "capacity": 24},
    "155 - María Francisca 1": {"id": 155, "lat": 40.4442258, "lon": -3.6787169, "capacity": 18},
    "156 - Bravo Murillo 44": {"id": 156, "lat": 40.4418402, "lon": -3.7040344, "capacity": 24},
    "157 - Santa Engracia 127": {"id": 157, "lat": 40.44156, "lon": -3.70164, "capacity": 20},
    "158 - Plaza de San Juan de la Cruz": {"id": 158, "lat": 40.4415974, "lon": -3.6927821, "capacity": 24},
    "159 - José Gutiérrez Abascal ": {"id": 159, "lat": 40.4396792, "lon": -3.6907784, "capacity": 24},
    "160 - Cea Bermúdez": {"id": 160, "lat": 40.438994, "lon": -3.7154329, "capacity": 27},
    "161 - José Abascal": {"id": 161, "lat": 40.4383865, "lon": -3.6982353, "capacity": 24},
    "162 - Velázquez 130": {"id": 162, "lat": 40.4385127, "lon": -3.6831578, "capacity": 27},
    "163 - General Álvarez de Castro": {"id": 163, "lat": 40.4344731, "lon": -3.7015686, "capacity": 24},
    "164 - General Martínez Campos ": {"id": 164, "lat": 40.435285, "lon": -3.6948626, "capacity": 24},
    "165 - Paseo de la Castellana - Glorieta de Emilio Castelar": {"id": 165, "lat": 40.4355143, "lon": -3.6892368, "capacity": 12},
    "166 - Diego de León 52": {"id": 166, "lat": 40.4345973, "lon": -3.678492, "capacity": 24},
    "167 - Castellana 42": {"id": 167, "lat": 40.4334087, "lon": -3.6879154, "capacity": 24},
    "168 - Fernando el Católico": {"id": 168, "lat": 40.4338516, "lon": -3.708439, "capacity": 24},
    "169 - Manuel Silvela": {"id": 169, "lat": 40.4309524, "lon": -3.6993465, "capacity": 24},
    "170 - Juan Bravo 50": {"id": 170, "lat": 40.4323655, "lon": -3.6758555, "capacity": 24},
    "171 - Ortega y Gasset 87": {"id": 171, "lat": 40.429887, "lon": -3.6712823, "capacity": 24},
    "172 - Colombia": {"id": 172, "lat": 40.4572466, "lon": -3.6763439, "capacity": 24},
    "173 - Paseo de la Habana 63": {"id": 173, "lat": 40.4543852, "lon": -3.6835926, "capacity": 24},
    "174 - Segovia 26": {"id": 174, "lat": 40.4138333, "lon": -3.7135833, "capacity": 24},
    "175 - Segovia 45": {"id": 175, "lat": 40.413736, "lon": -3.717487, "capacity": 24},
    "176 - Batalla del Salado": {"id": 176, "lat": 40.4044722, "lon": -3.6959166, "capacity": 24},
    "177 - Pirámides": {"id": 177, "lat": 40.4016111, "lon": -3.7138055, "capacity": 24},
    "178 - Paseo de la Esperanza": {"id": 178, "lat": 40.401, "lon": -3.7043611, "capacity": 24},
    "179 - Embajadores-Cáceres": {"id": 179, "lat": 40.39975, "lon": -3.6983888, "capacity": 24},
    "180 - Delicias": {"id": 180, "lat": 40.4008888, "lon": -3.6935833, "capacity": 24},
    "181 - Puente Praga": {"id": 181, "lat": 40.3981798, "lon": -3.7023918, "capacity": 24},
    "182 - Madrid Río-Yeserías": {"id": 182, "lat": 40.3974444, "lon": -3.7065277, "capacity": 27},
    "183 - Jaime el Conquistador": {"id": 183, "lat": 40.3962222, "lon": -3.6983055, "capacity": 21},
    "184 - Beata": {"id": 184, "lat": 40.39425, "lon": -3.6937222, "capacity": 24},
    "185 - Legazpi": {"id": 185, "lat": 40.3914722, "lon": -3.6941944, "capacity": 24},
    "186 - Junta Municipal Retiro": {"id": 186, "lat": 40.4029202, "lon": -3.6788343, "capacity": 24},
    "187 - Puente de Vallecas": {"id": 187, "lat": 40.3979722, "lon": -3.66925, "capacity": 24},
    "188 - Méndez Álvaro": {"id": 188, "lat": 40.3941388, "lon": -3.6758888, "capacity": 24},
    "189 - Retiro-Ibiza": {"id": 189, "lat": 40.41825, "lon": -3.6766111, "capacity": 27},
    "190 - Parque Roma": {"id": 190, "lat": 40.4186666, "lon": -3.6657777, "capacity": 24},
    "191 - Doctor Esquerdo-Hermosilla": {"id": 191, "lat": 40.425635, "lon": -3.669339, "capacity": 24},
    "192 - Marqués de Zafra": {"id": 192, "lat": 40.426, "lon": -3.6653055, "capacity": 24},
    "193 - Quinta Fuente del Berro": {"id": 193, "lat": 40.4250833, "lon": -3.6615277, "capacity": 24},
    "194 - General Pardiñas": {"id": 194, "lat": 40.4290555, "lon": -3.6782777, "capacity": 24},
    "195 - Alcalá-Ventas": {"id": 195, "lat": 40.4301666, "lon": -3.6638888, "capacity": 24},
    "196 - Puente de Ventas": {"id": 196, "lat": 40.4311944, "lon": -3.6590555, "capacity": 27},
    "197 - Avenida Donostiarra": {"id": 197, "lat": 40.4351256, "lon": -3.6554918, "capacity": 24},
    "198 - Velázquez-Diego de León": {"id": 198, "lat": 40.4343333, "lon": -3.6835833, "capacity": 24},
    "199 - Diego de león": {"id": 199, "lat": 40.4346388, "lon": -3.674, "capacity": 18},
    "200 - Avenida de los Toreros": {"id": 200, "lat": 40.4318611, "lon": -3.6714166, "capacity": 27},
    "201 - Ventas": {"id": 201, "lat": 40.4324722, "lon": -3.6655555, "capacity": 27},
    "202 - Avenida de América 2": {"id": 202, "lat": 40.43725, "lon": -3.6772222, "capacity": 24},
    "203 - Avenida de América 1": {"id": 203, "lat": 40.4392222, "lon": -3.6754444, "capacity": 24},
    "204 - Prosperidad": {"id": 204, "lat": 40.4441388, "lon": -3.6751388, "capacity": 24},
    "205 - Parque Berlín": {"id": 205, "lat": 40.4515833, "lon": -3.6780555, "capacity": 24},
    "206 - Rubén Darío": {"id": 206, "lat": 40.4331111, "lon": -3.6915555, "capacity": 24},
    "207 - Fernando el Católico": {"id": 207, "lat": 40.4343611, "lon": -3.7149166, "capacity": 27},
    "208 - Quevedo": {"id": 208, "lat": 40.4336944, "lon": -3.7046666, "capacity": 24},
    "209 - Canal": {"id": 209, "lat": 40.4386944, "lon": -3.7038333, "capacity": 24},
    "210 - Parque Santander": {"id": 210, "lat": 40.4411388, "lon": -3.7080833, "capacity": 24},
    "211 - San Francisco de Sales": {"id": 211, "lat": 40.44175, "lon": -3.7144722, "capacity": 24},
    "212 - Cuatro Caminos 2": {"id": 212, "lat": 40.4476666, "lon": -3.7041666, "capacity": 24},
    "213 - Estrecho": {"id": 213, "lat": 40.4535, "lon": -3.7032777, "capacity": 24},
    "214 - Metro Tetuán": {"id": 214, "lat": 40.4607502, "lon": -3.6989925, "capacity": 24},
    "215 - Remonta": {"id": 215, "lat": 40.4630277, "lon": -3.6973333, "capacity": 18},
    "216 - Plaza de Castilla": {"id": 216, "lat": 40.4663611, "lon": -3.6886388, "capacity": 24},
    "217 - Plaza de Castilla 2": {"id": 217, "lat": 40.4656779, "lon": -3.6887722, "capacity": 24},
    "218 - Tres Cruces": {"id": 218, "lat": 40.419674, "lon": -3.7026735, "capacity": 27},
    "219 - Desengaño": {"id": 219, "lat": 40.42059, "lon": -3.70239, "capacity": 24},
    "220 - Marqués de Vadillo": {"id": 220, "lat": 40.398247, "lon": -3.716591, "capacity": 24},
    "221 - Glorieta de Cádiz": {"id": 221, "lat": 40.38895, "lon": -3.70017, "capacity": 24},
    "222 - Condesa de Venadito": {"id": 222, "lat": 40.44315, "lon": -3.65741, "capacity": 24},
    "223 - Gutierre de Cetina": {"id": 223, "lat": 40.429706, "lon": -3.640994, "capacity": 24},
    "224 - Puerta del Ángel": {"id": 224, "lat": 40.413764, "lon": -3.728318, "capacity": 24},
    "225 - Pedro Rico": {"id": 225, "lat": 40.481086, "lon": -3.688463, "capacity": 24},
    "226 - Camino Vinateros": {"id": 226, "lat": 40.41053, "lon": -3.65779, "capacity": 24},
    "227 - Marroquina": {"id": 227, "lat": 40.408264, "lon": -3.646697, "capacity": 24},
    "228 - Plaza del Encuentro": {"id": 228, "lat": 40.40617, "lon": -3.65122, "capacity": 24},
    "229 - Pavones": {"id": 229, "lat": 40.400368, "lon": -3.634587, "capacity": 24},
    "230 - Antonio López": {"id": 230, "lat": 40.3917871, "lon": -3.7026789, "capacity": 24},
    "231 - Ermita Santo": {"id": 231, "lat": 40.406837862773465, "lon": -3.7244893989507686, "capacity": 24},
    "232 - Caramuel": {"id": 232, "lat": 40.40913630273305, "lon": -3.728533714316331, "capacity": 24},
    "233 - Doctor Lozano": {"id": 233, "lat": 40.40248333540473, "lon": -3.660188083470652, "capacity": 24},
    "234 - Sierra Toledana": {"id": 234, "lat": 40.39901531507069, "lon": -3.6607768678037744, "capacity": 24},
    "235 - San Delfín": {"id": 235, "lat": 40.39440607959559, "lon": -3.708042972844556, "capacity": 24},
    "236 - Concordia": {"id": 236, "lat": 40.39382977920336, "lon": -3.665936242935637, "capacity": 24},
    "237 - C.D. Concepción": {"id": 237, "lat": 40.43715089959262, "lon": -3.64835857929032, "capacity": 24},
    "238 - Carlota O’Neill": {"id": 238, "lat": 40.44370542379883, "lon": -3.648958444298144, "capacity": 24},
    "239 - Derechos Humanos": {"id": 239, "lat": 40.43965673033275, "lon": -3.6557656204708775, "capacity": 24},
    "240 - José María Pereda": {"id": 240, "lat": 40.43272086245887, "lon": -3.6485306152875134, "capacity": 24},
    "241 - Marqués de Corbera 12": {"id": 241, "lat": 40.422962108947424, "lon": -3.6555552857442697, "capacity": 24},
    "242 - Marqués de Corbera 52": {"id": 242, "lat": 40.42620714320088, "lon": -3.651034981803642, "capacity": 24},
    "243 - Embajadores 191": {"id": 243, "lat": 40.38925864357911, "lon": -3.690358964335348, "capacity": 24},
    "244 - Paseo Imperial": {"id": 244, "lat": 40.40765396169372, "lon": -3.7172213778842007, "capacity": 24},
    "245 - Pablo Iglesias": {"id": 245, "lat": 40.451333, "lon": -3.710525, "capacity": 24},
    "246 - San Germán 5": {"id": 246, "lat": 40.45619382579544, "lon": -3.69293767517953, "capacity": 24},
    "247 - Francos Rodríguez": {"id": 247, "lat": 40.45673408797698, "lon": -3.708002730875242, "capacity": 24},
    "248 - Avenida Brasilia": {"id": 248, "lat": 40.43666, "lon": -3.66096, "capacity": 24},
    "249 - Camilo José Cela": {"id": 249, "lat": 40.4378, "lon": -3.66779, "capacity": 24},
    "250 - Avenida Bruselas": {"id": 250, "lat": 40.43865, "lon": -3.66301, "capacity": 24},
    "251 - Cartagena": {"id": 251, "lat": 40.43503, "lon": -3.67012, "capacity": 24},
    "252 - Hospital Clínico": {"id": 252, "lat": 40.44003, "lon": -3.71757, "capacity": 24},
    "253 - Galileo": {"id": 253, "lat": 40.4364, "lon": -3.71019, "capacity": 24},
    "254 - Santa Engracia 87": {"id": 254, "lat": 40.43604, "lon": -3.69928, "capacity": 24},
    "256 - Torre Cepsa": {"id": 256, "lat": 40.47435, "lon": -3.68797, "capacity": 24},
    "257 - Manuel Caldeiro": {"id": 257, "lat": 40.47938, "lon": -3.68532, "capacity": 24},
    "258 - Serrano 113": {"id": 258, "lat": 40.44106, "lon": -3.68609, "capacity": 24},
    "259 - Corazón de María": {"id": 259, "lat": 40.44421, "lon": -3.66683, "capacity": 24},
    "260 - Chamartín": {"id": 260, "lat": 40.4716, "lon": -3.68391, "capacity": 24},
    "261 - Doctor Fleming": {"id": 261, "lat": 40.45546, "lon": -3.68844, "capacity": 21},
    "262 - Pío XII": {"id": 262, "lat": 40.46041, "lon": -3.67712, "capacity": 24},
    "263 - López Pozas": {"id": 263, "lat": 40.46361, "lon": -3.68514, "capacity": 24},
    "264 - Reina Victoria": {"id": 264, "lat": 40.44635, "lon": -3.71383, "capacity": 24},
    "265 - INEF": {"id": 265, "lat": 40.43896, "lon": -3.72997, "capacity": 24},
    "266 - Ciudad Universitaria 1": {"id": 266, "lat": 40.44375, "lon": -3.72699, "capacity": 24},
    "267 - Ciudad Universitaria 2": {"id": 267, "lat": 40.44342, "lon": -3.72693, "capacity": 24},
    "268 - Facultad Biología": {"id": 268, "lat": 40.4483322, "lon": -3.7272945, "capacity": 24},
    "269 - Facultad Derecho": {"id": 269, "lat": 40.45109, "lon": -3.72937, "capacity": 24},
    "270 - Zurbano": {"id": 270, "lat": 40.43837, "lon": -3.69281, "capacity": 24},
}


MESES_ES = {
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
    "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
}
HORAS_DISPONIBLES = [f"{h:02d}:00" for h in range(24)]
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
NUM_ESTACIONES_CERCANAS_MAPA = 8


def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    radio_tierra_metros = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radio_tierra_metros * c


@st.cache_data(show_spinner=False)
def obtener_estaciones_cercanas_mapa(estacion_nombre, cantidad=NUM_ESTACIONES_CERCANAS_MAPA):
    estacion_origen = estaciones_data.get(estacion_nombre)
    if not estacion_origen:
        return []

    distancias = []
    for nombre, coord in estaciones_data.items():
        if nombre == estacion_nombre:
            continue

        distancia = calcular_distancia_metros(
            estacion_origen["lat"],
            estacion_origen["lon"],
            coord["lat"],
            coord["lon"],
        )
        distancias.append((nombre, round(distancia)))

    distancias.sort(key=lambda item: item[1])
    return distancias[:cantidad]


@st.cache_data(ttl=1800)
def obtener_clima_madrid():
    """Obtiene la prediccion horaria de AEMET para Madrid de forma robusta.

    Evita valores raros usando siempre la hora disponible mas cercana y
    comprobando rangos razonables antes de enviar los datos al modelo.
    """

    default = {
        "temp_mean": 20.0,
        "temp_max": 25.0,
        "temp_min": 15.0,
        "precip": 0.0,
        "hum": 50.0,
        "estado": "Sin AEMET: valores por defecto 🌤️"
    }

    if not API_KEY:
        return default

    def es_numero_valido(valor):
        try:
            return valor is not None and str(valor).strip() not in ["", "Ip"]
        except Exception:
            return False

    def extraer_valor(item, campo="value"):
        valor = item.get(campo)
        if not es_numero_valido(valor):
            return None
        return float(str(valor).replace(",", "."))

    def seleccionar_por_hora(lista, hora_objetivo):
        """Devuelve el item de AEMET mas cercano a la hora actual.

        Si hay horas futuras disponibles, prioriza la primera hora futura.
        Si no, usa la hora pasada mas cercana.
        """
        candidatos = []

        for item in lista or []:
            periodo = str(item.get("periodo", "")).zfill(2)
            if not periodo.isdigit():
                continue

            hora_item = int(periodo)
            if 0 <= hora_item <= 23:
                candidatos.append((hora_item, item))

        if not candidatos:
            return None

        candidatos.sort(key=lambda x: x[0])

        for hora_item, item in candidatos:
            if hora_item >= hora_objetivo:
                return item

        return candidatos[-1][1]

    try:
        url_metadata = (
            "https://opendata.aemet.es/opendata/api/prediccion/especifica/"
            f"municipio/horaria/28079/?api_key={API_KEY}"
        )

        res_meta = requests.get(url_metadata, timeout=10)
        if res_meta.status_code != 200:
            return default

        url_datos = res_meta.json().get("datos")
        if not url_datos:
            return default

        res_datos = requests.get(url_datos, timeout=10)
        if res_datos.status_code != 200:
            return default

        respuesta = res_datos.json()
        if not respuesta:
            return default

        datos = respuesta[0]
        dias = datos.get("prediccion", {}).get("dia", [])
        if not dias:
            return default

        ahora = datetime.now()
        fecha_hoy = ahora.strftime("%Y-%m-%d")

        # Elegimos el bloque del dia actual si existe. Si no, usamos el primero disponible.
        dia = next((d for d in dias if str(d.get("fecha", "")).startswith(fecha_hoy)), dias[0])

        item_temp = seleccionar_por_hora(dia.get("temperatura", []), ahora.hour)
        item_hum = seleccionar_por_hora(dia.get("humedadRelativa", []), ahora.hour)
        item_precip = seleccionar_por_hora(dia.get("precipitacion", []), ahora.hour)

        temp_actual = extraer_valor(item_temp) if item_temp else None
        hum_actual = extraer_valor(item_hum) if item_hum else None
        precip_actual = extraer_valor(item_precip) if item_precip else 0.0

        # Rango de seguridad para no mostrar ni usar valores absurdos.
        if temp_actual is None or not (-20 <= temp_actual <= 50):
            temp_actual = default["temp_mean"]

        if hum_actual is None or not (0 <= hum_actual <= 100):
            hum_actual = default["hum"]

        if precip_actual is None or precip_actual < 0 or precip_actual > 200:
            precip_actual = default["precip"]

        temperaturas_dia = []
        for item in dia.get("temperatura", []):
            valor = extraer_valor(item)
            if valor is not None and -20 <= valor <= 50:
                temperaturas_dia.append(valor)

        if temperaturas_dia:
            temp_max = max(temperaturas_dia)
            temp_min = min(temperaturas_dia)
        else:
            temp_max = temp_actual + 5.0
            temp_min = temp_actual - 5.0

        return {
            "temp_mean": round(temp_actual, 1),
            "temp_max": round(temp_max, 1),
            "temp_min": round(temp_min, 1),
            "precip": round(precip_actual, 1),
            "hum": round(hum_actual, 1),
            "estado": f"Conectado a AEMET 🌤️ Hora {ahora.hour:02d}:00"
        }

    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
        return default

clima_actual = obtener_clima_madrid()


def predecir_bicis(estacion_nombre, hora, mes, dia_semana_str, tipo_dia_str,
                    temp_mean, precip, hum, temp_max, temp_min):
    if modelo_rf is None:
        return -1


    mapa_semana = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3,
                    "Viernes": 4, "Sábado": 5, "Domingo": 6}
    dia_num = mapa_semana.get(dia_semana_str, 0)


    is_working_day = 1 if tipo_dia_str == "Laborable" else 0
    is_weekend = 1 if tipo_dia_str in ["Sábado", "Domingo", "Fin de semana"] else 0


    mapa_day_type = {"Laborable": 0, "Sábado": 1, "Domingo": 2,
                      "Fin de semana": 1, "Festivo": 2}
    day_type_codificado = mapa_day_type.get(tipo_dia_str, 0)


    precipitation_has = 1.0 if precip > 0 else 0.0
    estacion = estaciones_data[estacion_nombre]


    columnas_ordenadas = [
        'snapshot_hour', 'snapshot_day_of_week', 'snapshot_month',
        'station_capacity', 'station_latitude', 'station_longitude',
        'weather_temperature_mean_c', 'weather_temperature_min_c', 'weather_temperature_max_c',
        'weather_precipitation_mm', 'weather_humidity_mean_pct',
        'station_id_historical', 'day_type', 'is_working_day', 'is_weekend',
        'weather_has_precipitation'
    ]


    input_data = pd.DataFrame([{
        'snapshot_hour': float(hora),
        'snapshot_day_of_week': float(dia_num),
        'snapshot_month': float(mes),
        'station_capacity': float(estacion["capacity"]),
        'station_latitude': float(estacion["lat"]),
        'station_longitude': float(estacion["lon"]),
        'weather_temperature_mean_c': float(temp_mean),
        'weather_temperature_min_c': float(temp_min),
        'weather_temperature_max_c': float(temp_max),
        'weather_precipitation_mm': float(precip),
        'weather_humidity_mean_pct': float(hum),
        'station_id_historical': float(estacion["id"]),
        'day_type': float(day_type_codificado),
        'is_working_day': float(is_working_day),
        'is_weekend': float(is_weekend),
        'weather_has_precipitation': precipitation_has
    }], columns=columnas_ordenadas)


    try:
        prediccion = modelo_rf.predict(input_data)
        resultado = max(0, int(round(prediccion[0])))
        return min(resultado, estacion["capacity"])
    except Exception as e:
        st.error(f"Error interno del modelo: {e}")
        return -1


tab_usuario, tab_gestion = st.tabs(["📱 Vista Usuario (Ciclista)", "⚙️ Vista Gestión (BiciMAD)"])


# ==========================================
# PESTAÑA 1: VISTA USUARIO
# ==========================================
with tab_usuario:
    with st.container():
        st.markdown("### ¿Habrá bicis cuando llegue?")
        st.info(f"📡 **El tiempo ahora en Madrid:** {clima_actual['temp_mean']}ºC - {clima_actual['estado']}")

    col_izq, col_der = st.columns([1, 1.5])

    with col_izq:
        with st.container():
            with st.form("form_usuario"):
                estacion_usu = st.selectbox("¿A qué estación vas?", list(estaciones_data.keys()), key="est_usu")
                hora_usu_str = st.selectbox("¿A qué hora vas a ir?", HORAS_DISPONIBLES, index=8, key="hora_usu")
                submit_usu = st.form_submit_button("Consultar Disponibilidad")

            if submit_usu:
                hora_usu = int(hora_usu_str.split(":")[0])
                ahora = datetime.now()
                mapa_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                dia_real = mapa_dias[ahora.weekday()]
                tipo_real = "Fin de semana" if ahora.weekday() >= 5 else "Laborable"

                bicis_pred = predecir_bicis(
                    estacion_nombre=estacion_usu, hora=hora_usu, mes=ahora.month,
                    dia_semana_str=dia_real, tipo_dia_str=tipo_real,
                    temp_mean=clima_actual['temp_mean'], precip=clima_actual['precip'],
                    hum=clima_actual['hum'], temp_max=clima_actual['temp_max'], temp_min=clima_actual['temp_min']
                )

                if bicis_pred != -1:
                    capacidad_est = estaciones_data[estacion_usu]["capacity"]
                    huecos = capacidad_est - bicis_pred

                    st.success("Previsión lista. ¡Buen viaje!")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="Bicis libres estimadas", value=str(bicis_pred))
                    with col2:
                        st.metric(label="Huecos para aparcar", value=str(max(0, huecos)))

    with col_der:
        with st.container():
            st.markdown('<div class="titulo-mapa">Mapa de estaciones cercanas</div>', unsafe_allow_html=True)

            # Centro del mapa según la estación elegida en el desplegable
            coord_estacion = estaciones_data[estacion_usu]
            centro_mapa = [coord_estacion["lat"], coord_estacion["lon"]]
            estaciones_cercanas = obtener_estaciones_cercanas_mapa(estacion_usu)

            m = folium.Map(
                location=centro_mapa,
                zoom_start=17,
                tiles=None,
                prefer_canvas=True
            )

            folium.TileLayer(
                tiles="OpenStreetMap",
                name="OpenStreetMap",
                control=False,
                opacity=1
            ).add_to(m)

            # Evita el efecto visual de transparencia/fade mientras cargan las teselas del mapa.
            m.get_root().header.add_child(Element("""
                <style>
                    .leaflet-container {
                        background: #ffffff !important;
                    }
                    .leaflet-tile {
                        opacity: 1 !important;
                        transition: none !important;
                    }
                    .leaflet-fade-anim .leaflet-tile {
                        opacity: 1 !important;
                        transition: none !important;
                    }
                    .leaflet-marker-icon, .leaflet-marker-shadow {
                        opacity: 1 !important;
                    }
                </style>
            """))

            folium.Marker(
                [coord_estacion["lat"], coord_estacion["lon"]],
                tooltip=f"{estacion_usu} · estación seleccionada",
                popup=f"<b>{estacion_usu}</b><br>Estación seleccionada",
                icon=folium.Icon(color="red", icon="star")
            ).add_to(m)

            puntos_mapa = [[coord_estacion["lat"], coord_estacion["lon"]]]
            for nombre, distancia_metros in estaciones_cercanas:
                coord = estaciones_data[nombre]
                puntos_mapa.append([coord["lat"], coord["lon"]])

                folium.Marker(
                    [coord["lat"], coord["lon"]],
                    tooltip=f"{nombre} · {distancia_metros} m",
                    popup=f"<b>{nombre}</b><br>A {distancia_metros} m de la estación seleccionada",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)

            if len(puntos_mapa) > 1:
                m.fit_bounds(puntos_mapa, padding=[24, 24])

            st.caption(f"Mostrando la estación seleccionada y las {len(estaciones_cercanas)} estaciones más cercanas.")

            st_folium(
                m,
                width=None,
                use_container_width=True,
                height=350,
                key="mapa_usuario",
                center=centro_mapa,
                zoom=16,
                returned_objects=[]
            )


# ==========================================
# PESTAÑA 2: VISTA GESTOR
# ==========================================
with tab_gestion:
    if not st.session_state.get("gestion_autenticada", False):
        mostrar_acceso_gestion()
        st.stop()

    col_sesion, col_logout = st.columns([3, 1])
    with col_sesion:
        st.caption(f"Sesión iniciada: {st.session_state.get('gestion_email')}")
    with col_logout:
        if st.button("Cerrar sesión"):
            cerrar_sesion_gestion()
            st.rerun()

    with st.container():
        st.markdown("### Panel de Control Logístico")

        if modelo_rf is None:
            st.warning("⚠️ Modelo no cargado.")

        with st.form("form_gestion"):
            col_est, col_espacio = st.columns([1, 2])
            with col_est:
                estacion_gest = st.selectbox("Selecciona la estación:", list(estaciones_data.keys()), key="est_gest")

            col_g1, col_g2, col_g3 = st.columns([1, 1, 1])

            with col_g1:
                st.markdown("**Fecha y hora**")
                hora_gest_str = st.selectbox("Hora", HORAS_DISPONIBLES, index=8, key="h_g")

                anio_gest = st.number_input(
                    "Año",
                    min_value=2020,
                    max_value=2035,
                    value=datetime.now().year,
                    step=1,
                    key="anio_g"
                )

                mes_gest_str = st.selectbox(
                    "Mes",
                    list(MESES_ES.keys()),
                    index=datetime.now().month - 1,
                    key="m_g"
                )

                mes_gest = MESES_ES[mes_gest_str]
                dias_del_mes = calendar.monthrange(int(anio_gest), mes_gest)[1]

                dia_mes_gest = st.selectbox(
                    "Día",
                    list(range(1, dias_del_mes + 1)),
                    index=min(datetime.now().day, dias_del_mes) - 1,
                    key="dia_mes_g"
                )

                fecha_gest = datetime(int(anio_gest), mes_gest, int(dia_mes_gest))
                dia_gest_str = DIAS_SEMANA[fecha_gest.weekday()]

            with col_g2:
                st.markdown("**Resultado de fecha**")
                st.info(f"📅 Ese día cae en: **{dia_gest_str}**")

                es_festivo = st.checkbox("¿Es festivo?", value=False, key="festivo_g")

                submit_gest = st.form_submit_button("Ejecutar Simulación")

            with col_g3:
                st.markdown("**Condiciones climáticas**")
                t_gest = st.number_input("Temp media", value=clima_actual['temp_mean'])
                p_gest = st.number_input("Precipitación", value=0.0)
                h_gest = st.number_input("Humedad", value=50.0)

    if submit_gest and modelo_rf is not None:
        hora_gest = int(hora_gest_str.split(":")[0])

        t_max_sim = t_gest + 5.0
        t_min_sim = t_gest - 5.0

        if es_festivo:
            tipo_gest_calculado = "Festivo"
        elif dia_gest_str in ["Sábado", "Domingo"]:
            tipo_gest_calculado = "Fin de semana"
        else:
            tipo_gest_calculado = "Laborable"

        bicis_pred = predecir_bicis(
            estacion_nombre=estacion_gest, hora=hora_gest, mes=mes_gest,
            dia_semana_str=dia_gest_str, tipo_dia_str=tipo_gest_calculado,
            temp_mean=t_gest, precip=p_gest, hum=h_gest,
            temp_max=t_max_sim, temp_min=t_min_sim
        )

        if bicis_pred != -1:
            with st.container():
                st.success("✅ Simulación completada.")

                col_res1, col_res2 = st.columns(2)
                capacidad_total = estaciones_data[estacion_gest]["capacity"]
                huecos_libres = max(0, capacidad_total - bicis_pred)

                with col_res1:
                    st.metric("Bicicletas Disponibles", f"{bicis_pred} uds.")
                with col_res2:
                    st.metric("Anclajes Libres", f"{huecos_libres} uds.")

                st.markdown("---")
                if bicis_pred <= 3:
                    st.error("🚨 **ESTADO CRÍTICO:** Disponibilidad mínima. Se requiere furgoneta de reposición inmediata.")
                elif 4 <= bicis_pred <= 7:
                    st.warning("⚠️ **ESTADO MODERADO:** Disponibilidad baja. Programar reposición en la próxima ruta.")
                elif bicis_pred >= (capacidad_total - 3):
                    st.warning("⚠️ **ESTADO DE SATURACIÓN:** Estación casi llena. Plantear retirada de unidades.")
                else:
                    st.info("🟢 **ESTADO ÓPTIMO:** Inventario equilibrado. No requiere acción logística.")
