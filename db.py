import sqlite3
from typing import List, Dict

DB_FILE = "requirements.db"


def init_db() -> None:
    """Inicializa la base de datos creando la tabla si no existe."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requirements (
                    id TEXT PRIMARY KEY,
                    text TEXT,
                    context TEXT,
                    result_json TEXT
                )
            """)
    except sqlite3.Error as e:
        print(f"❌ Error al inicializar la base de datos: {e}")


def save_result(req_id: str, text: str, context: str, result_json: str) -> None:
    """Guarda o actualiza un requisito en la base de datos."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO requirements (id, text, context, result_json)
                VALUES (?, ?, ?, ?)
            """, (req_id, text, context, result_json))
    except sqlite3.Error as e:
        print(f"❌ Error al guardar el requisito {req_id}: {e}")


def load_all() -> List[Dict[str, str]]:
    """Carga todos los requisitos almacenados como una lista de diccionarios."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT id, text, context, result_json FROM requirements")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"❌ Error al cargar requisitos: {e}")
        return []


if __name__ == "__main__":
    init_db()
    print(f"✅ Base de datos inicializada: {DB_FILE}")
