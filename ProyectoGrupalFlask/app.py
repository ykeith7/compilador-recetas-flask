app = Flask(__name__)
# ... tus rutas ...

# AGREGA ESTA LÍNEA AL FINAL (Fuera del if __name__)
wsgi_app = app.wsgi_app

"""
Analizador Léxico / Sintáctico
Teoría de Compiladores

Uso:
    python analizador.py <archivo.txt>
    python analizador.py <archivo.txt> --json
    python analizador.py <archivo.txt> --json --out resultado.json
"""

import re
import json
import sys
import argparse
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# DEFINICIÓN DE TOKENS
# ============================================================

@dataclass
class TokenDef:
    name: str
    pattern: str
    desc: str

TOKEN_DEFS: list[TokenDef] = [
    TokenDef("FECHA",         r"\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b",                      "Fechas en formato DD/MM/AAAA"),
    TokenDef("MONTO",         r"S\/\.\s*[\d,]+\.?\d*|\$\s*[\d,]+\.?\d*|\b\d{1,3}(?:,\d{3})*\.\d{2}\b", "Montos monetarios (S/, $)"),
    TokenDef("RUC",           r"\b\d{11}\b",                                                       "RUC peruano (11 dígitos)"),
    TokenDef("DNI",           r"\b\d{8}\b",                                                        "DNI peruano (8 dígitos)"),
    TokenDef("TELEFONO",      r"\b(?:\+51\s?)?(?:9\d{8}|0\d{1,2}[\s\-]\d{6,8})\b",               "Números de teléfono"),
    TokenDef("NUMERO",        r"\b\d+(?:\.\d+)?\b",                                                "Números enteros o decimales"),
    TokenDef("PALABRA_CLAVE", r"\b(?:TOTAL|SUBTOTAL|IGV|FACTURA|BOLETA|RECIBO|PACIENTE|MEDICO|DOCTOR"
                              r"|DIAGNOSTICO|FECHA|HOSPITAL|CLINICA|FARMACIA|TRATAMIENTO|DOSIS|FIRMA"
                              r"|PRECIO|CANTIDAD|DESCRIPCION|CODIGO|NOMBRE|DIRECCION|EMISOR|RECEPTOR"
                              r"|IMPORTE|UNIDAD|LOTE|VENCIMIENTO|REGISTRO|N[°º]|Nro)\b",           "Palabras reservadas del dominio"),
    TokenDef("IDENTIFICADOR", r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}){0,3}\b", "Nombres propios e identificadores"),
    TokenDef("SEPARADOR",     r"[:;,|\/]",                                                         "Separadores y delimitadores"),
    TokenDef("OPERADOR",      r"[+\-=*%]",                                                         "Operadores"),
]


# ============================================================
# ESTRUCTURAS DE DATOS
# ============================================================

@dataclass
class Token:
    type: str
    lexema: str
    pos: int
    desc: str = ""

@dataclass
class TokenGroup:
    name: str
    desc: str
    pattern: str
    lexemas: list[str] = field(default_factory=list)

@dataclass
class AnalysisResult:
    text: str
    doc_type: str
    groups: dict[str, TokenGroup]
    stream: list[Token]
    fields: dict[str, str]


# ============================================================
# ANALIZADOR LÉXICO
# ============================================================

