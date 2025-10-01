# Intelligent Agent-Based Model for Software Requirements Quality Analysis

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![GitHub Repo Size](https://img.shields.io/github/repo-size/TU_USUARIO/TU_REPOSITORIO)
![License](https://img.shields.io/github/license/TU_USUARIO/TU_REPOSITORIO)

## 📖 Descripción

Este repositorio contiene un **modelo basado en agentes inteligentes con IA generativa** diseñado para **analizar y mejorar la calidad de los requisitos funcionales de software**.  
El sistema ayuda a identificar ambigüedades, inconsistencias y posibles mejoras en los requisitos para asegurar un desarrollo más robusto y eficiente.

---

## 🚀 Características principales

- Análisis de **claridad, completitud y consistencia** de requisitos funcionales.
- Modelo **basado en agentes inteligentes**, capaz de evaluar y sugerir mejoras automáticamente.
- Integración con **IA generativa** para recomendaciones y explicaciones.
- Fácil de extender y adaptar a proyectos de software reales.

---

## 📂 Estructura del repositorio

```
reqcheck/
├── agents.py           # Agentes inteligentes y lógica principal
├── evaluate.py         # Evalúa el modelo usando dataset.json
├── app.py              # Archivo principal de la aplicación (FastAPI)
├── dataset.json        # Datos de prueba / requisitos
├── back.txt            # Librerías usadas en Python
├── .gitignore          # Archivos ignorados por Git
└── README.md           # Documentación
```

> **Nota:** Archivos sensibles como `config.py` o `.env` **no se suben al repositorio**.

---

## 💻 Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git
cd TU_REPOSITORIO
```

2. Crear un entorno virtual (recomendado):
```bash
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

> **Nota:** agrega tus claves de API (por ejemplo Gemini) en un archivo `.env` local, **no subido al repo**.

---

## ⚙️ Uso básico

### 1. Probar el modelo directamente
```bash
python agents.py
```
Esto imprimirá en consola la evaluación de un requisito de ejemplo.

---

### 2. Iniciar la aplicación (`app.py`) con FastAPI
```bash
uvicorn app:app --reload
```
- `app:app` → el primer `app` es el nombre del archivo (`app.py`), el segundo `app` es la instancia de FastAPI.  
- `--reload` → permite que los cambios en el código se actualicen automáticamente.  

#### Probar con Postman:
- URL: `http://127.0.0.1:8000/evaluar`  
- Método: `POST`  
- Body (JSON):
```json
{
  "requisito": "El sistema debe permitir registrar usuarios con nombre, correo y contraseña"
}
```

Recibirás en la respuesta el análisis generado por el modelo.

---

## 🛡️ Buenas prácticas

- Mantener las claves de API fuera del repositorio (`config.py` y `.env`).
- Comprobar los resultados con casos de prueba reales.
- Revisar los logs para entender cómo los agentes toman decisiones.

---

## 📖 Referencias y documentación

- [Python](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/) *(si aplica integración web)*
- [IA Generativa](https://openai.com/research)

---
