import re
import json
import logging
import asyncio
import google.generativeai as genai
from typing import Dict, Any
from config import GEMINI_API_KEY

# ==========================
# CONFIGURACIÓN
# ==========================
genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ==========================
# FUNCIONES UTILITARIAS
# ==========================
async def ask_gemini(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """Envía un prompt a Gemini y devuelve texto limpio."""
    try:
        model_instance = genai.GenerativeModel(model_name=model)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, model_instance.generate_content, prompt)
        text = getattr(response, "text", None)
        return text.strip() if text else str(response)
    except Exception as e:
        logging.exception("Error en ask_gemini")
        return json.dumps({"error": str(e)})


def safe_json_loads(text: str) -> dict:
    """Extrae JSON válido del texto de respuesta, tolerando errores de formato."""
    try:
        match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {"error": "No JSON encontrado", "raw_response": text}
    except json.JSONDecodeError as e:
        return {"error": "JSON inválido", "detalle": str(e), "raw_response": text}


# ==========================
# AJUSTE DE PUNTAJES
# ==========================
def ajustar_puntaje(analisis_agente: Dict[str, Any]) -> float:
    """
    Recalibra el puntaje según problemas detectados.
    Penaliza ambigüedad, falta de claridad, incompletitud o falta de verificabilidad.
    """
    penalizacion = 0
    total_attrs = 0

    if not isinstance(analisis_agente, dict):
        return 0

    atributos = analisis_agente.get("atributos", {})
    for nombre, datos in atributos.items():
        if not isinstance(datos, dict):
            continue
        total_attrs += 1

        valor = str(datos.get("valor", "")).lower()
        sugerencia = str(datos.get("sugerencia", "")).lower()

        # Penalizaciones comunes
        if any(p in valor for p in ["ambiguo", "incompleto", "baja", "no"]):
            penalizacion += 20
        if any(p in sugerencia for p in ["reemplazar", "no medible", "ajustar", "reformule"]):
            penalizacion += 15
        if any(p in sugerencia for p in ["rápido", "eficiente", "adecuado"]):
            penalizacion += 20

    if total_attrs == 0:
        return 0

    puntaje_base = analisis_agente.get("porcentaje", 0)
    puntaje_ajustado = max(0, puntaje_base - penalizacion / total_attrs)
    return round(puntaje_ajustado, 2)


