import streamlit as st
import pandas as pd
import re

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from io import BytesIO


# ============================================================
# CONFIGURACIÓN DE LA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Analizador de WhatsApp",
    page_icon="📊",
    layout="wide"
)


# ============================================================
# FUNCIONES
# ============================================================

def normalizar_texto(texto):
    """
    Normaliza espacios especiales que aparecen
    en los archivos exportados de WhatsApp.
    """

    texto = texto.replace("\u202f", " ")
    texto = texto.replace("\xa0", " ")

    return texto


def convertir_fecha_hora(fecha_texto, hora_texto, periodo):
    """
    Convierte:

    19/8/2026
    10:03
    a. m.

    en un objeto datetime de Python.
    """

    periodo = periodo.lower().strip()

    hora = datetime.strptime(
        hora_texto,
        "%H:%M"
    )

    horas = hora.hour
    minutos = hora.minute

    # Convertir formato AM / PM
    if "p" in periodo and horas != 12:
        horas += 12

    if "a" in periodo and horas == 12:
        horas = 0

    fecha = datetime.strptime(
        fecha_texto,
        "%d/%m/%Y"
    )

    return datetime(
        fecha.year,
        fecha.month,
        fecha.day,
        horas,
        minutos
    )


def leer_chat_whatsapp(contenido):
    """
    Lee el TXT completo de WhatsApp.

    Detecta mensajes de varias líneas y devuelve
    fecha, remitente y contenido.
    """

    contenido = normalizar_texto(contenido)

    lineas = contenido.splitlines()

    mensajes = []

    mensaje_actual = None

    # Ejemplo:
    # 19/8/2026, 10:03 a. m. - Agentesautorizados: mensaje

    patron = re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{4}),\s*"
        r"(\d{1,2}:\d{2})\s*"
        r"([ap]\.\s*m\.)\s*-\s*"
        r"([^:]+):\s*(.*)$",
        re.IGNORECASE
    )

    for linea in lineas:

        coincidencia = patron.match(linea)

        if coincidencia:

            # Guardar mensaje anterior
            if mensaje_actual is not None:
                mensajes.append(mensaje_actual)

            fecha_texto = coincidencia.group(1)
            hora_texto = coincidencia.group(2)
            periodo = coincidencia.group(3)
            remitente = coincidencia.group(4).strip()
            texto = coincidencia.group(5).strip()

            try:

                fecha_hora = convertir_fecha_hora(
                    fecha_texto,
                    hora_texto,
                    periodo
                )

            except Exception:
                fecha_hora = None

            mensaje_actual = {
                "fecha_hora": fecha_hora,
                "remitente": remitente,
                "mensaje": texto
            }

        else:

            # Si la línea no comienza con fecha/hora,
            # pertenece al mensaje anterior.

            if mensaje_actual is not None:

                mensaje_actual["mensaje"] += "\n" + linea

    # Guardar último mensaje
    if mensaje_actual is not None:
        mensajes.append(mensaje_actual)

    return mensajes


def detectar_tipo_solicitud(mensaje):
    """
    Determina si el mensaje es:

    SOLICITUD
    SOLICITUD-R
    """

    texto = mensaje.upper()

    # Primero comprobamos SOLICITUD-R
    # para evitar confundirla con SOLICITUD.

    if re.search(
        r"\bSOLICITUD\s*-\s*R\b",
        texto
    ):
        return "SOLICITUD-R"

    if re.search(
        r"\bSOLICITUD\b",
        texto
    ):
        return "SOLICITUD"

    return None


def extraer_rif(mensaje):
    """
    Extrae el RIF del bloque.

    Ejemplos:
    V192856201
    G200002085
    """

    patron = re.search(
        r"RIF\s*:\s*([A-Z]?\s*-?\s*\d+)",
        mensaje,
        re.IGNORECASE
    )

    if not patron:
        return ""

    rif = patron.group(1)

    rif = rif.upper()
    rif = rif.replace(" ", "")
    rif = rif.replace("-", "")

    return rif


