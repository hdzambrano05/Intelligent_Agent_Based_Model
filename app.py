from agents import orchestrate
from fastapi.responses import RedirectResponse
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import db
import logging


# ------------------- Logging -------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ------------------- Excepciones personalizadas -------------------
class DBError(Exception):
    """Error relacionado con la base de datos."""


class AnalysisError(Exception):
    """Error en el análisis de requisitos."""


# ------------------- Inicializar DB -------------------
try:
    db.init_db()
    logging.info("✅ Base de datos inicializada correctamente")
except Exception as e:  # pylint: disable=broad-exception-caught
    logging.error("❌ Error al inicializar la DB: %s", e, exc_info=True)
    raise DBError(f"No se pudo inicializar la base de datos: {e}") from e


# ------------------- FastAPI -------------------
app = FastAPI(title="REQ Quality Analyzer", version="0.4")


# ------------------- Modelos -------------------
class RequirementIn(BaseModel):
    id: str = Field(..., min_length=1, description="Identificador único del requisito")
    text: str = Field(..., min_length=5, description="Texto del requisito")
    context: str = Field(default="", description="Contexto adicional del requisito")


class BatchIn(BaseModel):
    requirements: List[RequirementIn]


# ------------------- Endpoints -------------------

@app.get("/", include_in_schema=False)
def root():
    """Redirige automáticamente a la documentación interactiva"""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    """Endpoint para comprobar si la API está viva"""
    return {"status": "healthy", "message": "API funcionando correctamente!"}


@app.post("/analyze")
def analyze(req: RequirementIn):
    """Analiza un único requisito y lo guarda en DB"""
    try:
        payload = {"id": req.id, "text": req.text, "context": req.context}
        result = orchestrate(payload)

        db.save_result(
            req.id,
            req.text,
            req.context,
            json.dumps(result, ensure_ascii=False)
        )

        return {
            "status": "success",
            "message": "Requisito analizado correctamente",
            "data": result
        }

    except DBError as e:
        logging.error("Error guardando en DB: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error en /analyze: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en análisis: {e}") from e


@app.post("/batch_analyze")
def batch_analyze(batch: BatchIn):
    """Analiza varios requisitos a la vez"""
    results = []
    for r in batch.requirements:
        try:
            payload = {"id": r.id, "text": r.text, "context": r.context}
            res = orchestrate(payload)

            db.save_result(r.id, r.text, r.context, json.dumps(res, ensure_ascii=False))
            results.append({"id": r.id, "status": "success", "data": res})

        except DBError as e:
            logging.error("DB error para requisito %s: %s", r.id, e, exc_info=True)
            results.append({"id": r.id, "status": "db_error", "error": str(e)})

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.warning("Error analizando requisito %s: %s", r.id, e, exc_info=True)
            results.append({"id": r.id, "status": "error", "error": str(e)})

    return {"status": "completed", "count": len(results), "results": results}


@app.get("/stored")
def get_stored(
    limit: Optional[int] = Query(None, description="Número máximo de registros a devolver"),
    filter_id: Optional[str] = Query(None, description="Filtrar por ID")
):
    """Devuelve todos los requisitos analizados guardados en DB"""
    try:
        rows = db.load_all()
        out = []

        for id_, text, ctx, result_json in rows:
            if filter_id and id_ != filter_id:
                continue

            try:
                parsed = json.loads(result_json)
            except json.JSONDecodeError:
                parsed = {"raw": result_json}

            out.append({
                "id": id_,
                "text": text,
                "context": ctx,
                "result": parsed
            })

        if limit:
            out = out[:limit]

        return {"status": "success", "count": len(out), "items": out}

    except DBError as e:
        logging.error("Error cargando datos desde DB: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error desconocido en /stored: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error cargando datos: {e}") from e
