"""
Тест сквозного конвейера OCR и предобработки.
"""

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ocr_ready"] is True


def test_analyze_image_with_text():
    client = TestClient(app)

    # Создаём синтетическое изображение с текстом
    img = np.ones((300, 800, 3), dtype=np.uint8) * 255
    cv2.putText(img, "INN 7701234567 OGRN 1027700132195", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, "AGREEMENT ON SERVICES N 105/2026", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    _, buf = cv2.imencode(".png", img)

    files = {"file": ("test_doc.png", buf.tobytes(), "image/png")}
    response = client.post("/analyze", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_pages"] == 1
    assert data["quality"] is not None
    assert data["quality"]["is_blurry"] is False
    assert len(data["ocr_results"]) >= 2

    recognized_texts = [block["text"] for block in data["ocr_results"]]
    full_text = " ".join(recognized_texts)
    print("\nРаспознанный текст:\n", full_text)
    assert "7701234567" in full_text or "INN" in full_text or "AGREEMENT" in full_text
