from flask import Flask, render_template, request, jsonify
import pandas as pd
from google.oauth2 import service_account
import gspread
from datetime import datetime
import unicodedata
import re

app = Flask(__name__)

# === CONFIGURACIÓN GOOGLE SHEETS ===
SHEET_NAME = "Control de Gastos Telegram"  # nombre exacto de tu hoja
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS_PATH = "creds/service_account.json"  # ruta del JSON de credenciales

credentials = service_account.Credentials.from_service_account_file(
    CREDS_PATH, scopes=SCOPES
)
gc = gspread.authorize(credentials)
sheet = gc.open(SHEET_NAME).sheet1


# === UTILIDADES ===
def quitar_acentos(s: str) -> str:
    if not isinstance(s, str):
        return s
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def limpiar_monto_raw(raw):
    """
    Limpia una cadena que representa un monto recibido desde Google Sheets.
    - Elimina símbolos no numéricos salvo '.' y ','
    - Si existe ',' y no '.', interpreta ',' como decimal -> reemplaza por '.'
    - Si existen ambos, asume que '.' es decimal o que '.' es separador de miles (tratamos así):
        * Si el último separador visible es ',', lo tratamos como decimal (reemplazamos , -> . y quitamos puntos)
        * Si el último separador visible es '.', lo tratamos como decimal (quitamos comas)
    - Manejo simple, funciona para formatos comunes como:
        "1.234,56", "1,234.56", "2,5", "$ 1.000", "25"
    """
    if pd.isna(raw):
        return None
    s = str(raw).strip()

    # eliminar espacios y simbolos de moneda (dejamos solo dígitos, coma y punto)
    s = re.sub(r"[^\d\.,\-]", "", s)

    if s == "":
        return None

    # detectar posiciones
    has_comma = "," in s
    has_dot = "." in s

    # Caso: solo coma -> coma es decimal -> reemplazar por punto
    if has_comma and not has_dot:
        s = s.replace(",", ".")
    # Caso: solo dot -> dot es decimal (no hacer nada)
    elif has_dot and not has_comma:
        pass
    # Caso: ambos presentes -> decidir cuál es decimal
    elif has_dot and has_comma:
        # si la última aparición es coma -> coma decimal (ej: "1.234,56")
        if s.rfind(",") > s.rfind("."):
            # quitar todos los puntos (miles) y convertir coma a punto
            s = s.replace(".", "").replace(",", ".")
        else:
            # última aparición es punto -> quitar todas las comas (miles), mantener punto decimal
            s = s.replace(",", "")

    # finalmente, tratar casos de signo negativo
    # ya sólo queda algo como "-1234.56" o "1234.56" o "25"
    try:
        # convertir a float
        return float(s)
    except Exception:
        return None


# Mapa de normalización de categorías (puedes ampliar)
CATEGORIA_MAP = {
    "comida": "alimentacion",
    "alimentacion": "alimentacion",
    "alimentación": "alimentacion",
    "transporte": "transporte",
    "servicios": "servicios",
    "entretenimiento": "entretenimiento",
    "otros": "otros",
    "otro": "otros",
    # añade más mapeos que quieras unificar
}


def normalizar_categoria(cat):
    if pd.isna(cat):
        return "otros"
    s = str(cat).strip().lower()
    s = quitar_acentos(s)
    # intentar mapear
    if s in CATEGORIA_MAP:
        return CATEGORIA_MAP[s]
    # si no está en el map, usar versión sin acentos y sin espacios
    s_clean = re.sub(r"\s+", " ", s)
    return s_clean


# === FUNCIONES DE DATOS ===
def obtener_datos_google_sheets():
    """Lee todos los datos desde Google Sheets y devuelve un DataFrame normalizado"""
    datos = sheet.get_all_records()
    if not datos:
        return pd.DataFrame()

    df = pd.DataFrame(datos)

    # Normalizar nombres de columnas: quitar espacios, pasar a minúsculas, quitar acentos
    df.columns = [quitar_acentos(str(c).strip().lower()) for c in df.columns]

    # Renombrar columnas esperadas por nombres simples si existen variantes
    # por ejemplo: 'categoría' -> 'categoria'
    rename_map = {}
    for c in df.columns:
        if "categoria" in c:
            rename_map[c] = "categoria"
        if "monto" in c:
            rename_map[c] = "monto"
        if "fecha" in c:
            rename_map[c] = "fecha"
        if "descripcion" in c:
            rename_map[c] = "descripcion"
        if "usuario" in c:
            rename_map[c] = "usuario"
    if rename_map:
        df = df.rename(columns=rename_map)

    # Asegurar columnas mínimas
    for col in ["fecha", "categoria", "monto", "descripcion", "usuario"]:
        if col not in df.columns:
            df[col] = None

    # Limpiar montos: usar función robusta
    df["monto_limpio"] = df["monto"].apply(limpiar_monto_raw)
    # si la conversión falló, poner 0
    df["monto_limpio"] = df["monto_limpio"].fillna(0.0)

    # Normalizar categorías
    df["categoria_norm"] = df["categoria"].apply(normalizar_categoria)

    # (opcional) convertir fecha a datetime si quieres filtrar por mes
    # Intentamos parsear fechas comunes
    df["fecha_parsed"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)

    # devolvemos DataFrame con columnas útiles
    return df


# === RUTAS ===
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/agregar_gasto", methods=["POST"])
def agregar_gasto():
    """Recibe datos del formulario y los guarda en Google Sheets"""
    data = request.json
    fecha = data.get("fecha", datetime.now().strftime("%Y-%m-%d"))
    categoria = data.get("categoria", "")
    monto = data.get("monto", 0)
    descripcion = data.get("descripcion", "")
    usuario = "Smith"  # fijo por ahora

    # Guardamos el monto tal como viene (si el frontend envía número, google lo pone como número)
    sheet.append_row([fecha, categoria, monto, descripcion, usuario])

    return jsonify({"status": "ok", "mensaje": "✅ Gasto guardado correctamente"})


@app.route("/reporte_mensual")
def reporte_mensual():
    """Genera el resumen mensual de gastos (por categoría unificada)"""
    df = obtener_datos_google_sheets()
    if df.empty:
        return jsonify({"categorias": [], "montos": [], "total": 0.0})

    # Tomamos la categoría normalizada y el monto limpio
    resumen = (
        df.groupby("categoria_norm")["monto_limpio"]
        .sum()
        .reset_index()
        .rename(columns={"categoria_norm": "categoria", "monto_limpio": "monto"})
    )

    # Opcional: si quieres mapear nombres 'alimentacion' a 'Alimentación' para mostrar bonito:
    display_name = {
        "alimentacion": "Alimentación",
        "transporte": "Transporte",
        "servicios": "Servicios",
        "entretenimiento": "Entretenimiento",
        "otros": "Otros"
    }
    resumen["categoria_display"] = resumen["categoria"].apply(lambda x: display_name.get(x, x.title()))

    categorias = resumen["categoria_display"].tolist()
    montos = resumen["monto"].astype(float).tolist()
    total = float(resumen["monto"].sum())

    return jsonify({
        "categorias": categorias,
        "montos": montos,
        "total": total
    })


if __name__ == "__main__":
    app.run(debug=True)
