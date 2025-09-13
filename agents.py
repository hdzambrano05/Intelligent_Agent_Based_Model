import re
import json
import logging
import google.generativeai as genai

from typing import Dict, Any
from config import GEMINI_API_KEY

# ------------------- Configuración -------------------
genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def ask_gemini(prompt: str, model="gemini-2.5-flash") -> str:
    """Envía un prompt al modelo Gemini y devuelve la respuesta en texto."""
    try:
        model_instance = genai.GenerativeModel(model_name=model)
        response = model_instance.generate_content(prompt)
        return response.text if hasattr(response, "text") else str(response)

    except Exception as e:
        logging.exception("Error en ask_gemini")
        return json.dumps({"error": str(e)})


def safe_json_loads(text: str) -> dict:
    """Intenta extraer y cargar un JSON desde el texto devuelto por Gemini."""
    try:
        match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {"raw_response": text, "error": "No JSON encontrado"}

    except json.JSONDecodeError as e:
        return {"error": "JSON inválido", "detalle": str(e), "raw_response": text}


# ------------------- Clase de Agentes -------------------
class Agent:
    def __init__(self, role: str):
        self.role = role

    def analyze(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Genera un análisis del requisito según el rol (sin refinamiento)."""
        text = req["text"]
        context = req.get("context", "")
        palabras_vagas = ["rápido", "adecuado", "fácil", "eficiente"]

        if self.role == "Product Owner":
            prompt = f"""
Eres Product Owner. Evalúa necesidad, validez y prioridad del requisito.
Requisito: {text}
Contexto: {context}

Responde SOLO en JSON:
{{
  "validez": true/false,
  "priorizacion": "alta" | "media" | "baja",
  "necesidad": true/false,
  "porcentaje": 0-100
}}
"""
        elif self.role == "Analyst":
            ambiguo = any(p in text.lower() for p in palabras_vagas)
            prompt = f"""
Eres Analyst. Evalúa claridad, completitud, consistencia, atomicidad y conformidad.
Requisito: {text}
Contexto: {context}
Palabras vagas detectadas: {palabras_vagas}

Responde SOLO en JSON:
{{
  "claridad": "ambiguo" if {ambiguo} else "claro",
  "completitud": "completo" | "incompleto",
  "consistencia": "consistente" | "inconsistente",
  "atomicidad": "atómico" | "compuesto",
  "conformidad": "conforme" | "no_conforme",
  "porcentaje": 0-100
}}
"""
        elif self.role == "Scrum Master":
            prompt = f"""
Eres Scrum Master. Evalúa modificabilidad, trazabilidad y viabilidad.
Requisito: {text}
Contexto: {context}

Responde SOLO en JSON:
{{
  "modificabilidad": "alta" | "media" | "baja",
  "trazabilidad": "trazable" | "no_trazable",
  "viabilidad": "viable" | "no_viable",
  "porcentaje": 0-100
}}
"""
        elif self.role == "Tester":
            prompt = f"""
Eres Tester. Evalúa verificabilidad y genera casos de prueba.
Requisito: {text}
Contexto: {context}

Responde SOLO en JSON:
{{
  "verificabilidad": true/false,
  "casos_prueba": ["caso 1", "caso 2"],
  "porcentaje": 0-100
}}
"""
        else:
            return {"role": self.role, "analysis": "Rol no definido", "porcentaje": 0}

        # ---- Ejecución del análisis ----
        response_text = ask_gemini(prompt)
        analysis = safe_json_loads(response_text)
        return {"role": self.role, "analysis": analysis, "porcentaje": analysis.get("porcentaje", 0)}


# ------------------- Orquestador colaborativo -------------------
def orchestrate(req: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta los agentes, consolida el análisis y decide refinamiento según el promedio."""
    agents_list = [
        Agent("Product Owner").analyze(req),
        Agent("Analyst").analyze(req),
        Agent("Scrum Master").analyze(req),
        Agent("Tester").analyze(req),
    ]

    porcentajes = [a.get("porcentaje", 0) for a in agents_list]
    promedio = sum(porcentajes) / len(porcentajes) if porcentajes else 0

    # ---- Decisión según promedio ----
    if promedio < 35:
        # Refinamiento obligatorio
        refine_prompt = f"""
Eres un ingeniero de requisitos que coordina a un Product Owner, Analyst, Scrum Master y Tester.
El promedio de calidad del requisito es muy bajo (<35%). Reescribe el requisito de forma clara,
completa, atómica, consistente, verificable y viable.

Requisito original: {req['text']}
Contexto: {req.get('context','')}
Análisis de los agentes: {agents_list}

Responde SOLO en JSON:
{{
  "estado": "refinado_obligatorio",
  "requisito_refinado_final": "texto corregido y mejorado"
}}
"""
        refined = safe_json_loads(ask_gemini(refine_prompt))

    elif promedio < 60:
        # Solo sugerencias de mejora
        suggest_prompt = f"""
Eres un ingeniero de requisitos. El promedio de calidad es moderado (35%-59%).
No reescribas el requisito, solo da sugerencias de mejora claras y concretas.

Requisito original: {req['text']}
Contexto: {req.get('context','')}
Análisis de los agentes: {agents_list}

Responde SOLO en JSON:
{{
  "estado": "sugerencias",
  "sugerencias": ["sugerencia 1", "sugerencia 2", "sugerencia 3"]
}}
"""
        refined = safe_json_loads(ask_gemini(suggest_prompt))

    elif promedio >= 90:
        # Requisito aceptado sin cambios
        refined = {
            "estado": "aceptado",
            "requisito_refinado_final": req["text"],
        }
    else:
        # Caso intermedio (60-89%): se puede dejar opcional o sugerir refinamiento menor
        refined = {
            "estado": "opcional",
            "mensaje": "El requisito es aceptable pero puede mejorarse si se desea.",
        }

    consolidated = {
        "id": req.get("id", "-"),
        "text": req.get("text", ""),
        "context": req.get("context", ""),
        "promedio_cumplimiento": promedio,
        "agents": {a["role"]: a for a in agents_list},
        "refined_requirement": refined,
    }

    return consolidated


# ------------------- Prueba rápida -------------------
if __name__ == "__main__":
    r = {
        "id": "RF-01",
        "text": "El sistema debe garantizar una experiencia de usuario eficiente y un rendimiento óptimo, cumpliendo con los siguientes requisitos no funcionales:\n\n1.  **Rendimiento del Sistema:**\n    *   La carga de la página principal del listado de productos con hasta 1000 elementos no excederá los 2 segundos.\n    *   Las operaciones de búsqueda y filtrado de productos complejas se completarán en menos de 3 segundos.\n    *   La navegación entre los módulos principales (productos, categorías, informes) se realizará en menos de 1 segundo.\n\n2.  **Facilidad de Uso (Usabilidad):**\n    *   Un usuario sin experiencia previa en el sistema deberá ser capaz de crear un nuevo producto desde cero en un máximo de 5 clics y menos de 30 segundos.\n    *   La interfaz de edición masiva de atributos permitirá a los usuarios modificar 50 productos con una tasa de error inferior al 5%.\n    *   El sistema deberá obtener una puntuación mínima de 75 sobre 100 en la encuesta de System Usability Scale (SUS) aplicada a usuarios representativos tras completar tareas clave (creación, edición y búsqueda de productos).",
        "context": "Sistema gestión de productos",
    }

    analysis_result = orchestrate(r)

    with open("resultado.json", "w", encoding="utf-8") as f:
        json.dump(analysis_result, f, indent=2, ensure_ascii=False)

    print("✅ Análisis colaborativo completado. Revisa 'resultado.json'")
