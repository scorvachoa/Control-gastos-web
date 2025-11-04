from flask import Flask, render_template, request, jsonify
import pandas as pd
from google.oauth2 import service_account
import gspread
from datetime import datetime

app = Flask(__name__)

# --- Configuración de Google Sheets ---
SHEET_NAME = "Control de Gastos Telegram"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS_PATH = "creds/service_account.json"

credentials = service_account.Credentials.from_service_account_file(
    CREDS_PATH, scopes=SCOPES
)
gc = gspread.authorize(credentials)
sheet = gc.open(SHEET_NAME).sheet1


# --- Función para obtener datos desde Google Sheets ---
def obtener_datos_google_sheets():
    datos = sheet.get_all_records()
    df = pd.DataFrame(datos)
    return df


# --- Rutas ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/agregar_gasto", methods=["POST"])
def agregar_gasto():
    data = request.json
    # 🔹 Fecha y hora actual en formato dd/mm/yyyy HH:MM:SS
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    categoria = data.get("categoria", "")
    monto = float(data.get("monto", 0))
    descripcion = data.get("descripcion", "")
    usuario = "Smith"

    sheet.append_row([fecha_actual, categoria, monto, descripcion, usuario])
    return jsonify({"status": "ok", "mensaje": "Gasto guardado correctamente"})


@app.route("/reporte_mensual")
def reporte_mensual():
    df = obtener_datos_google_sheets()

    if df.empty:
        return jsonify({"error": "No hay datos disponibles"}), 400

    df.columns = df.columns.str.strip().str.capitalize()
    if "Fecha" not in df.columns or "Monto" not in df.columns or "Categoría" not in df.columns:
        return jsonify({"error": "Formato de datos incorrecto"}), 400

    # Convertir la fecha automáticamente (día primero)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["Fecha"])

    mes = request.args.get("mes")  # Formato: YYYY-MM
    if mes:
        try:
            año, mes_num = map(int, mes.split("-"))
            df = df[(df["Fecha"].dt.year == año) & (df["Fecha"].dt.month == mes_num)]
        except Exception as e:
            print("Error en filtro:", e)

    if df.empty:
        return jsonify({"reporte": [], "total": 0})

    df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
    resumen = df.groupby("Categoría")["Monto"].sum().reset_index()
    resumen["Monto"] = resumen["Monto"].astype(float)

    reporte = resumen.to_dict(orient="records")
    total = float(df["Monto"].sum())

    return jsonify({"reporte": reporte, "total": total})


if __name__ == "__main__":
    app.run(debug=True)