# ==========================
# CLASE DE AGENTE
# ==========================
class Agent:
    def __init__(self, role: str):
        self.role = role

    async def analyze(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza un requisito según el rol del agente."""
        text = req["text"]
        descripcion_proyecto = req["descripcion_proyecto"]  # Ahora es descripción del proyecto

        # Diccionario de prompts por rol
        prompts = {
            "Product Owner": f"""
Eres un **Product Owner experto en ingeniería de requisitos**.
Analiza el siguiente requisito en el contexto del proyecto. Responde SOLO en formato JSON estructurado.

DESCRIPCIÓN DEL PROYECTO: "{descripcion_proyecto}"
REQUISITO A ANALIZAR: "{text}"

Evalúa los siguientes atributos considerando la descripción del proyecto:
- necesidad (¿es necesario para este proyecto?)
- validez (¿está alineado con los objetivos del proyecto?)
- priorización (¿qué tan prioritario es para este proyecto específico?)

Ejemplo JSON:
{{
  "atributos": {{
    "necesidad": {{"valor": true, "sugerencia": "Es necesario para cumplir con el registro de usuarios requerido en el proyecto."}},
    "validez": {{"valor": true, "sugerencia": "Alineado con el objetivo de tener usuarios validados antes del acceso."}},
    "priorizacion": {{"valor": "alta", "sugerencia": "Crítico para la seguridad y funcionamiento básico del sistema."}}
  }},
  "porcentaje": 85
}}
""",

            "Analyst": f"""
Actúa como **Analista de Requisitos Técnico y Lingüístico**.
Evalúa la redacción técnica del requisito en el contexto del proyecto. Devuelve SOLO JSON.

DESCRIPCIÓN DEL PROYECTO: "{descripcion_proyecto}"
REQUISITO A ANALIZAR: "{text}"

Evalúa considerando el contexto del proyecto:
- claridad (¿está claro en el contexto de este proyecto?)
- completitud (¿cubre lo necesario para este proyecto?)
- consistencia (¿es consistente con la descripción del proyecto?)
- atomicidad
- conformidad con estándares

Ejemplo JSON:
{{
  "atributos": {{
    "claridad": {{"valor": "ambigua", "sugerencia": "En el contexto de este proyecto, debe especificar qué información se considera 'completa'."}},
    "completitud": {{"valor": "parcial", "sugerencia": "Faltan detalles sobre el proceso de validación mencionado en la descripción del proyecto."}},
    "consistencia": {{"valor": "alta", "sugerencia": "Consistente con el objetivo de registro y validación del proyecto."}},
    "atomicidad": {{"valor": "correcta", "sugerencia": "Define una sola acción principal."}},
    "conformidad": {{"valor": "media", "sugerencia": "Podría mejorarse para seguir mejor el formato SMART considerando el proyecto."}}
  }},
  "porcentaje": 70
}}
""",

            "Scrum Master": f"""
Eres un **Scrum Master experto en agilidad y mantenibilidad**.
Evalúa si el requisito es ágil y adaptable para este proyecto específico. Devuelve SOLO JSON.

DESCRIPCIÓN DEL PROYECTO: "{descripcion_proyecto}"
REQUISITO A ANALIZAR: "{text}"

Evalúa en el contexto de este proyecto:
- modificabilidad (¿fácil de modificar según evolucione este proyecto?)
- trazabilidad (¿puede rastrearse hasta los objetivos de este proyecto?)
- viabilidad (¿es viable técnicamente para este proyecto?)

Ejemplo JSON:
{{
  "atributos": {{
    "modificabilidad": {{"valor": "media", "sugerencia": "Para este proyecto, debería definirse métricas claras de validación."}},
    "trazabilidad": {{"valor": "alta", "sugerencia": "Se traza directamente al objetivo de registro del proyecto."}},
    "viabilidad": {{"valor": "alta", "sugerencia": "Viable considerando los requisitos de seguridad del proyecto."}}
  }},
  "porcentaje": 80
}}
""",

            "Tester": f"""
Eres un **Tester QA experto en pruebas de software**.
Evalúa si el requisito puede verificarse mediante pruebas en el contexto de este proyecto.
Devuelve SOLO JSON.

DESCRIPCIÓN DEL PROYECTO: "{descripcion_proyecto}"
REQUISITO A ANALIZAR: "{text}"

Evalúa considerando los requisitos del proyecto:
- verificabilidad (¿puede probarse según lo que requiere el proyecto?)
- ejemplos de casos de prueba relevantes para este proyecto

Ejemplo JSON:
{{
  "atributos": {{
    "verificabilidad": {{"valor": false, "sugerencia": "Para este proyecto, debe especificar criterios medibles de 'información completa' y 'validada'."}},
    "casos_prueba": {{"valor": ["Verificar que usuario con email inválido no pueda registrarse", "Validar que usuario sin todos los campos obligatorios no sea registrado"]}}
  }},
  "porcentaje": 60
}}
"""
        }

        prompt = prompts.get(self.role)
        if not prompt:
            return {"role": self.role, "analysis": {"error": "Rol no definido"}, "porcentaje": 0}

        # Llamada al modelo
        response_text = await ask_gemini(prompt)
        analysis = safe_json_loads(response_text)

        return {
            "role": self.role,
            "analysis": analysis,
            "porcentaje": analysis.get("porcentaje", 0)
        }


# ==========================
# ORQUESTADOR
# ==========================
async def orchestrate(req: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta los agentes, combina resultados y genera el requisito refinado."""
    
    # Validar que descripcion_proyecto esté presente
    if "descripcion_proyecto" not in req or not req["descripcion_proyecto"]:
        return {
            "error": "El campo 'descripcion_proyecto' es obligatorio",
            "id": req.get("id", "-"),
            "text": req["text"]
        }
    
    agents = [Agent("Product Owner"), Agent("Analyst"), Agent("Scrum Master"), Agent("Tester")]
    results = await asyncio.gather(*[a.analyze(req) for a in agents])

    # Recalibrar puntajes individuales
    porcentajes = [ajustar_puntaje(a["analysis"]) for a in results]
    promedio = round(sum(porcentajes) / len(porcentajes), 2) if porcentajes else 0

    # Combinar sugerencias (con requisito incluido)
    sugerencias = []
    for a, puntaje in zip(results, porcentajes):
        attrs = a["analysis"].get("atributos", {})
        for attr, info in attrs.items():
            if isinstance(info, dict) and info.get("sugerencia"):
                sugerencias.append(
                    f"- ({a['role']} - {attr} - {puntaje}%): "
                    f"Sugerencia: {info['sugerencia']}"
                )

    sugerencias_texto = "\n".join(sugerencias) if sugerencias else "Ninguna sugerencia."

    # Refinamiento final del requisito
    refine_prompt = f"""
Eres un **ingeniero senior en requisitos funcionales (IEEE 830 / SMART)**.
Refina el siguiente requisito aplicando las sugerencias combinadas y considerando el contexto del proyecto.

DESCRIPCIÓN DEL PROYECTO: "{req['descripcion_proyecto']}"
REQUISITO ORIGINAL: "{req['text']}"
SUGERENCIAS COMBINADAS:
{sugerencias_texto}

El requisito refinado debe ser:
- Específico para este proyecto
- Medible
- Alcanzable
- Relevante para los objetivos del proyecto
- Temporal (si aplica)

Responde SOLO en formato JSON.

Ejemplo JSON:
{{
  "estado": "refinado_final",
  "requisito_refinado_final": "El sistema debe validar que todos los nuevos usuarios proporcionen nombre, email válido y contraseña segura antes de permitir el acceso a las funcionalidades principales.",
  "justificacion_refinamiento": "Refinado para incluir criterios específicos de validación alineados con la descripción del proyecto."
}}
"""

    refined = safe_json_loads(await ask_gemini(refine_prompt))

    # Crear nuevo requisito funcional basado en la descripción del proyecto
    create_prompt = f"""
Eres un **ingeniero senior en requisitos funcionales**.
Basándote SOLAMENTE en la siguiente descripción del proyecto, crea un requisito funcional completo y bien estructurado que sea esencial para este proyecto.

DESCRIPCIÓN DEL PROYECTO: "{req['descripcion_proyecto']}"

El requisito debe:
- Ser específico para ESTE proyecto
- Ser medible y verificable
- Ser alcanzable técnicamente
- Ser relevante para los objetivos del proyecto
- Seguir estándares IEEE 830

Responde SOLO en formato JSON.

Ejemplo JSON:
{{
  "estado": "nuevo_requisito",
  "requisito_funcional_nuevo": "El sistema debe validar automáticamente el formato de email y completitud de todos los campos obligatorios (nombre, email, contraseña) durante el registro de nuevos usuarios.",
  "justificacion": "Este requisito es esencial para garantizar que solo usuarios con información válida y completa puedan acceder al sistema, cumpliendo con los objetivos de seguridad e integridad de datos del proyecto."
}}
"""

    nuevo_requisito = safe_json_loads(await ask_gemini(create_prompt))

    return {
        "id": req.get("id", "-"),
        "text": req["text"],
        "descripcion_proyecto": req["descripcion_proyecto"],
        "promedio_cumplimiento": promedio,
        "analisis_detallado": {a["role"]: a["analysis"] for a in results},
        "sugerencias_combinadas": sugerencias,
        "opciones_requisito": {
            "requisito_refinado": refined.get("requisito_refinado_final", "No generado"),
            "justificacion_refinado": refined.get("justificacion_refinamiento", "Sin justificación"),
            "requisito_nuevo": nuevo_requisito.get("requisito_funcional_nuevo", "No generado"),
            "justificacion_nuevo": nuevo_requisito.get("justificacion", "Sin justificación")
        },
        "recomendacion": "Compare ambas opciones y elija la que mejor se adapte a las necesidades específicas del proyecto."
    }


# ==========================
# PRUEBA
# ==========================
if __name__ == "__main__":
    r = {
        "id": "RF-01",
        "text": "el sistema debe buscar un libro muy rapido y no debe mostrar errores de conexión",
        "descripcion_proyecto": "La Universidad Tecnológica necesita un sistema integral de gestión bibliotecaria que permita administrar el catálogo de libros, préstamos a estudiantes y personal académico, reservas de materiales y control de devoluciones. El sistema debe garantizar la disponibilidad de materiales educativos, prevenir pérdidas de libros y ofrecer estadísticas de uso para la toma de decisiones. Debe integrarse con el sistema de matrícula existente y permitir acceso diferenciado para estudiantes, bibliotecarios y administradores. El objetivo principal es digitalizar completamente los procesos manuales actuales que son lentos y propensos a errores, mejorando la experiencia del usuario y optimizando los recursos bibliotecarios.",
    }

    result = asyncio.run(orchestrate(r))
    print(json.dumps(result, indent=2, ensure_ascii=False))