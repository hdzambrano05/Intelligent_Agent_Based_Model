import json


from sklearn.metrics import precision_recall_fscore_support
from agents import orchestrate


DATA_FILE = "dataset.json"

def load_dataset():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def evaluate():
    data = load_dataset()
    
    # Diccionarios para almacenar valores
    gold_dict = {
        "ambiguous": [],
        "atomic": [],
        "complete": [],
        "valid": []
    }
    pred_dict = {
        "ambiguous": [],
        "atomic": [],
        "complete": [],
        "valid": []
    }

    porcentaje_promedio_reqs = []

    for item in data:
        res = orchestrate({
            "id": item["id"],
            "text": item["text"],
            "context": item.get("context", "")
        })

        analyst = res["agents"].get("Analyst", {}).get("analysis", {})
        product_owner = res["agents"].get("Product Owner", {}).get("analysis", {})
        promedio = res.get("promedio_cumplimiento", 0)
        porcentaje_promedio_reqs.append(promedio)

        # ---- Predicciones ----
        is_amb = analyst.get("claridad") == "ambiguo"
        is_atomic = analyst.get("atomicidad") == "atómico"
        is_complete = analyst.get("completitud") == "completo"
        is_valid = product_owner.get("validez", False)

        # ---- Valores reales ----
        gold = item["annotations"]
        gold_dict["ambiguous"].append(1 if gold["ambiguous"] else 0)
        pred_dict["ambiguous"].append(1 if is_amb else 0)

        gold_dict["atomic"].append(1 if gold["atomic"] else 0)
        pred_dict["atomic"].append(1 if is_atomic else 0)

        gold_dict["complete"].append(1 if gold["complete"] else 0)
        pred_dict["complete"].append(1 if is_complete else 0)

        gold_dict["valid"].append(1 if gold["valid"] else 0)
        pred_dict["valid"].append(1 if is_valid else 0)

    # ---- Métricas ----
    def prf(y_true, y_pred):
        p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
        return p, r, f

    print("📊 Evaluación de atributos (dataset de prueba):")
    macro_p, macro_r, macro_f = 0, 0, 0
    n_attrs = len(gold_dict)

    for attr in gold_dict:
        p, r, f = prf(gold_dict[attr], pred_dict[attr])
        macro_p += p
        macro_r += r
        macro_f += f
        print(f"{attr.capitalize():12}: Precision={p:.3f}, Recall={r:.3f}, F1={f:.3f}")

    print("-" * 50)
    print(f"Promedio Macro: Precision={macro_p/n_attrs:.3f}, Recall={macro_r/n_attrs:.3f}, F1={macro_f/n_attrs:.3f}")
    print(f"Promedio porcentaje cumplimiento por requisito: {sum(porcentaje_promedio_reqs)/len(porcentaje_promedio_reqs):.2f}%")

if __name__ == "__main__":
    evaluate()