class LexicalAnalyzer:

    def __init__(self):
        # Compilar las expresiones regulares
        self._compiled = [
            (td, re.compile(td.pattern, re.IGNORECASE if td.name == "PALABRA_CLAVE" else 0))
            for td in TOKEN_DEFS
        ]

    def analyze(self, text: str) -> AnalysisResult:
        groups: dict[str, TokenGroup] = {}
        stream: list[Token] = []
        used_ranges: list[tuple[int, int]] = []

        for td, rx in self._compiled:
            for m in rx.finditer(text):
                start, end = m.start(), m.end()
                # Evitar solapamientos
                if any(start < r[1] and end > r[0] for r in used_ranges):
                    continue
                used_ranges.append((start, end))
                lexema = m.group().strip()
                if not lexema:
                    continue
                if td.name not in groups:
                    groups[td.name] = TokenGroup(name=td.name, desc=td.desc, pattern=td.pattern)
                if lexema not in groups[td.name].lexemas:
                    groups[td.name].lexemas.append(lexema)
                stream.append(Token(type=td.name, lexema=lexema, pos=start, desc=td.desc))

        stream.sort(key=lambda t: t.pos)

        doc_type = self._detect_doc_type(text)
        fields   = self._extract_fields(text)

        return AnalysisResult(
            text=text,
            doc_type=doc_type,
            groups=groups,
            stream=stream,
            fields=fields,
        )

    @staticmethod
    def _detect_doc_type(text: str) -> str:
        t = text.upper()
        if "FACTURA"    in t: return "FACTURA"
        if "BOLETA"     in t: return "BOLETA"
        if "RECETA"     in t or "PRESCRIPCION" in t or "MEDICAMENTO" in t: return "RECETA_MEDICA"
        if "HOSPITAL"   in t or "CLINICA" in t or "PACIENTE" in t:         return "DOCUMENTO_MEDICO"
        if "CONTRATO"   in t: return "CONTRATO"
        if "RECIBO"     in t: return "RECIBO"
        return "DOCUMENTO_GENERICO"

    @staticmethod
    def _extract_fields(text: str) -> dict[str, str]:
        patterns = {
            "ruc":         r"RUC[°:.\s]*(\d{11})",
            "dni":         r"DNI[°:.\s]*(\d{8})",
            "fecha":       r"fecha[°:.\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            "total":       r"TOTAL[°:.\s]*S?\/?\.?\s*([\d,]+\.?\d*)",
            "paciente":    r"PACIENTE[°:.\s]*([A-Za-záéíóúñÁÉÍÓÚÑ ,]+?)[\n\r;]",
            "medico":      r"(?:MEDICO|DOCTOR|DR\.?)[°:.\s]*([A-Za-záéíóúñÁÉÍÓÚÑ ,]+?)[\n\r;]",
            "diagnostico": r"DIAGNOSTICO[°:.\s]*([^\n\r;]+)",
            "codigo":      r"(?:C[OÓ]DIGO|COD)[°:.\s]*([A-Z0-9\-]+)",
        }
        fields: dict[str, str] = {}
        for key, pat in patterns.items():
            m = re.search(pat, text, re.IGNORECASE)
            if m and m.group(1):
                fields[key] = m.group(1).strip()[:80]
        return fields


# ============================================================
# GRAMÁTICA LIBRE DE CONTEXTO
# ============================================================

def get_grammar(doc_type: str) -> list[tuple[str, str]]:
    return [
        ("Documento",  doc_type),
        (doc_type,     "Encabezado Cuerpo [Pie]"),
        ("Encabezado", "PALABRA_CLAVE SEPARADOR Valor"),
        ("Valor",      "NUMERO | FECHA | MONTO | IDENTIFICADOR"),
        ("Cuerpo",     "Linea | Cuerpo Linea"),
        ("Linea",      "Campo SEPARADOR Valor | Campo Valor"),
        ("Campo",      "PALABRA_CLAVE | IDENTIFICADOR"),
        ("Items",      "Item | Items Item"),
        ("Item",       "IDENTIFICADOR NUMERO MONTO"),
        ("Pie",        '"TOTAL" SEPARADOR MONTO'),
    ]


# ============================================================
# AUTÓMATAS (descripción estructural)
# ============================================================

def build_afnd(token_names: list[str]) -> dict:
    states = ["q0"] + [f"q{i+1}" for i in range(len(token_names))]
    return {
        "tipo": "AFND",
        "nota": "Cada estado qi acepta lexemas del token correspondiente vía ε-clausura",
        "estados": states,
        "estado_inicial": "q0",
        "estados_aceptacion": states[1:],
        "alfabeto": token_names,
        "transiciones_epsilon": [
            {"desde": "q0", "con": "ε", "hacia": f"q{i+1}"}
            for i in range(len(token_names))
        ],
    }

def build_afd(token_names: list[str]) -> dict:
    states = ["q0"] + [f"q{i+1}" for i in range(len(token_names))]
    return {
        "tipo": "AFD",
        "estados": states,
        "estado_inicial": "q0",
        "estados_aceptacion": states[1:],
        "alfabeto": token_names,
        "transiciones": [
            {"desde": "q0", "con": t, "hacia": f"q{i+1}"}
            for i, t in enumerate(token_names)
        ],
    }

def build_transition_table(token_names: list[str]) -> list[dict]:
    states = ["q0"] + [f"q{i+1}" for i in range(len(token_names))]
    table = []
    for si, state in enumerate(states):
        row: dict = {"estado": state, "inicial": si == 0, "acepta": si > 0}
        for ai, tok in enumerate(token_names):
            if si == 0:
                row[tok] = f"q{ai+1}"
            elif si == ai + 1:
                row[tok] = state        # self-loop
            else:
                row[tok] = "—"
        table.append(row)
    return table


