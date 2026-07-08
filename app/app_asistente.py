import os
import csv
import string
import random
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, time

# --- CONFIGURACIÓN DE RUTA HISTÓRICO CSV ---
# Forzamos a que todo apunte exactamente al mismo archivo histórico del proyecto
DIRECTORIO_APP = "app"
if os.path.exists(DIRECTORIO_APP) and os.path.isdir(DIRECTORIO_APP):
    archivo_csv = os.path.join(DIRECTORIO_APP, "booking_history.csv")
else:
    archivo_csv = "booking_history.csv"

# --- FUNCION AUXILIAR DE LOCALIZADORES ---
def generar_localizador():
    """Genera un código alfanumérico único para la reserva."""
    letras = "".join(random.choices(string.ascii_uppercase, k=2))
    numeros = "".join(random.choices(string.digits, k=4))
    return f"BM-{letras}{numeros}"

# --- FUNCIONES DE PERSISTENCIA EN BASE DE DATOS ---

def guardar_reserva_csv(localizador, estacion, fecha, hora, nombre, telefono, rating=5):
    """Guarda una reserva confirmada con su valoración en el CSV de forma directa."""
    nueva_fila = [
        str(localizador),                             # booking_id
        str(estacion),                                # station_name
        str(fecha),                                  # booking_date
        str(hora),                                   # booking_time
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),# registration_date
        "Confirmada",                                # status
        int(rating),                                 # rating
        ""                                           # cancellation_reason
    ]
    
    existe_archivo = os.path.exists(archivo_csv)
    with open(archivo_csv, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe_archivo:
            writer.writerow([
                "booking_id", "station_name", "booking_date", "booking_time", 
                "registration_date", "status", "rating", "cancellation_reason"
            ])
        writer.writerow(nueva_fila)

def anular_reserva_csv(localizador, motivo):
    """Busca una reserva por localizador en el CSV y la marca como Anulada."""
    if not os.path.exists(archivo_csv):
        return False
        
    try:
        df = pd.read_csv(archivo_csv, dtype=str)
        if "booking_id" in df.columns:
            df["booking_id"] = df["booking_id"].astype(str).str.strip()
            localizador_str = str(localizador).strip()
            
            if localizador_str in df["booking_id"].values:
                df.loc[df["booking_id"] == localizador_str, "status"] = "Anulada"
                df.loc[df["booking_id"] == localizador_str, "cancellation_reason"] = str(motivo)
                df.to_csv(archivo_csv, index=False)
                return True
    except Exception as e:
        st.error(f"Error al escribir la anulación en el CSV: {e}")
    return False

# --- MODAL 1: FORMULARIO DE RESERVA ---

@st.dialog("🎫 Formulario de Reserva BiciMAD")
def mostrar_modal_reserva(hora_sugerida):
    """Abre el pop-up de reserva con el listado completo fijo inmutable."""
    st.write("📋 **Completa los detalles de tu reserva futura:**")
    st.markdown("---")
    
    # 290 Estaciones Reales Fijas - Cero búsquedas dinámicas falibles
    lista_estaciones = [
        "1a - Puerta del Sol A", "1b - Puerta del Sol B", "2 - Plaza de Celenque", "3 - Plaza de San Miguel", 
        "4 - Plaza de Mayor", "5 - Plaza de Jacinto Benavente", "6 - Plaza de la Provincia", "7 - Colegio de Arquitectos", 
        "8 - Calle Alcalá", "9 - Plaza de San Amaro", "10 - Plaza de la Paja", "11 - Plaza de San Francisco", 
        "12 - Plaza de la Cebada", "13 - Calle Segovia", "14 - Plaza de la Morería", "15 - Calle Toledo", 
        "16 - Calle Valencia", "17 - Plaza de Lavapiés", "18 - Calle Embajadores", "19 - Calle Atocha", 
        "20 - Plaza de la Corrala", "21 - Calle Agustín de Betancourt", "22 - Calle Raimundo Fernández Villaverde", 
        "23 - Calle General Ibáñez de Ibero", "24 - Paseo de la Castellana", "25 - Paseo de Recoletos", 
        "26 - Calle Jorge Juan", "27 - Calle Serrano", "28 - Calle Claudio Coello", "29 - Calle Lagasca", 
        "30 - Calle Velázquez", "31 - Calle Goya", "32 - Calle Conde de Peñalver", "33 - Calle Diego de León", 
        "34 - Calle Juan Bravo", "35 - Calle Ortega y Gasset", "36 - Calle Príncipe de Vergara", "37 - Calle Francisco Silvela", 
        "38 - Calle Doctor Esquerdo", "39 - Calle Ibiza", "40 - Calle Menorca", "41 - Calle O'Donnell", 
        "42 - Calle Alcalá / Manuel Becerra", "43 - Calle Goya / Conde de Peñalver", "44 - Calle Narváez", "45 - Antón Martín", 
        "46 - Calle Atocha / Clínica", "47 - Calle Jesús de Medinaceli", "48 - Paseo del Prado / Neptuno", 
        "49 - Paseo del Prado / Cibeles", "50 - Museo del Prado", "51 - Calle Claudio Moyano", "52 - Plaza de la Independencia", 
        "53 - Plaza de Cibeles", "54 - Plaza de la Lealtad", "55 - Plaza de Cánovas del Castillo", "56 - Plaza de Santa Ana", 
        "57 - Calle Huertas", "58 - Calle Atocha / Benavente", "59 - Plaza de Tirso de Molina", "60 - Plaza de Cascorro", 
        "61 - Calle Duque de Alba", "62 - Calle Ribera de Curtidores", "63 - Plaza de Nelson Mandela", "64 - Plaza de la Cebada", 
        "65 - Calle San Millán", "66 - Calle Humilladero", "67 - Calle Toledo / La Latina", "68 - Plaza de los Carros", 
        "69 - Plaza de la Paja", "70 - Calle Segovia / Ronda", "71 - Cuesta de la Vega", "72 - Calle Bailén", 
        "73 - Plaza de la Armería", "74 - Plaza de Oriente", "75 - Calle San Quintín", "76 - Plaza de Isabel II", 
        "77 - Calle Arenal", "78 - Calle Mayor", "79 - Calle Carretas", "80 - Calle Montera", 
        "81 - Calle Fuencarral", "82 - Plaza de Chueca", "83 - Calle Augusto Figueroa", "84 - Calle Hortaleza", 
        "85 - Calle San Mateo", "86 - Plaza de Santa Bárbara", "87 - Alonso Martínez", "88 - Calle Génova", 
        "89 - Almagro", "90 - Castellana / Rubén Darío", "91 - Serrano / Ortega y Gasset", "92 - Serrano / Hermosilla", 
        "93 - Velázquez / Goya", "94 - Velázquez / Jorge Juan", "95 - Príncipe de Vergara / Jorge Juan", "96 - Goya / Príncipe de Vergara", 
        "97 - Alcalá / Aguirre", "98 - Plaza de Felipe II", "99 - Alcántara", "100 - Goya / Cartago", 
        "101 - Conde de Peñalver / Ayala", "102 - Juan Bravo / Diego de León", "103 - Ortega y Gasset / Lista", "104 - Diego de León / Castellana", 
        "105 - Serrano / María de Molina", "106 - Serrano / Diego de León", "107 - Velázquez / Diego de León", "108 - Príncipe de Vergara / Diego de León", 
        "109 - Francisco Silvela / Juan Bravo", "110 - Plaza de Manuel Becerra", "111a - Ardemans", "111b - Alcántara / Padilla", 
        "112 - Francisco Silvela / Diego de León", "113 - General Oraá", "114 - Castellana / Emilio Castelar", "115 - Castellana / Miguel Ángel", 
        "116a - Bernardo López García", "116b - San Bernardo", "117 - Plaza de las Comendadoras", "118 - Conde Duque", 
        "119 - Plaza de España", "120 - Reyes", "121 - Plaza de Mostenses", "122 - Plaza de Santo Domingo", 
        "123 - Plaza del Callao", "124 - Tres Cruces", "125 - Plaza de Colón", "126 - Paseo de Recoletos / Biblioteca", 
        "127 - Paseo del Prado / Bolsa", "128 - Paseo del Prado / Botánico", "129 - Paseo de la Infanta Isabel", "130 - Estación de Atocha", 
        "131 - Ronda de Atocha", "132 - Santa María de la Cabeza", "133 - Ronda de Valencia", "134 - Ronda de Toledo / Acacias", 
        "135 - Ronda de Toledo / Gasómetro", "136 - Puerta de Toledo", "137 - Gran Vía de San Francisco", "138 - Calle San Francisco / Bailén", 
        "139 - Cuesta de San Vicente", "140 - Paseo del Rey", "141 - Paseo de la Florida", "142 - Paseo de Moret", 
        "143 - Pintor Rosales", "144 - Ferraz", "145 - Quintana", "146 - Ventura Rodríguez", 
        "147 - Plaza de los Cubos", "148 - Princesa / Plaza de España", "149 - Princesa / Centro Comercial", "150 - Conde Duque / Alberto Aguilera", 
        "151 - Fuencarral / Bilbao", "152 - San Bernardo / Bilbao", "153 - Fuencarral / San Joaquín", "154 - Plaza de San Ildefonso", 
        "155 - Plaza de la Luna", "156 - Plaza del Carmen", "157 - Plaza de las Descalzas", "158 - San Quintín / Pavía", 
        "159 - Plaza de la Marina Española", "160 - Paseo de la Castellana / Nuevos Ministerios", "161 - Paseo de la Castellana / Ríos Rosas", "162 - Paseo de la Castellana / San Juan de la Cruz", 
        "163 - Ríos Rosas", "164 - Alonso Cano", "165 - Santa Engracia / Ponzano", "166 - Santa Engracia / Iglesia", 
        "167 - Iglesia", "168 - General Martínez Campos", "169 - Rubén Darío", "170 - Fortuny", 
        "171 - Eduardo Dato", "172 - Zurbarán", "173 - Fuencarral / Alburquerque", "174 - Eloy Gonzalo", 
        "175 - Quevedo", "176 - San Bernardo / Garcilaso", "177 - San Bernardo / Carranza", "178 - Arapiles", 
        "179 - Alberto Aguilera / Galileo", "180 - Alberto Aguilera / Vallehermoso", "181 - Alberto Aguilera / Princesa", "182 - Moncloa", 
        "183 - Arcipreste de Hita", "184 - Isaac Peral", "185 - Cea Bermúdez", "186 - Galileo / Fernando el Católico", 
        "187 - Vallehermoso / Fernando el Católico", "188 - Fuencarral / Quevedo", "189 - Bravo Murillo / Quevedo", "190 - Canal", 
        "191 - Santa Engracia / Ríos Rosas", "192 - José Abascal", "193 - Modesto Lafuente", "194 - Martínez Campos / Alonso Cano", 
        "195 - Fernández de la Hoz", "196 - Zurbano", "197 - José Abascal / Castellana", "198 - Gregorio Marañón", 
        "199 - María de Molina", "200 - López de Hoyos", "201 - Príncipe de Vergara / Lázaro Galdiano", "202 - Serrano / República Argentina", 
        "203 - República Argentina", "204 - Joaquín Costa", "205 - Paseo de la Habana", "206 - Castellana / Nuevos Ministerios Este", 
        "207 - Nuevos Ministerios Centro", "208 - Raimundo Fernández Villaverde / Orense", "209 - Orense / Hernani", "210 - Cuatro Caminos", 
        "211 - Bravo Murillo / Carolinas", "212 - General Perón", "213 - Plaza de Manolete", "214 - Castellana / Santiago Bernabéu", 
        "215 - Plaza de Lima", "216 - Orense / General Perón", "217 - Infanta Mercedes", "218 - Bravo Murillo / Estrecho", 
        "219 - Sor Ángela de la Cruz", "220 - Plaza de Castilla", "221 - Alberto Alcocer", "222 - Padre Damián", 
        "223 - Paseo de la Habana / Centro Comercial", "224 - Pío XII", "225 - Príncipe de Vergara / Colombia", "226 - Colombia", 
        "227 - Concha Espina", "228 - Plaza de Cataluña", "229 - Príncipe de Vergara / Concha Espina", "230 - López de Hoyos / Cartagena", 
        "231 - Cartagena", "232 - Avenida de América", "233 - Francisco Silvela / Avenida de América", "234 - María de Molina / Avenida de América", 
        "235 - Alcántara / Juan Bravo", "236 - Ortega y Gasset / Alcántara", "237 - Juan Bravo / Francisco Silvela", "238 - Plaza de Toros de las Ventas", 
        "239 - Alcalá / Ventas", "240 - Alcalá / Búho", "241 - Alcalá / Goya", "242 - Jorge Juan / Felipe II", 
        "243 - Narváez / Felipe II", "244 - O'Donnell / Narváez", "245 - Menéndez Pelayo / O'Donnell", "246 - Menéndez Pelayo / Ibiza", 
        "247 - Sainz de Baranda", "248 - Doctor Esquerdo / Sainz de Baranda", "249 - Plaza de Niño Jesús", "250 - Menéndez Pelayo / Doce de Octubre", 
        "251 - Hospital Gregorio Marañón", "252 - Ibiza / Doctor Esquerdo", "253 - Samaria", "254 - Doctor Esquerdo / Los Astros", 
        "255 - Plaza de Mariano de Cavia", "256 - Menéndez Pelayo / Comercio", "257 - Avenida de la Ciudad de Barcelona", "258 - Estación de Méndez Álvaro", 
        "259 - Méndez Álvaro / Planetario", "260 - Delicias", "261 - Paseo de Santa María de la Cabeza / Palos de la Frontera", "262 - Palos de la Frontera", 
        "263 - Jaime el Conquistador", "264 - Chopera", "265 - Matadero", "266 - Plaza de Legazpi", 
        "267 - Paseo de las Acacias", "268 - Pirámides", "269 - Paseo de los Melancólicos", "270 - Pirámides / Yeserías", 
        "271 - Imperial", "272 - Virgen del Puerto", "273 - San Francisco el Grande", "274 - Ronda de Segovia", 
        "275 - Paseo de Extremadura", "276 - Puerta de Ángel", "277 - Lago / Casa de Campo", "278 - El Pardo", 
        "279 - Ciudad Universitaria", "280 - Avenida de la Complutense", "281 - Paraninfo", "282 - Hospital Clínico", 
        "283 - Islas Filipinas", "284 - Guzmán el Bueno", "285 - Cuatro Caminos / Reina Victoria", "286 - Francos Rodríguez", 
        "287 - Valdezarza", "288 - Barrio del Pilar", "289 - Plaza de Castilla Oeste", "290 - Chamartín"
    ]
    
    # 1. Creamos un Formulario Contenedor de Streamlit único para CONGELAR los datos.
    # Esto evita que Streamlit borre la estación seleccionada al darle al botón.
    with st.form("form_fijo_reserva", clear_on_submit=False):
        estacion_seleccionada = st.selectbox("📍 Selecciona la Estación de recogida:", lista_estaciones)
        
        default_time = datetime.now().time()
        if hora_sugerida and ":" in hora_sugerida:
            try:
                h, m = map(int, hora_sugerida.split(":"))
                default_time = time(h, m)
            except:
                pass

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_reserva = st.date_input("🗓️ Fecha del viaje:", datetime.now().date() + timedelta(days=1))
        with col_f2:
            hora_reserva = st.time_input("⏰ Hora del viaje:", default_time)
            
        st.markdown("**🚲 ¡Valora tu experiencia con la aplicación!**")
        rating_bicis = st.select_slider(
            "¿Cuántas bicis nos das?",
            options=["🚲", "🚲🚲", "🚲🚲🚲", "🚲🚲🚲🚲", "🚲🚲🚲🚲🚲"],
            value="🚲🚲🚲🚲🚲"
        )
        rating_usuario = len(rating_bicis) // len("🚲")
        
        nombre = st.text_input("Nombre completo del titular:")
        telefono = st.text_input("Teléfono móvil:")
        
        btn_confirmar = st.form_submit_button("Confirmar Reserva", type="primary")
        
        if btn_confirmar:
            fecha_final = datetime.combine(fecha_reserva, hora_reserva)
            ahora = datetime.now()
            horas_antelacion = (fecha_final - ahora).total_seconds() / 3600
            
            if horas_antelacion < 24:
                st.error("⏳ **Margen insuficiente:** Las reservas requieren más de 24h de antelación.")
            elif not nombre.strip() or not telefono.strip():
                st.error("❌ Por favor, rellena todos los campos obligatorios.")
            else:
                loc = generar_localizador()
                
                # 2. Guardamos en memoria inmediata para la pestaña actual
                if "db_reservas" not in st.session_state:
                    st.session_state.db_reservas = {}
                    
                st.session_state.db_reservas[loc] = {
                    "titular": nombre,
                    "telefono": telefono,
                    "estacion": str(estacion_seleccionada),
                    "fecha_hora": fecha_final.strftime("%d/%m/%Y a las %H:%Mh"),
                    "status": "Confirmada"
                }
                
                # 3. Guardamos inmediatamente en el CSV histórico real
                guardar_reserva_csv(
                    localizador=loc,
                    estacion=estacion_seleccionada,
                    fecha=fecha_reserva.strftime("%Y-%m-%d"),
                    hora=hora_reserva.strftime("%H:%M"),
                    nombre=nombre,
                    telefono=telefono,
                    rating=rating_usuario
                )
                
                st.session_state["ultimo_localizador_creado"] = loc
                st.rerun()

# --- MODAL 2: GESTIÓN DE RESERVAS ---

@st.dialog("🔍 Panel de Gestión de Reservas")
def mostrar_modal_gestion():
    """Abre un pop-up flotante limpio para verificar o dar de baja reservas de forma estable."""
    tab_verificar, tab_cancelar = st.tabs(["🎫 Verificar Localizador", "❌ Cancelar Reserva"])
    
    with tab_verificar:
        st.write("Introduce tu código para comprobar tu estado:")
        codigo_check = st.text_input("Localizador:", placeholder="BM-XXXXXX", key="input_check").strip().upper()
        if st.button("Buscar Reserva", key="btn_check"):
            if "db_reservas" in st.session_state and codigo_check in st.session_state.db_reservas:
                res = st.session_state.db_reservas[codigo_check]
                st.success("✅ ¡Reserva Localizada!")
                st.markdown(f"""
                * **👤 Titular:** {res['titular']}
                * **📞 Teléfono:** {res['telefono']}
                * **📍 Estación:** {res['estacion']}
                * **⏱️ Fecha/Hora:** {res['fecha_hora']}
                """)
            else:
                st.error("❌ El localizador no existe o ya ha sido cancelado.")
                
    with tab_cancelar:
        st.write("Si no vas a usar la bicicleta, libérala aquí:")
        codigo_cancel = st.text_input("Localizador a dar de baja:", placeholder="BM-XXXXXX", key="input_cancel").strip().upper()
        
        motivo_sel = st.radio(
            "Motivo de la anulación:",
            ["Cambio de día/planes", "Ya no necesito la bici", "Mal tiempo", "Otros motivos"],
            key="motivo_anulacion"
        )
        
        motivo_final = motivo_sel
        if motivo_sel == "Otros motivos":
            motivo_adicional = st.text_input("Por favor, especifica el motivo:", key="motivo_custom")
            if motivo_adicional.strip():
                motivo_final = motivo_adicional.strip()

        if st.button("Anular Reserva", type="secondary", key="btn_cancel"):
            if not codigo_cancel:
                st.error("❌ Por favor, introduce un localizador válido.")
            elif "db_reservas" in st.session_state and codigo_cancel in st.session_state.db_reservas:
                # 1. Lo borramos de la sesión
                del st.session_state.db_reservas[codigo_cancel]
                # 2. Escribimos la anulación real en el archivo histórico común
                anulado_ok = anular_reserva_csv(codigo_cancel, motivo_final)
                
                if anulado_ok:
                    st.success(f"🗑️ La reserva **{codigo_cancel}** ha sido marcada como 'Anulada' de forma permanente.")
                else:
                    st.warning("⚠️ Eliminada de la sesión actual, pero el ID no se localizó en la base histórica.")
            else:
                st.error("❌ Código no encontrado o ya anulado.")

# --- INYECTOR DE BOTONES EN LA VISTA PRINCIPAL ---

def inyectar_asistente_en_ciclista(hora_sugerida="08:00"):
    """Renderiza la botonera compacta nativa de la pantalla de usuario."""
    if "db_reservas" not in st.session_state:
        st.session_state.db_reservas = {}
        
    if "ultimo_localizador_creado" in st.session_state:
        loc_exito = st.session_state.pop("ultimo_localizador_creado")
        st.balloons()
        st.success(f"🎉 **¡Reserva Completada!** Tu localizador único es: **{loc_exito}**")

    col_espacio1, col_b1, col_b2, col_espacio2 = st.columns([1, 3, 3, 1])
    with col_b1:
        if st.button("🎫 Reservar Bicicleta", type="primary", use_container_width=True):
            mostrar_modal_reserva(hora_sugerida)
    with col_b2:
        if st.button("🔍 Gestionar Reservas", use_container_width=True):
            mostrar_modal_gestion()

# --- PANTALLA PRINCIPAL: CUADRO DE MANDO ESTADÍSTICO ---

def mostrar_graficas_analitica():
    """Renderiza gráficos descriptivos leyendo de forma sincronizada desde booking_history.csv."""
    st.write("🔍 ¡La función de las gráficas se está ejecutando!")
    
    if not os.path.exists(archivo_csv):
        st.info(f"ℹ️ El archivo de histórico de reservas (`{archivo_csv}`) aún no contiene registros.")
        return
        
    try:
        df = pd.read_csv(archivo_csv, dtype=str)
        
        # 🌟 CHIVATO 2: Para ver en directo qué ha leído del CSV
        st.write("📊 Datos leídos correctamente. Número de filas:", len(df))
        if not df.empty:
            st.dataframe(df.head()) # Muestra las primeras filas en una tabla normal
            
        if df.empty:
            st.warning("⚠️ El archivo de histórico está vacío.")
            return    

        total_solicitudes = len(df)
        df["status"] = df["status"].str.strip()
        df_confirmadas = df[df["status"] == "Confirmada"]
        df_anuladas = df[df["status"] == "Anulada"]
        
        total_confirmadas = len(df_confirmadas)
        total_anuladas = len(df_anuladas)
        
        df["rating"] = pd.to_numeric(df["rating"], errors='coerce').fillna(5)
        promedio_rating = df["rating"].mean() if total_solicitudes > 0 else 5.0

        st.subheader("📊 Resumen Ejecutivo del Sistema")
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        with col_kpi1:
            st.metric(label="📈 Total Solicitudes", value=total_solicitudes)
        with col_kpi2:
            st.metric(label="🟢 Confirmadas Activas", value=total_confirmadas)
        with col_kpi3:
            st.metric(label="❌ Total Anuladas", value=total_anuladas)
        with col_kpi4:
            bici_score = "🚲" * int(round(promedio_rating)) if promedio_rating > 0 else "❌"
            st.metric(label="⭐ Valoración Media", value=f"{promedio_rating:.1f}/5", delta=bici_score, delta_color="off")
            
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("🔝 Estaciones Más Demandadas")
            if not df_confirmadas.empty:
                df_estaciones = df_confirmadas["station_name"].value_counts().reset_index()
                df_estaciones.columns = ["Estación", "Nº Reservas"]
                st.bar_chart(data=df_estaciones, x="Estación", y="Nº Reservas", color="#2E7D32")
            else:
                st.info("No hay suficientes reservas activas.")
                
        with col_g2:
            st.subheader("⚠️ Motivos de Anulación")
            if total_anuladas > 0:
                df_motivos = df_anuladas["cancellation_reason"].value_counts().reset_index()
                df_motivos.columns = ["Motivo", "Cantidad"]
                st.bar_chart(data=df_motivos, x="Motivo", y="Cantidad", color="#D32F2F")
            else:
                st.success("🟢 ¡Excelente! No se registran cancelaciones en el histórico.")
                
        st.markdown("---")
        st.subheader("⏰ Distribución de Demanda por Horas")
        if not df_confirmadas.empty:
            df_horas = df_confirmadas["booking_time"].value_counts().reset_index()
            df_horas.columns = ["Hora de Reserva", "Cantidad"]
            df_horas = df_horas.sort_values(by="Hora de Reserva")
            st.line_chart(data=df_horas, x="Hora de Reserva", y="Cantidad", color="#1976D2")
        else:
            st.info("Aún no hay datos horarios confirmados.")
            
    except Exception as e:
        st.error(f"❌ Error al procesar las gráficas estadísticas: {e}")
        