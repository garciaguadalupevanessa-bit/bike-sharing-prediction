import os
import csv
import string
import random
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, time

# --- CONFIGURACIÓN DE RUTA HISTÓRICO CSV ---
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

# --- FUNCIONES DE PERSISTENCIA EN BASE DE DATOS (SIN CACHÉ PROBLEMÁTICA) ---

def guardar_reserva_csv(localizador, estacion, fecha, hora, nombre, telefono, rating=5):
    """Guarda una reserva confirmada con su valoración en el CSV de forma directa."""
    nueva_fila = [
        localizador,                                 # booking_id
        estacion,                                    # station_name
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
    """Busca una reserva por localizador en el CSV y la marca como Anulada de forma segura."""
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

# --- MODAL 1: FORMULARIO DE RESERVA (SÓLO UX, SIN MENÚS DUPLICADOS) ---

@st.dialog("🎫 Formulario de Reserva BiciMAD")
def mostrar_modal_reserva(hora_sugerida):
    """Abre un pop-up flotante limpio con calendario y selector completo de estaciones."""
    st.write("📋 **Completa los detalles de tu reserva futura:**")
    st.markdown("---")
    
    # Intentamos recuperar de forma dinámica todas las estaciones desde el archivo o sesión principal
    if "estaciones_data" in st.session_state and hasattr(st.session_state.estaciones_data, "empty") and not st.session_state.estaciones_data.empty:
        # Si tienes guardado un dataframe en session_state lo extraemos directamente
        lista_estaciones = st.session_state.estaciones_data["name"].tolist()
    elif os.path.exists(os.path.join("data", "estaciones.csv")):
        try:
            df_est = pd.read_csv(os.path.join("data", "estaciones.csv"))
            lista_estaciones = df_est["name"].tolist()
        except:
            lista_estaciones = ["1 - Puerta del Sol A", "7 - Colegio de Arquitectos", "10 - Plaza de la Paja", "45 - Antón Martín", "64 - Plaza de la Cebada"]
    else:
        # Lista extendida de seguridad por si falla la lectura de datos dinámicos
        lista_estaciones = [
            "1a - Puerta del Sol A", "1b - Puerta del Sol B", "7 - Colegio de Arquitectos", 
            "10 - Plaza de la Paja", "43 - Plaza de Jacinto Benavente", "45 - Antón Martín", 
            "64 - Plaza de la Cebada", "148 - Doctor Arce 45", "172 - Colombia", "174 - Segovia 26"
        ]
    
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
        
    fecha_final = datetime.combine(fecha_reserva, hora_reserva)
    ahora = datetime.now()
    horas_antelacion = (fecha_final - ahora).total_seconds() / 3600
    
    if horas_antelacion < 24:
        st.error("⏳ **Margen insuficiente:** Las reservas automáticas requieren más de 24h de antelación.")
    else:
        st.success("🟢 **Margen correcto:** El sistema bloqueará una bicicleta para la fecha indicada.")
        
        st.markdown("**🚲 ¡Valora tu experiencia con la aplicación!**")
        rating_bicis = st.select_slider(
            "¿Cuántas bicis nos das?",
            options=["🚲", "🚲🚲", "🚲🚲🚲", "🚲🚲🚲🚲", "🚲🚲🚲🚲🚲"],
            value="🚲🚲🚲🚲🚲"
        )
        rating_usuario = len(rating_bicis) // len("🚲")
        
        with st.form("form_interno_reserva", clear_on_submit=True):
            nombre = st.text_input("Nombre completo del titular:")
            telefono = st.text_input("Teléfono móvil:")
            btn_confirmar = st.form_submit_button("Confirmar Reserva")
            
            if btn_confirmar:
                if not nombre.strip() or not telefono.strip():
                    st.error("❌ Por favor, rellena todos los campos obligatorios.")
                else:
                    loc = generar_localizador()
                    
                    if "db_reservas" not in st.session_state:
                        st.session_state.db_reservas = {}
                        
                    st.session_state.db_reservas[loc] = {
                        "titular": nombre,
                        "telefono": telefono,
                        "estacion": estacion_seleccionada,
                        "fecha_hora": fecha_final.strftime("%d/%m/%Y a las %H:%Mh"),
                        "status": "Confirmada"
                    }
                    
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

# --- MODAL 2: GESTIÓN DE RESERVAS (SÓLO ACCIONES UX, SIN RE-ENTRADAS DE DIALOGS) ---

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
                
                # 1. Modificación en la sesión viva de memoria
                del st.session_state.db_reservas[codigo_cancel]
                
                # 2. Impacto inmediato sobre el archivo CSV
                anulado_ok = anular_reserva_csv(codigo_cancel, motivo_final)
                
                if anulado_ok:
                    st.success(f"🗑️ La reserva **{codigo_cancel}** ha sido marcada como 'Anulada' de forma permanente.")
                    st.info("💡 Éxito. Puedes cerrar esta ventana; los gráficos cambiarán de inmediato al actualizar la pestaña externa.")
                else:
                    st.warning("⚠️ Eliminada de la sesión actual, pero el ID no se localizó en la base histórica.")
            else:
                st.error("❌ Código no encontrado o ya anulado.")

# --- INYECTOR DE BOTONES EN LA VISTA PRINCIPAL (USER EXPERIENCE) ---

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
    """Renderiza gráficos descriptivos en tiempo real dentro de la pestaña principal."""
    if not os.path.exists(archivo_csv):
        st.info(f"ℹ️ El archivo de histórico de reservas (`{archivo_csv}`) aún no contiene registros.")
        return
        
    try:
        df = pd.read_csv(archivo_csv, dtype=str)
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

        st.subheader("📊 Resumen Ejecutivo del System")
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