"""Genera casos de prueba con el código Python para verificar la versión web (TypeScript).

Uso:  python scripts/generate_web_fixtures.py
Escribe web/tests/fixtures/core_cases.json. El CI controla que esté al día (--check).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from revision_pipes.annotations import Box
from revision_pipes.inference import decode
from revision_pipes.review import classify, drop_nested, verdict
from revision_pipes.tiling import merge, to_plate, windows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "tests" / "fixtures" / "core_cases.json"
LABELS = ["Good Weld", "Bad Weld", "Defect"]


def box_json(b: Box) -> dict:
    return {"xMin": b.x_min, "yMin": b.y_min, "xMax": b.x_max, "yMax": b.y_max,
            "label": b.label, "score": b.score}


def random_boxes(rng, n, size=400):
    out = []
    for _ in range(n):
        x, y = rng.uniform(0, size * 0.8, 2)
        w, h = rng.uniform(5, size * 0.4, 2)
        out.append(Box(float(x), float(y), float(x + w), float(y + h),
                       LABELS[int(rng.integers(0, 3))], round(float(rng.uniform(0.05, 0.99)), 3)))
    return out


def build() -> dict:
    rng = np.random.default_rng(7)
    cases: dict = {"windows": [], "merge": [], "decode": [], "review": [], "to_plate": [], "resize": []}
    for w, h in [(640, 640), (3000, 600), (600, 3000), (900, 640), (1000, 600), (1601, 400), (5, 5)]:
        cases["windows"].append({"w": w, "h": h, "out": [list(x) for x in windows(w, h)]})
    for _ in range(25):
        boxes = random_boxes(rng, int(rng.integers(0, 12)))
        cases["merge"].append({"in": [box_json(b) for b in boxes],
                               "out": [box_json(b) for b in merge(boxes)]})
    for _ in range(15):
        queries = 30
        logits = rng.normal(-2, 2, (queries, 3)).astype(np.float32)
        pred = np.clip(rng.uniform(0, 1, (queries, 4)), 0.02, 0.98).astype(np.float32)
        size = (int(rng.integers(100, 900)), int(rng.integers(100, 900)))
        threshold = float(rng.choice([0.15, 0.3, 0.5]))
        out = decode(logits, pred, size, LABELS, threshold)
        cases["decode"].append({"logits": logits.flatten().tolist(), "predBoxes": pred.flatten().tolist(),
                                "size": list(size), "threshold": threshold,
                                "out": [box_json(b) for b in out]})
    for _ in range(25):
        boxes = random_boxes(rng, int(rng.integers(0, 10)))
        kept = drop_nested(boxes)
        findings = classify(kept, 0.5)
        cases["review"].append({
            "in": [box_json(b) for b in boxes],
            "nested": [box_json(b) for b in kept],
            "findings": [{"number": f.number, "level": f.level, "box": box_json(f.box)} for f in findings],
            "verdict": verdict(findings),
        })
    for _ in range(5):
        boxes = random_boxes(rng, 4)
        win = (int(rng.integers(0, 500)), int(rng.integers(0, 500)), 0, 0)
        cases["to_plate"].append({"in": [box_json(b) for b in boxes], "window": list(win),
                                  "out": [box_json(b) for b in to_plate(boxes, win)]})
    # Redimensionado: la web tiene que dar los mismos bytes que Pillow (BILINEAR), achicando y agrandando
    from PIL import Image

    for w, h, ow, oh in [(31, 17, 13, 9), (20, 20, 40, 40), (50, 12, 16, 16), (9, 33, 9, 11), (64, 48, 64, 48), (45, 45, 7, 31)]:
        arr = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
        arr[: h // 2] = (np.linspace(0, 255, w)[None, :, None]).astype(np.uint8)  # mitad con degradé
        out = np.asarray(Image.fromarray(arr).resize((ow, oh), Image.Resampling.BILINEAR))
        rgba = np.concatenate([arr, np.full((h, w, 1), 255, np.uint8)], axis=2)
        cases["resize"].append({"w": w, "h": h, "outW": ow, "outH": oh,
                                "rgba": rgba.flatten().tolist(), "out": out.flatten().tolist()})
    return cases


def main() -> int:
    content = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != content:
            print("Casos web desactualizados → corré python scripts/generate_web_fixtures.py")
            return 1
        print("Casos web al día.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"Casos generados: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
