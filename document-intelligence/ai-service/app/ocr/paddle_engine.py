"""
Реализация движка оптического распознавания на базе нейросети PaddleOCR.

Что делает этот модуль:
1. Инициализирует современные предобученные модели PaddleOCR:
   - Модель детекции текстовых областей (DBNet / PP-OCRv4/v5 Detection);
   - Классификатор ориентации строк (PP-LCNet Orientation Classifier);
   - Нейросеть распознавания символов (SVTR / CRNN Recognition) с поддержкой русского и английского языков.
2. Прогоняет изображение документа через нейросетевой пайплайн.
3. Парсит сырой вывод PaddleOCR (полигоны из 4 точек и кортежи вероятностей)
   в унифицированный формат OcrBlock с прямоугольными Bounding Box [x1, y1, x2, y2].

Почему PaddleOCR:
- Поддерживает русский язык из коробки (lang='ru' включает кириллицу, латиницу и цифры).
- Обеспечивает точность распознавания более 96-98% на сканах документов.
- Работает быстро как на CPU, так и на GPU.
- Поддерживает устойчивую детекцию строк под любыми углами.
"""

import logging
from typing import List, Optional
import cv2
import numpy as np

from app.ocr.base import BaseOcrEngine, OcrBlock

logger = logging.getLogger(__name__)


