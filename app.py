import streamlit as st
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo


# --------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# --------------------------------------------------

st.set_page_config(
    page_title="Analizador de WhatsApp",
    page_icon="📊",
    layout="wide"
)


# --------------------------------------------------
# TÍTULO
# --------------------------------------------------

st.title("Analizador de Atención al Cliente")

st.write(
    "Carga el archivo TXT exportado de WhatsApp para comenzar el análisis."
)


# --------------------------------------------------
# CARGA DEL ARCHIVO
# --------------------------------------------------

archivo = st.file_uploader(
    "Sube el archivo TXT exportado de WhatsApp",
    type=["txt"]
)


# --------------------------------------------------
# SI SE CARGÓ UN ARCHIVO
# --------------------------------------------------

if archivo is not None:

    st.success("Archivo cargado correctamente")

    st.divider()

    st.subheader("Período a analizar")


    # --------------------------------------------------
    # FECHA ACTUAL EN VENEZUELA
    # --------------------------------------------------

    zona_venezuela = ZoneInfo("America/Caracas")
    ahora = datetime.now(zona_venezuela)
    hoy = ahora.date()


    # --------------------------------------------------
    # CALCULAR FECHA "DESDE" POR DEFECTO
    #
    # Si hoy es lunes:
    # viernes anterior
    #
    # Si no:
    # día anterior
    # --------------------------------------------------

    if hoy.weekday() == 0:
        fecha_desde_default = hoy - timedelta(days=3)
    else:
        fecha_desde_default = hoy - timedelta(days=1)


    # --------------------------------------------------
    # HORA POR DEFECTO
    # 16:30 = 4:30 PM
    # --------------------------------------------------

    hora_default = time(16, 30)


    # --------------------------------------------------
    # INTERVALO DE MINUTOS
    # --------------------------------------------------

    intervalo_minutos = st.selectbox(
        "Intervalo para seleccionar la hora",
        options=[5, 10, 15, 20, 30],
        index=1,
        format_func=lambda x: f"Cada {x} minutos"
    )


    # --------------------------------------------------
    # CREAR LISTA DE HORAS
    # --------------------------------------------------

    horas = []

    for hora in range(24):

        for minuto in range(0, 60, intervalo_minutos):

            hora_obj = time(hora, minuto)

            texto_hora = datetime.strptime(
                f"{hora:02d}:{minuto:02d}",
                "%H:%M"
            ).strftime("%I:%M %p")

            # Quitar cero inicial
            # 04:30 PM -> 4:30 PM
            texto_hora = texto_hora.lstrip("0")

            horas.append(
                (texto_hora, hora_obj)
            )


    # --------------------------------------------------
    # BUSCAR 4:30 PM COMO HORA POR DEFECTO
    #
    # Si el intervalo elegido no contiene 4:30 PM,
    # buscamos la hora más cercana.
    # --------------------------------------------------

    def minutos_del_dia(hora_obj):
        return hora_obj.hour * 60 + hora_obj.minute


    minutos_default = minutos_del_dia(hora_default)

    indice_default = min(
        range(len(horas)),
        key=lambda i: abs(
            minutos_del_dia(horas[i][1]) - minutos_default
        )
    )


    # --------------------------------------------------
    # COLUMNAS DESDE / HASTA
    # --------------------------------------------------

    col1, col2 = st.columns(2)


    # --------------------------------------------------
    # DESDE
    # --------------------------------------------------

    with col1:

        st.markdown("### Desde")

        fecha_desde = st.date_input(
            "Fecha desde",
            value=fecha_desde_default,
            format="DD/MM/YYYY",
            key="fecha_desde"
        )

        hora_desde_texto = st.selectbox(
            "Hora desde",
            options=[texto for texto, _ in horas],
            index=indice_default,
            key="hora_desde"
        )

        hora_desde = dict(horas)[hora_desde_texto]


    # --------------------------------------------------
    # HASTA
    # --------------------------------------------------

    with col2:

        st.markdown("### Hasta")

        fecha_hasta = st.date_input(
            "Fecha hasta",
            value=hoy,
            format="DD/MM/YYYY",
            key="fecha_hasta"
        )

        hora_hasta_texto = st.selectbox(
            "Hora hasta",
            options=[texto for texto, _ in horas],
            index=indice_default,
            key="hora_hasta"
        )

        hora_hasta = dict(horas)[hora_hasta_texto]


    # --------------------------------------------------
    # UNIR FECHA + HORA
    # --------------------------------------------------

    desde = datetime.combine(
        fecha_desde,
        hora_desde
    )

    hasta = datetime.combine(
        fecha_hasta,
        hora_hasta
    )


    st.divider()


    # --------------------------------------------------
    # VALIDAR RANGO
    # --------------------------------------------------

    if desde >= hasta:

        st.error(
            "La fecha y hora 'Desde' debe ser anterior "
            "a la fecha y hora 'Hasta'."
        )

    else:

        # Formato 12 horas
        desde_texto = desde.strftime(
            "%d/%m/%Y %I:%M %p"
        )

        hasta_texto = hasta.strftime(
            "%d/%m/%Y %I:%M %p"
        )

        # Quitar cero inicial de la hora
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