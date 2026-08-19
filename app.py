import streamlit as st

st.set_page_config(
    page_title="Analizador de WhatsApp",
    page_icon="📊",
    layout="wide"
)

st.title("Analizador de Atención al Cliente")

st.write("Primera versión de la aplicación")

archivo = st.file_uploader(
    "Sube el archivo TXT exportado de WhatsApp",
    type=["txt"]
)

if archivo is not None:
    st.success("Archivo cargado correctamente")