class PaddleOcrEngine(BaseOcrEngine):
    """Движок OCR на базе PaddleOCR."""

    def __init__(self, lang: str = "ru", use_angle_cls: bool = True):
        """
        :param lang: Язык распознавания (по умолчанию 'ru' — русский + английский + цифры).
        :param use_angle_cls: Использовать ли классификатор ориентации перевёрнутых строк (0°/180°).
        """
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self._ocr = None
        self._initialize()

    def _initialize(self):
        """Ленивая или явная инициализация PaddleOCR с обработкой ошибок."""
        try:
            # На Windows CPU PaddlePaddle 3.4.0 имеет баг в oneDNN (mkldnn) PIR executor.
            # Отключение mkldnn в predictor config решает проблему на 100%.
            try:
                import paddle.inference
                if not hasattr(paddle.inference, "_docintel_patched"):
                    orig_create_predictor = paddle.inference.create_predictor
                    def patched_create_predictor(config):
                        if hasattr(config, "disable_mkldnn"):
                            config.disable_mkldnn()
                        return orig_create_predictor(config)
                    paddle.inference.create_predictor = patched_create_predictor
                    paddle.inference._docintel_patched = True
            except Exception as patch_err:
                logger.debug(f"oneDNN patch info: {patch_err}")

            from paddleocr import PaddleOCR
            logger.info(f"Инициализация моделей PaddleOCR (язык: '{self.lang}')...")
            # В PaddleOCR 3.x отключаем UVDoc unwarping и orientation classify,
            # чтобы координаты детекции (bbox) соответствовали оригинальному изображению
            self._ocr = PaddleOCR(
                lang=self.lang,
                use_doc_unwarping=False,
                use_doc_orientation_classify=False,
                use_textline_orientation=True
            )
            logger.info("PaddleOCR успешно инициализирован и готов к работе!")
        except Exception as e:
            logger.error(f"Не удалось инициализировать PaddleOCR: {str(e)}", exc_info=True)
            self._ocr = None

    @property
    def is_ready(self) -> bool:
        """Готов ли движок к распознаванию."""
        return self._ocr is not None

    def recognize(self, image: np.ndarray, page_num: int = 1) -> List[OcrBlock]:
        """
        Распознаёт текст на изображении с помощью нейросетей PaddleOCR.

        :param image: Изображение в формате OpenCV (BGR).
        :param page_num: Номер страницы.
        :return: Список структурированных блоков OcrBlock.
        """
        if not self.is_ready:
            logger.warning("PaddleOCR не инициализирован, попытка повторной инициализации...")
            self._initialize()
            if not self.is_ready:
                raise RuntimeError("Движок PaddleOCR недоступен (не удалось загрузить модели нейросети)")

        if image is None or image.size == 0:
            return []

        orig_h, orig_w = image.shape[:2]
        max_dim = 1920
        scale = 1.0
        ocr_input = image

        if max(orig_h, orig_w) > max_dim:
            scale = max_dim / max(orig_h, orig_w)
            target_w = int(round(orig_w * scale))
            target_h = int(round(orig_h * scale))
            ocr_input = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)
            logger.info(f"Изображение страницы {page_num} смасштабировано для OCR: {orig_w}x{orig_h} -> {target_w}x{target_h} (scale={scale:.3f})")

        def _unscale_bbox(b: List[int]) -> List[int]:
            if scale == 1.0 or not b:
                return b
            return [
                max(0, min(orig_w, int(round(b[0] / scale)))),
                max(0, min(orig_h, int(round(b[1] / scale)))),
                max(0, min(orig_w, int(round(b[2] / scale)))),
                max(0, min(orig_h, int(round(b[3] / scale))))
            ]

        # PaddleOCR принимает изображение в формате BGR/RGB numpy array
        try:
            # В PaddleOCR 3.x метод predict() возвращает результаты детекции и распознавания
            if hasattr(self._ocr, "predict"):
                raw_result = list(self._ocr.predict(ocr_input))
            else:
                raw_result = self._ocr.ocr(ocr_input)
        except Exception as e:
            logger.error(f"Ошибка во время распознавания страницы {page_num}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Ошибка распознавания PaddleOCR: {str(e)}") from e

        blocks: List[OcrBlock] = []

        # PaddleOCR возвращает список списков: [ [ [ [x1,y1],... ], ("text", score) ], ... ] ]
        if not raw_result:
            return blocks

        for page_data in raw_result:
            if page_data is None:
                continue

            # В зависимости от версии PaddleOCR, page_data может быть словарём или списком линий
            if isinstance(page_data, dict):
                # PaddleX / PaddleOCR 3.x словарь
                dt_polys = page_data.get("dt_polys", [])
                rec_texts = page_data.get("rec_texts", [])
                rec_scores = page_data.get("rec_scores", [])
                rec_boxes = page_data.get("rec_boxes", [])
                for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                    clean_text = str(text).strip()
                    if not clean_text:
                        continue
                    if rec_boxes is not None and len(rec_boxes) > i:
                        bbox = [int(v) for v in rec_boxes[i]]
                    elif dt_polys is not None and len(dt_polys) > i:
                        bbox = self._polygon_to_bbox(dt_polys[i])
                    else:
                        bbox = [0, 0, 0, 0]
                    blocks.append(
                        OcrBlock(
                            text=clean_text,
                            confidence=round(float(score), 4),
                            bbox=_unscale_bbox(bbox),
                            page=page_num
                        )
                    )
            elif isinstance(page_data, list):
                # Классический формат PaddleOCR: список строк
                for line in page_data:
                    if not line or len(line) < 2:
                        continue
                    poly_points = line[0]        # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                    text_score = line[1]         # ("Распознанный текст", 0.985)

                    if isinstance(text_score, (list, tuple)) and len(text_score) >= 2:
                        text = str(text_score[0]).strip()
                        confidence = float(text_score[1])
                    else:
                        text = str(text_score).strip()
                        confidence = 1.0

                    if not text:
                        continue

                    bbox = self._polygon_to_bbox(poly_points)
                    blocks.append(
                        OcrBlock(
                            text=text,
                            confidence=round(confidence, 4),
                            bbox=_unscale_bbox(bbox),
                            page=page_num
                        )
                    )

        # Улучшение перевёрнутых и вертикальных надписей (проверка поворотов 90°/270°/180° для совпадений < 75%)
        blocks = self._refine_orientations(image, blocks)

        # Отсечение остаточного оптического шума (drop_score < 0.45)
        clean_blocks = []
        for b in blocks:
            c_text = b.text.strip()
            if not c_text:
                continue
            if b.confidence < 0.45:
                continue
            if len(c_text) == 1 and not c_text.isalnum():
                continue
            clean_blocks.append(b)
        blocks = clean_blocks

        logger.info(f"Распознано {len(blocks)} валидных текстовых фрагментов на странице {page_num}.")
        return blocks

    def _refine_orientations(self, image: np.ndarray, blocks: List[OcrBlock]) -> List[OcrBlock]:
        """
        Проверяет и дораспознаёт блоки с низкой уверенностью (< 75%) или вертикальной ориентацией.
        Оптимизировано: пакетная обработка (batching) и фильтрация одиночных шумовых символов.
        """
        rec_model = None
        if self._ocr and hasattr(self._ocr, "paddlex_pipeline"):
            pipe = getattr(self._ocr.paddlex_pipeline, "_pipeline", None)
            if pipe and hasattr(pipe, "text_rec_model"):
                rec_model = pipe.text_rec_model

        if rec_model is None or image is None or image.size == 0:
            return blocks

        H, W = image.shape[:2]
        pad = 3

        # Отбираем кандидатов: вертикальные надписи или буквенно-цифровые блоки с сомнительной уверенностью
        candidates = []
        for b in blocks:
            x1, y1, x2, y2 = b.bbox
            w = max(1, x2 - x1)
            h = max(1, y2 - y1)
            aspect = h / w

            # Не проверяем чистый шум (слишком короткие знаки пунктуации)
            clean_t = b.text.strip()
            is_noise = len(clean_t) <= 1 and not clean_t.isalnum()
            if is_noise:
                continue

            # Условие: вертикальный блок или осмысленный текст с уверенностью от 0.35 до 0.75
            if aspect > 1.3 or (0.35 <= b.confidence < 0.75 and len(clean_t) >= 2):
                crop = image[max(0, y1 - pad):min(H, y2 + pad), max(0, x1 - pad):min(W, x2 + pad)]
                if crop.size > 0 and crop.shape[0] >= 6 and crop.shape[1] >= 6:
                    candidates.append((b, crop))

        # Ограничиваем максимальное количество для предотвращения задержек
        candidates = candidates[:15]
        if not candidates:
            return blocks

        # Формируем пакетный список всех повернутых изображений
        all_crops = []
        mapping = []  # (block, angle)

        for b, crop in candidates:
            all_crops.append(cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE))
            mapping.append((b, 90))

            all_crops.append(cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE))
            mapping.append((b, 270))

            all_crops.append(cv2.rotate(crop, cv2.ROTATE_180))
            mapping.append((b, 180))

        try:
            results = list(rec_model.predict(all_crops))
            best_updates = {}  # id(b) -> (best_score, best_txt, best_deg, block)

            for (b, deg), r in zip(mapping, results):
                t = r.get('rec_text', '').strip()
                s = float(r.get('rec_score', 0.0))
                if len(t) > 0:
                    current_best = best_updates.get(id(b), (b.confidence, b.text, 0, b))
                    # Условие обновления:
                    if (b.confidence < 0.75 and s >= 0.65 and s > current_best[0]) or (s > current_best[0] + 0.10):
                        best_updates[id(b)] = (s, t, deg, b)

            for b_id, (score, txt, deg, b) in best_updates.items():
                if deg != 0 and txt != b.text:
                    logger.info(
                        f"Ориентация скорректирована для блока: '{b.text}' ({b.confidence:.2f}) "
                        f"-> поворот {deg}°: '{txt}' ({score:.2f}) [bbox={b.bbox}]"
                    )
                    b.text = txt
                    b.confidence = round(score, 4)

        except Exception as ex:
            logger.debug(f"Ошибка пакетной проверки поворота: {ex}")

        return blocks

    @staticmethod
    def _polygon_to_bbox(points: list) -> List[int]:
        """
        Преобразует произвольный четырёхугольный полигон [[x1,y1], [x2,y2], ...]
        в стандартный прямоугольный bounding box [x_min, y_min, x_max, y_max].
        """
        if points is None or len(points) == 0:
            return [0, 0, 0, 0]

        try:
            pts_array = np.array(points, dtype=np.float32)
            # Если размерность [4, 2]
            if pts_array.ndim >= 2:
                x_min = int(np.min(pts_array[:, 0]))
                y_min = int(np.min(pts_array[:, 1]))
                x_max = int(np.max(pts_array[:, 0]))
                y_max = int(np.max(pts_array[:, 1]))
                return [max(0, x_min), max(0, y_min), max(0, x_max), max(0, y_max)]
        except Exception:
            pass

        return [0, 0, 0, 0]
