"""
Генератор тестового образца Счёта на оплату (Invoice) с таблицей товаров и услуг.
"""

from PIL import Image, ImageDraw, ImageFont


def generate_invoice(output_path: str = "sample_invoice.png"):
    width, height = 1200, 1600
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    font_path_bold = "C:\\Windows\\Fonts\\arialbd.ttf"

    font_title = ImageFont.truetype(font_path_bold, 24)
    font_bold = ImageFont.truetype(font_path_bold, 15)
    font_regular = ImageFont.truetype(font_path, 14)
    font_small = ImageFont.truetype(font_path, 12)

    # 1. Банковская плашка
    bx, by, bw, bh = 80, 60, 1040, 140
    draw.rectangle([bx, by, bx + bw, by + bh], outline="black", width=2)
    # Горизонтальные разделители
    draw.line([bx, by + 70, bx + bw, by + 70], fill="black", width=1)
    draw.line([bx, by + 105, bx + bw, by + 105], fill="black", width=1)
    # Вертикальные разделители
    draw.line([bx + 620, by, bx + 620, by + bh], fill="black", width=1)
    draw.line([bx + 720, by, bx + 720, by + 70], fill="black", width=1)
    draw.line([bx + 720, by + 70, bx + 720, by + bh], fill="black", width=1)

    # Текст банка
    draw.text((bx + 10, by + 10), "ПАО СБЕРБАНК Г. МОСКВА", fill="black", font=font_regular)
    draw.text((bx + 10, by + 30), "Банк получателя", fill="#666666", font=font_small)

    draw.text((bx + 630, by + 10), "БИК", fill="black", font=font_regular)
    draw.text((bx + 730, by + 10), "044525225", fill="black", font=font_bold)

    draw.text((bx + 630, by + 40), "Сч. №", fill="black", font=font_regular)
    draw.text((bx + 730, by + 40), "30101810400000000225", fill="black", font=font_regular)

    draw.text((bx + 10, by + 80), "ИНН 7701234567", fill="black", font=font_regular)
    draw.text((bx + 260, by + 80), "КПП 770101001", fill="black", font=font_regular)

    draw.text((bx + 630, by + 90), "Сч. №", fill="black", font=font_regular)
    draw.text((bx + 730, by + 90), "40702810938000012345", fill="black", font=font_bold)

    draw.text((bx + 10, by + 115), "ООО \"ТЕХНОЛОГИИ ИНТЕЛЛЕКТА\"", fill="black", font=font_bold)
    draw.text((bx + 10, by + 132), "Получатель", fill="#666666", font=font_small)

    # 2. Заголовок документа
    draw.text((80, 240), "Счет на оплату № 105 от 15.03.2026", fill="black", font=font_title)
    draw.line([80, 275, 1120, 275], fill="black", width=2)

    # 3. Контрагенты
    draw.text((80, 290), "Поставщик:", fill="#555555", font=font_regular)
    draw.text((200, 290), "ООО \"ТЕХНОЛОГИИ ИНТЕЛЛЕКТА\", ИНН 7701234567, КПП 770101001, г. Москва", fill="black", font=font_bold)

    draw.text((80, 320), "Покупатель:", fill="#555555", font=font_regular)
    draw.text((200, 320), "ООО \"РОГА И КОПЫТА\", ИНН 7801987654, КПП 780101001, г. Санкт-Петербург", fill="black", font=font_bold)

    draw.text((80, 350), "Основание:", fill="#555555", font=font_regular)
    draw.text((200, 350), "Основной договор поставки № Д-12 от 10.01.2026", fill="black", font=font_regular)

    # 4. Основная таблица товаров и услуг
    tx = 80
    ty = 400
    tw = 1040
    row_h = 36

    col_widths = [50, 480, 80, 70, 170, 190]
    headers = ["№", "Товары (работы, услуги)", "Кол-во", "Ед.", "Цена", "Сумма"]

    rows_data = [
        ["1", "Разработка модуля компьютерного зрения и OCR", "1", "усл.", "120 000.00", "120 000.00"],
        ["2", "Настройка распознавания документов и таблиц", "1", "усл.", "45 000.00", "45 000.00"],
        ["3", "Техническая поддержка и сопровождение системы", "2", "мес.", "15 000.00", "30 000.00"]
    ]

    total_rows = 1 + len(rows_data)
    th = total_rows * row_h

    # Внешняя рамка таблицы
    draw.rectangle([tx, ty, tx + tw, ty + th], outline="black", width=2)

    # Горизонтальные линии строк
    for r in range(1, total_rows):
        cur_y = ty + r * row_h
        draw.line([tx, cur_y, tx + tw, cur_y], fill="black", width=1 if r > 1 else 2)

    # Вертикальные линии колонок
    cur_x = tx
    for w in col_widths[:-1]:
        cur_x += w
        draw.line([cur_x, ty, cur_x, ty + th], fill="black", width=1)

    # Отрисовка заголовков
    cur_x = tx
    for i, (h_text, w) in enumerate(zip(headers, col_widths)):
        draw.text((cur_x + 8, ty + 10), h_text, fill="black", font=font_bold)
        cur_x += w

    # Отрисовка строк
    for r_idx, row in enumerate(rows_data):
        row_y = ty + (r_idx + 1) * row_h
        cur_x = tx
        for c_idx, (val, w) in enumerate(zip(row, col_widths)):
            # Выравнивание чисел вправо
            if c_idx in [0, 2, 4, 5]:
                bbox = font_regular.getbbox(val)
                text_w = bbox[2] - bbox[0]
                draw.text((cur_x + w - text_w - 10, row_y + 9), val, fill="black", font=font_regular)
            else:
                draw.text((cur_x + 8, row_y + 9), val, fill="black", font=font_regular)
            cur_x += w

    # 5. Итоги под таблицей
    foot_y = ty + th + 15
    draw.text((750, foot_y), "Итого:", fill="black", font=font_bold)
    draw.text((950, foot_y), "195 000.00 руб.", fill="black", font=font_bold)

    draw.text((750, foot_y + 25), "В том числе НДС (20%):", fill="black", font=font_regular)
    draw.text((950, foot_y + 25), "32 500.00 руб.", fill="black", font=font_regular)

    draw.text((750, foot_y + 50), "Всего к оплате:", fill="black", font=font_bold)
    draw.text((950, foot_y + 50), "195 000.00 руб.", fill="black", font=font_bold)

    draw.text((80, foot_y + 90), "Всего наименований 3, на сумму 195 000.00 руб.", fill="black", font=font_regular)
    draw.text((80, foot_y + 115), "Сто девяносто пять тысяч рублей 00 копеек", fill="black", font=font_bold)

    # 6. Подписи
    draw.line([80, foot_y + 160, 1120, foot_y + 160], fill="#cccccc", width=1)
    draw.text((80, foot_y + 190), "Руководитель:  __________________  / Иванов И.И. /", fill="black", font=font_regular)
    draw.text((650, foot_y + 190), "Бухгалтер:  __________________  / Петрова А.С. /", fill="black", font=font_regular)

    img.save(output_path, "PNG")
    print(f"Образец счёта сохранён: {output_path}")


if __name__ == "__main__":
    generate_invoice("sample_invoice.png")
