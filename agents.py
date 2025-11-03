import re
import json
import logging
import asyncio
import google.generativeai as genai
from typing import Dict, Any
from config import GEMINI_API_KEY

# ------------------- Configuración -------------------
genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ------------------- Funciones utilitarias -------------------
async def ask_gemini(prompt: str, model="gemini-2.5-flash") -> str:
    """Envía un prompt al modelo Gemini y devuelve la respuesta en texto (async)."""
    try:
        model_instance = genai.GenerativeModel(model_name=model)
        loop = asyncio.get_event_loop()
        # Ejecutar en un hilo separado para no bloquear asyncio
        response = await loop.run_in_executor(None, model_instance.generate_content, prompt)
        return response.text if hasattr(response, "text") else str(response)
    except Exception as e:  # pylint: disable=broad-exception-caught
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

    async def analyze(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Genera un análisis del requisito según el rol (ahora async)."""
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
Eres Tester. Evalúa verificabilidad y genera como máximo 3 casos de prueba simples.
Requisito: {text}
Contexto: {context}

Responde SOLO en JSON:
{{
  "verificabilidad": true/false,
  "casos_prueba": ["caso 1", "caso 2", "caso 3"],
  "porcentaje": 0-100
}}
"""
        else:
            return {"role": self.role, "analysis": "Rol no definido", "porcentaje": 0}

        # ---- Ejecución del análisis (async) ----
        response_text = await ask_gemini(prompt)
        analysis = safe_json_loads(response_text)
        return {"role": self.role, "analysis": analysis, "porcentaje": analysis.get("porcentaje", 0)}


# ------------------- Orquestador colaborativo -------------------
async def orchestrate(req: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta los agentes en paralelo, consolida el análisis y decide refinamiento según el promedio."""

    agents = [Agent("Product Owner"), Agent("Analyst"), Agent("Scrum Master"), Agent("Tester")]

    # Ejecutar en paralelo con asyncio.gather
    agents_list = await asyncio.gather(*[a.analyze(req) for a in agents])

    porcentajes = [a.get("porcentaje", 0) for a in agents_list]
    promedio = sum(porcentajes) / len(porcentajes) if porcentajes else 0

    # ---- Decisión según promedio ----
    if promedio < 35:
        refine_prompt = f"""
Eres un ingeniero de requisitos. El promedio es muy bajo (<35%).
Reescribe el requisito de forma breve, clara y precisa, sin cambiar el tema original.

Requisito original: {req['text']}
Contexto: {req.get('context','')}

Responde SOLO en JSON:
{{
  "estado": "refinado_obligatorio",
  "requisito_refinado_final": "versión corta, clara y precisa"
}}
"""
        refined = safe_json_loads(await ask_gemini(refine_prompt))

    elif promedio <= 70:  # hasta 70 da sugerencias
        suggest_prompt = f"""
Eres un ingeniero de requisitos. El promedio es moderado (35%-70%).
Da máximo 3 sugerencias claras y concretas de mejora.

Requisito original: {req['text']}
Contexto: {req.get('context','')}

Responde SOLO en JSON:
{{
  "estado": "sugerencias",
  "sugerencias": ["sugerencia 1", "sugerencia 2", "sugerencia 3"]
}}
"""
        refined = safe_json_loads(await ask_gemini(suggest_prompt))

    elif promedio >= 90:
        refined = {
            "estado": "aceptado",
            "requisito_refinado_final": req["text"],
        }
    else:  # 71–89 → opcional
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
        "text": "El sistema debe ser rápido y eficiente en la búsqueda de productoss.",
        "context": "Sistema gestión de productos",
    }

    result = asyncio.run(orchestrate(r))
    print(json.dumps(result, indent=2, ensure_ascii=False))