# ============================================================
# SERIALIZACIÓN JSON
# ============================================================

def to_json(result: AnalysisResult) -> dict:
    from datetime import datetime

    token_names = list(result.groups.keys())

    tokens_json = {
        name: {
            "descripcion": g.desc,
            "expresion_regular": g.pattern,
            "lexemas": g.lexemas,
            "total_instancias": len(g.lexemas),
        }
        for name, g in result.groups.items()
    }

    grammar_dict = {lhs: [rhs] for lhs, rhs in get_grammar(result.doc_type)}

    return {
        "documento": {
            "tipo_detectado": result.doc_type,
            "campos": result.fields,
            "estadisticas": {
                "total_tokens_reconocidos": len(result.stream),
                "tipos_de_token": len(result.groups),
                "caracteres_totales": len(result.text),
            },
        },
        "analisis_lexico": {
            "tokens": tokens_json,
            "secuencia_primeros_30": [
                {"token": t.type, "lexema": t.lexema, "posicion": t.pos}
                for t in result.stream[:30]
            ],
        },
        "analisis_sintactico": {
            "gramatica_libre_de_contexto": grammar_dict,
            "automata_no_determinista": build_afnd(token_names),
            "automata_determinista": build_afd(token_names),
            "tabla_de_transiciones": build_transition_table(token_names),
        },
        "traduccion": {
            "formato": "JSON",
            "fecha_generacion": datetime.now().isoformat(),
            "herramienta": "Analizador Léxico/Sintáctico v1.0 (Python)",
        },
    }


# ============================================================
# REPORTE EN TEXTO PLANO
# ============================================================

def print_report(result: AnalysisResult) -> None:
    SEP  = "=" * 60
    SEP2 = "-" * 60

    print(SEP)
    print("  ANÁLISIS LÉXICO / SINTÁCTICO")
    print(SEP)
    print(f"  Tipo de documento : {result.doc_type}")
    print(f"  Tokens encontrados: {len(result.stream)}")
    print(f"  Tipos de token    : {len(result.groups)}")
    print(f"  Caracteres        : {len(result.text)}")

    if result.fields:
        print(SEP2)
        print("CAMPOS DETECTADOS")
        print(SEP2)
        for k, v in result.fields.items():
            print(f"  {k:<14}: {v}")

    print(SEP2)
    print("TOKENS Y LEXEMAS")
    print(SEP2)
    for name, g in result.groups.items():
        lexemas_str = ", ".join(g.lexemas[:6])
        suffix = f"  (+{len(g.lexemas)-6} más)" if len(g.lexemas) > 6 else ""
        print(f"  [{name:<16}] {g.desc}")
        print(f"   RE : {g.pattern[:70]}")
        print(f"   Lex: {lexemas_str}{suffix}")
        print()

    print(SEP2)
    print("SECUENCIA DE TOKENS (primeros 40)")
    print(SEP2)
    for i, t in enumerate(result.stream[:40]):
        print(f"  {i+1:>3}. [{t.type:<16}] {t.lexema!r:<30}  @pos={t.pos}")
    if len(result.stream) > 40:
        print(f"  ... y {len(result.stream)-40} tokens más.")

    print(SEP2)
    print("GRAMÁTICA LIBRE DE CONTEXTO")
    print(SEP2)
    for lhs, rhs in get_grammar(result.doc_type):
        print(f"  {lhs:<16} → {rhs}")

    print(SEP2)
    print("AUTÓMATA FINITO (resumen)")
    print(SEP2)
    token_names = list(result.groups.keys())
    print(f"  Estados : q0 (inicial), {', '.join(f'q{i+1}' for i in range(len(token_names)))} (aceptación)")
    print("  AFND    : q0 --ε--> qi  (para cada tipo de token i)")
    print("  AFD     :")
    for i, t in enumerate(token_names):
        print(f"    q0 --{t[:14]}--> q{i+1}  [acepta]")
    print(SEP)


# ============================================================
# MAIN
# ============================================================

# PEGA ESTO EN SU LUGAR:
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analizar', methods=['POST'])
def analizar():
    if 'archivo' not in request.files:
        return jsonify({"error": "No se subió ningún archivo"}), 400
    
    file = request.files['archivo']
    if file.filename == '':
        return jsonify({"error": "Archivo no seleccionado"}), 400

    try:
        text = file.read().decode('utf-8')
        analyzer = LexicalAnalyzer()
        result = analyzer.analyze(text)
        return jsonify(to_json(result))
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True, port=5000)
