# -*- coding: utf-8 -*-
import re
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ==============================================
# DICCIONARIO DE TRADUCCIÓN
# ==============================================
TRADUCCIONES = {
    "pcm": "paracetamol",
    "etm": "eritromicina",
    "amc": "amoxicilina",
    "tylenol": "paracetamol",
    "dolex": "paracetamol",
    "aspirina": "acido acetilsalicilico",
    "advil": "ibuprofeno",
    "klaricid": "claritromicina",
    "paracetamol": "paracetamol",
    "ibuprofeno": "ibuprofeno",
    "amoxicilina": "amoxicilina",
    "eritromicina": "eritromicina",
    "metamizol": "metamizol",
}

# ==============================================
# ANALIZADOR LEXICO
# ==============================================
class AnalizadorLexico:
    def __init__(self):
        self.patrones = [
            ("MEDICAMENTO", r'\b(pcm|etm|amc|tylenol|dolex|aspirina|advil|klaricid|paracetamol|ibuprofeno|amoxicilina|eritromicina|metamizol)\b'),
            ("NUMERO", r'\b\d+\b'),
            ("UNIDAD", r'\b(mg|g|ml|tableta)\b'),
            ("FRECUENCIA", r'\b(cada\s+\d+\s*horas?|dosis\s+unica)\b'),
            ("VIA", r'\b(oral|intravenosa)\b'),
            ("ESPACIO", r'\s+'),
        ]
    
    def tokenizar(self, texto):
        texto = texto.lower()
        tokens = []
        pos = 0
        while pos < len(texto):
            encontrado = False
            for tipo, patron in self.patrones:
                regex = re.compile(patron)
                match = regex.match(texto, pos)
                if match:
                    valor = match.group(0)
                    if tipo != "ESPACIO":
                        tokens.append((tipo, valor))
                    pos = match.end(0)
                    encontrado = True
                    break
            if not encontrado:
                pos += 1
        return tokens

# ==============================================
# TRADUCTOR
# ==============================================
def traducir_receta(tokens):
    medicamento_original = None
    medicamento_traducido = None
    reconocido = True
    
    for tipo, valor in tokens:
        if tipo == "MEDICAMENTO":
            medicamento_original = valor
            if valor in TRADUCCIONES:
                medicamento_traducido = TRADUCCIONES[valor]
                reconocido = True
            else:
                medicamento_traducido = None
                reconocido = False
            break
    
    return medicamento_original, medicamento_traducido, reconocido

# ==============================================
# RUTAS DE FLASK
# ==============================================

# Ruta 1: Renderiza la interfaz gráfica del usuario
@app.route("/")
def home():
    return render_template("index.html")

# Ruta 2: Procesa la entrada usando tu analizador léxico y traductor
@app.route("/procesar", methods=["POST"])
def procesar():
    # Obtenemos los datos enviados desde el formulario web
    datos_recibidos = request.get_json()
    receta = datos_recibidos.get("receta", "")
    
    # Ejecutamos TU lógica del compilador
    lexico = AnalizadorLexico()
    tokens = lexico.tokenizar(receta)
    original, traducido, reconocido = traducir_receta(tokens)
    
    # Formateamos los tokens para mostrarlos bonitos en la web
    lista_tokens = [f"{tipo}: {valor}" for tipo, valor in tokens]
    
    # Respondemos a la página web con los resultados en formato JSON
    return jsonify({
        "tokens": lista_tokens,
        "original": original if original else "No detectado",
        "traducido": traducido if traducido else "No aplica",
        "reconocido": reconocido
    })

if __name__ == "__main__":
    app.run(debug=True)