def analizar_solicitudes(mensajes, desde, hasta):
    """
    Filtra por período y detecta solicitudes/respuestas.
    """

    registros = []

    for mensaje in mensajes:

        fecha_hora = mensaje["fecha_hora"]

        if fecha_hora is None:
            continue

        # Filtrar período seleccionado
        if not (desde <= fecha_hora <= hasta):
            continue

        tipo = detectar_tipo_solicitud(
            mensaje["mensaje"]
        )

        if tipo is None:
            continue

        rif = extraer_rif(
            mensaje["mensaje"]
        )

        registros.append({
            "Fecha y hora": fecha_hora,
            "Remitente": mensaje["remitente"],
            "Tipo": tipo,
            "RIF": rif,
            "Mensaje": mensaje["mensaje"]
        })

    return pd.DataFrame(registros)


def relacionar_solicitudes(df):
    """
    Relaciona una SOLICITUD con su SOLICITUD-R
    principalmente mediante el RIF.

    Toma la primera respuesta posterior
    que tenga el mismo RIF.
    """

    solicitudes = df[
        df["Tipo"] == "SOLICITUD"
    ].copy()

    respuestas = df[
        df["Tipo"] == "SOLICITUD-R"
    ].copy()

    solicitudes = solicitudes.sort_values(
        "Fecha y hora"
    )

    respuestas = respuestas.sort_values(
        "Fecha y hora"
    )

    respuestas_usadas = set()

    resultado = []

    for indice_solicitud, solicitud in solicitudes.iterrows():

        rif = solicitud["RIF"]

        respuesta_encontrada = None
        indice_respuesta_encontrada = None

        # Solo podemos relacionar automáticamente
        # mediante RIF si existe.

        if rif:

            for indice_respuesta, respuesta in respuestas.iterrows():

                if indice_respuesta in respuestas_usadas:
                    continue

                if respuesta["RIF"] != rif:
                    continue

                if respuesta["Fecha y hora"] < solicitud["Fecha y hora"]:
                    continue

                respuesta_encontrada = respuesta
                indice_respuesta_encontrada = indice_respuesta

                break

        if respuesta_encontrada is not None:

            respuestas_usadas.add(
                indice_respuesta_encontrada
            )

            diferencia = (
                respuesta_encontrada["Fecha y hora"]
                - solicitud["Fecha y hora"]
            )

            minutos_respuesta = round(
                diferencia.total_seconds() / 60,
                1
            )

            estado = "Contestada"

            fecha_respuesta = respuesta_encontrada[
                "Fecha y hora"
            ]

        else:

            estado = "Sin contestar"
            fecha_respuesta = None
            minutos_respuesta = None

        resultado.append({
            "Fecha solicitud":
                solicitud["Fecha y hora"],

            "Solicitante":
                solicitud["Remitente"],

            "RIF":
                rif,

            "Estado":
                estado,

            "Fecha respuesta":
                fecha_respuesta,

            "Tiempo respuesta (min)":
                minutos_respuesta
        })

    detalle = pd.DataFrame(resultado)

    # Respuestas que no pudieron relacionarse
    respuestas_sin_vincular = respuestas[
        ~respuestas.index.isin(respuestas_usadas)
    ].copy()

    return detalle, respuestas_sin_vincular


def crear_excel(
    detalle,
    respuestas_sin_vincular,
    resumen
):

    salida = BytesIO()

    with pd.ExcelWriter(
        salida,
        engine="openpyxl"
    ) as writer:

        resumen.to_excel(
            writer,
            index=False,
            sheet_name="Resumen"
        )

        detalle.to_excel(
            writer,
            index=False,
            sheet_name="Solicitudes"
        )

        respuestas_sin_vincular.to_excel(
            writer,
            index=False,
            sheet_name="Respuestas sin vincular"
        )

    salida.seek(0)

    return salida


# ============================================================
# TÍTULO
# ============================================================

st.title("Analizador de Atención al Cliente")

st.write(
    "Carga el archivo TXT exportado de WhatsApp "
    "para generar las estadísticas."
)


# ============================================================
# CARGA DEL ARCHIVO
# ============================================================

archivo = st.file_uploader(
    "Sube el archivo TXT exportado de WhatsApp",
    type=["txt"]
)


# ============================================================
# ARCHIVO CARGADO
# ============================================================

if archivo is not None:

    try:

        contenido = archivo.read().decode(
            "utf-8"
        )

    except UnicodeDecodeError:

        archivo.seek(0)

        contenido = archivo.read().decode(
            "utf-8-sig",
            errors="replace"
        )


    st.success(
        "Archivo cargado correctamente"
    )

    st.divider()


    # ========================================================
    # FECHA Y HORA
    # ========================================================

    st.subheader(
        "Período a analizar"
    )

    zona_venezuela = ZoneInfo(
        "America/Caracas"
    )

    ahora = datetime.now(
        zona_venezuela
    )

    hoy = ahora.date()


    # Si hoy es lunes:
    # viernes anterior.

    if hoy.weekday() == 0:

        fecha_desde_default = (
            hoy - timedelta(days=3)
        )

    else:

        fecha_desde_default = (
            hoy - timedelta(days=1)
        )


    # Hora predeterminada
    # 16:30 = 4:30 PM

    hora_default = time(
        16,
        30
    )


    # ========================================================
    # INTERVALO DE MINUTOS
    # ========================================================

    intervalo_minutos = st.selectbox(
        "Intervalo para seleccionar la hora",
        options=[
            5,
            10,
            15,
            20,
            30
        ],
        index=1,
        format_func=lambda x:
            f"Cada {x} minutos"
    )


    # ========================================================
    # CREAR HORAS
    # ========================================================

    horas = []

    for hora in range(24):

        for minuto in range(
            0,
            60,
            intervalo_minutos
        ):

            hora_obj = time(
                hora,
                minuto
            )

            texto_hora = datetime.strptime(
                f"{hora:02d}:{minuto:02d}",
                "%H:%M"
            ).strftime(
                "%I:%M %p"
            )

            texto_hora = (
                texto_hora.lstrip("0")
            )

            horas.append(
                (
                    texto_hora,
                    hora_obj
                )
            )


    # ========================================================
    # BUSCAR HORA MÁS CERCANA A 4:30 PM
    # ========================================================

    def minutos_del_dia(hora_obj):

        return (
            hora_obj.hour * 60
            + hora_obj.minute
        )


    minutos_default = minutos_del_dia(
        hora_default
    )

    indice_default = min(
        range(len(horas)),
        key=lambda i: abs(
            minutos_del_dia(
                horas[i][1]
            )
            - minutos_default
        )
    )


    # ========================================================
    # DESDE / HASTA
    # ========================================================

    col1, col2 = st.columns(2)


    with col1:

        st.markdown(
            "### Desde"
        )

        fecha_desde = st.date_input(
            "Fecha desde",
            value=fecha_desde_default,
            format="DD/MM/YYYY",
            key="fecha_desde"
        )

        hora_desde_texto = st.selectbox(
            "Hora desde",
            options=[
                texto
                for texto, _ in horas
            ],
            index=indice_default,
            key="hora_desde"
        )

        hora_desde = dict(
            horas
        )[hora_desde_texto]


    with col2:

        st.markdown(
            "### Hasta"
        )

        fecha_hasta = st.date_input(
            "Fecha hasta",
            value=hoy,
            format="DD/MM/YYYY",
            key="fecha_hasta"
        )

        hora_hasta_texto = st.selectbox(
            "Hora hasta",
            options=[
                texto
                for texto, _ in horas
            ],
            index=indice_default,
            key="hora_hasta"
        )

        hora_hasta = dict(
            horas
        )[hora_hasta_texto]


    desde = datetime.combine(
        fecha_desde,
        hora_desde
    )

    hasta = datetime.combine(
        fecha_hasta,
        hora_hasta
    )


    st.divider()


    # ========================================================
    # VALIDACIÓN
    # ========================================================

    if desde >= hasta:

        st.error(
            "La fecha y hora 'Desde' debe "
            "ser anterior a la fecha y hora 'Hasta'."
        )

    else:

        desde_texto = desde.strftime(
            "%d/%m/%Y %I:%M %p"
        )

        hasta_texto = hasta.strftime(
            "%d/%m/%Y %I:%M %p"
        )

        desde_texto = desde_texto.replace(
            " 0",
            " "
        )

        hasta_texto = hasta_texto.replace(
            " 0",
            " "
        )

        st.info(
            f"Período seleccionado: "
            f"desde {desde_texto} "
            f"hasta {hasta_texto}"
        )


        # ====================================================
        # LEER Y ANALIZAR CHAT
        # ====================================================

        mensajes = leer_chat_whatsapp(
            contenido
        )

        df = analizar_solicitudes(
            mensajes,
            desde,
            hasta
        )


        # ====================================================
        # SI NO HAY REGISTROS
        # ====================================================

        if df.empty:

            st.warning(
                "No se encontraron SOLICITUDES "
                "ni SOLICITUD-R dentro del período seleccionado."
            )

        else:

            detalle, respuestas_sin_vincular = (
                relacionar_solicitudes(df)
            )


            # =================================================
            # ESTADÍSTICAS
            # =================================================

            total_solicitudes = len(
                detalle
            )

            total_contestadas = (
                detalle["Estado"]
                .eq("Contestada")
                .sum()
            )

            total_sin_contestar = (
                detalle["Estado"]
                .eq("Sin contestar")
                .sum()
            )

            total_respuestas = len(
                df[
                    df["Tipo"]
                    == "SOLICITUD-R"
                ]
            )


            if total_solicitudes > 0:

                porcentaje_respuesta = (
                    total_contestadas
                    / total_solicitudes
                    * 100
                )

            else:

                porcentaje_respuesta = 0


            # =================================================
            # MOSTRAR ESTADÍSTICAS
            # =================================================

            st.subheader(
                "Estadísticas"
            )

            col1, col2, col3, col4 = (
                st.columns(4)
            )


            with col1:

                st.metric(
                    "Solicitudes",
                    total_solicitudes
                )


            with col2:

                st.metric(
                    "Contestadas",
                    total_contestadas
                )


            with col3:

                st.metric(
                    "Sin contestar",
                    total_sin_contestar
                )


            with col4:

                st.metric(
                    "Tasa de respuesta",
                    f"{porcentaje_respuesta:.1f}%"
                )


            # =================================================
            # GRÁFICA
            # =================================================

            st.subheader(
                "Solicitudes vs contestadas"
            )

            grafica = pd.DataFrame({
                "Cantidad": [
                    total_solicitudes,
                    total_contestadas,
                    total_sin_contestar
                ]
            },
                index=[
                    "Solicitudes",
                    "Contestadas",
                    "Sin contestar"
                ]
            )

            st.bar_chart(
                grafica
            )


            # =================================================
            # INFORMACIÓN ADICIONAL
            # =================================================

            st.caption(
                f"Se detectaron "
                f"{total_respuestas} mensajes "
                f"de tipo SOLICITUD-R "
                f"dentro del período seleccionado."
            )


            if len(
                respuestas_sin_vincular
            ) > 0:

                st.caption(
                    f"{len(respuestas_sin_vincular)} "
                    f"respuesta(s) no pudieron "
                    f"vincularse con una solicitud "
                    f"del período mediante el RIF."
                )


            # =================================================
            # CREAR RESUMEN PARA EXCEL
            # =================================================

            resumen = pd.DataFrame({
                "Indicador": [
                    "Solicitudes",
                    "Contestadas",
                    "Sin contestar",
                    "Total SOLICITUD-R detectadas",
                    "Respuestas sin vincular",
                    "Tasa de respuesta"
                ],

                "Resultado": [
                    total_solicitudes,
                    total_contestadas,
                    total_sin_contestar,
                    total_respuestas,
                    len(
                        respuestas_sin_vincular
                    ),
                    f"{porcentaje_respuesta:.1f}%"
                ]
            })


            # =================================================
            # EXCEL
            # =================================================

            archivo_excel = crear_excel(
                detalle,
                respuestas_sin_vincular,
                resumen
            )


            st.divider()


            st.download_button(
                label="📥 Descargar Excel",
                data=archivo_excel,
                file_name=(
                    "estadisticas_whatsapp_"
                    f"{fecha_hasta.strftime('%d-%m-%Y')}"
                    ".xlsx"
                ),
                mime=(
                    "application/"
                    "vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )