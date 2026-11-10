"""Тесты проверки документов по правилам."""

from app.checks.blocks import parse_blocks
from app.checks.engine import check_html
from app.checks.numbers_ru import find_number_words, number_to_words
from app.checks.rules import account_valid, inn_valid, ogrn_valid

CONTRACT = (
    '<h1 style="text-align:center">ДОГОВОР ПОСТАВКИ № 124-А</h1>'
    "<p>г. Самара      21 июля 2025 г.</p>"
    "<h2>1. ПРЕДМЕТ ДОГОВОРА</h2><p>1.1. Поставщик передаёт Покупателю мебель.</p>"
    "<h2>2. ЦЕНА ДОГОВОРА</h2><p>2.1. Общая стоимость составляет 1 250 000 (один миллион двести тысяч) рублей 00 копеек.</p>"
    "<h2>3. ПОРЯДОК РАСЧЁТОВ</h2><p>3.1. Оплата в течение 10 рабочих дней.</p>"
    "<h2>4. ПОСТАВКА ТОВАРА</h2><p>4.1. Поставка не позднее 31 сентября 2025 г.</p>"
    "<p>4.2. Поставшик доставляет Товар на склад.</p><p>4.4. Риск переходит к Покупателю.</p>"
    "<h2>5. ОТВЕТСТВЕННОСТЬ СТОРОН</h2><p>5.1. Неустойка 0,1 % в день.</p>"
    "<h2>6. РАЗРЕШЕНИЕ СПОРОВ</h2><p>6.1. Споры — в Арбитражном суде.</p>"
    "<h2>7. СРОК ДЕЙСТВИЯ И РЕКВИЗИТЫ</h2><p>7.1. Расторжение — в соответствии с п. 9.3 Договора.</p>"
    "<p>Поставщик: ООО «Вектор Снаб», ИНН 7725123540, КПП 772501001.</p>"
    "<p>Покупатель: ООО «Северный Терминал», ИНН 6311098769, КПП 631101001.</p>"
)


def _by_rule(result, rule):
    return [f for f in result["findings"] if f["rule"] == rule]


def test_number_words():
    assert find_number_words("один миллион двести тысяч рублей")[0] == 1_200_000
    assert find_number_words("Сорок пять тысяч триста двенадцать")[0] == 45_312
    assert number_to_words(1_250_000) == "один миллион двести пятьдесят тысяч"
    assert number_to_words(2_021) == "две тысячи двадцать один"
    assert number_to_words(11_000) == "одиннадцать тысяч"


def test_checksums():
    assert inn_valid("7725123450") and not inn_valid("7725123540")
    assert inn_valid("6311098769")
    assert ogrn_valid("1027700132195") and not ogrn_valid("1027700132196")
    bik = "044525225"
    base = "4070281043800000000"
    account = next(base[:8] + str(k) + base[9:] + "2" for k in range(10) if account_valid(base[:8] + str(k) + base[9:] + "2", bik))
    assert account_valid(account, bik)


def test_contract_findings():
    r = check_html(CONTRACT, "CONTRACT")
    amount = _by_rule(r, "amount_words")
    assert len(amount) == 1 and amount[0]["replacement"] == "один миллион двести пятьдесят тысяч"
    assert amount[0]["quote"] == "один миллион двести тысяч"
    inn = _by_rule(r, "inn")
    assert len(inn) == 1 and inn[0]["quote"] == "7725123540" and inn[0]["severity"] == "critical"
    date = _by_rule(r, "date")
    assert len(date) == 1 and date[0]["quote"] == "31" and date[0]["replacement"] == "30"
    num = _by_rule(r, "numbering")
    assert len(num) == 1 and num[0]["quote"] == "4.4" and num[0]["replacement"] == "4.3"
    spell = _by_rule(r, "spelling")
    assert len(spell) == 1 and spell[0]["replacement"] == "Поставщик"
    ref = _by_rule(r, "reference")
    assert len(ref) == 1 and "9.3" in ref[0]["quote"]
    assert not _by_rule(r, "template")                 # все обязательные разделы есть
    assert not _by_rule(r, "double_space")             # выравнивание даты не считается двойным пробелом
    assert r["counts"]["critical"] == 3
    assert r["findings"][0]["severity"] == "critical"  # сначала критичные


def test_offsets_point_to_text():
    r = check_html(CONTRACT, "CONTRACT")
    blocks, _ = parse_blocks(CONTRACT)
    for f in r["findings"]:
        if f["block"] is not None and f["start"] is not None:
            assert blocks[f["block"]].text[f["start"]:f["end"]] == f["quote"]


def test_blocks_skip_nested_and_tables():
    blocks, tables = parse_blocks("<p>A <b>жирный</b><br>текст</p><table><tr><td><p>x</p><p>y</p></td><td>z</td></tr></table><ul><li>п<ul><li>в</li></ul></li></ul>")
    assert [b.text for b in blocks] == ["A жирныйтекст", "xy", "z", "пв"]
    assert tables[0].rows == [[1, 2]]


def test_table_total_and_row_math():
    html = ("<table><tr><td>Наименование</td><td>Кол-во</td><td>Цена</td><td>Сумма</td></tr>"
            "<tr><td>Стол</td><td>2</td><td>5 000</td><td>10 000</td></tr>"
            "<tr><td>Стул</td><td>4</td><td>1 500</td><td>7 000</td></tr>"
            "<tr><td>Итого</td><td></td><td></td><td>17 000</td></tr></table>")
    r = check_html(html)
    row = _by_rule(r, "row_math")
    assert len(row) == 1 and row[0]["quote"] == "7 000" and row[0]["replacement"] == "6 000"
    # итог сверяется с исправленными строками: 10 000 + 6 000 = 16 000, а не 17 000
    total = _by_rule(r, "table_total")
    assert len(total) == 1 and total[0]["replacement"] == "16 000"


def test_table_total_consistent_with_row_fix():
    # Строка «Шкаф» ошибочна (3 × 80 000 = 240 000), но итог 480 000 верен для исправленных строк — менять итог не нужно
    html = ("<table><tr><td>Товар</td><td>Кол-во</td><td>Цена</td><td>Сумма</td></tr>"
            "<tr><td>Стол</td><td>4</td><td>60 000</td><td>240 000</td></tr>"
            "<tr><td>Шкаф</td><td>3</td><td>80 000</td><td>250 000</td></tr>"
            "<tr><td>Итого</td><td></td><td></td><td>480 000</td></tr></table>")
    r = check_html(html)
    assert [f["replacement"] for f in _by_rule(r, "row_math")] == ["240 000"]
    assert not _by_rule(r, "table_total")


def test_template_missing_sections():
    r = check_html("<h1>ДОГОВОР № 5</h1><h2>1. Предмет</h2><p>1.1. Текст.</p><h2>2. Цена</h2><p>2.1. 100 рублей.</p><h2>3. Срок</h2><p>3.1. До конца года.</p>", "CONTRACT")
    missing = {f["title"] for f in _by_rule(r, "template")}
    assert missing == {"Нет раздела «Ответственность сторон»", "Нет раздела «Разрешение споров»", "Нет раздела «Реквизиты и подписи сторон»"}


def test_misc_rules():
    r = check_html('<p>Оплата согласно договора в течении 5 дней. Цена  указана. Как в "Положении" и «Регламенте». Дoговор договор.</p>'
                   "<p>с 10.05.2025 по 01.03.2025 г.</p><p>Дата: «___» ________ 2025 г.</p>")
    rules = {f["rule"] for f in r["findings"]}
    assert {"spelling", "double_space", "quotes", "homoglyph", "period", "placeholder"} <= rules
    fixes = {f["replacement"] for f in _by_rule(r, "spelling")}
    assert {"согласно договору", "в течение "} <= fixes
    assert any(f["replacement"] == "Договор" for f in _by_rule(r, "homoglyph"))


def test_dictionary_spelling():
    from app.checks.speller import speller
    assert speller.available() and speller.known("наймодателем") and speller.known("неустойки") and speller.known("Счёт")
    assert not speller.known("договр")
    html = ("<p>Стороны заключили договр аренды, оплпта вносится ежемесячно, арендатра уведомляют заранее.</p>"
            "<p>Наймодатель Сединкин передаёт комнату; перерасчеты делает ЕИРЦ; сканы и сканов хранятся в архиве.</p>")
    result = check_html(html)
    typos = {f["quote"]: f["replacement"] for f in _by_rule(result, "spelling-dict")}
    # фамилия, сокращение, редкая форма слова и повторяющийся термин опечатками не считаются
    assert typos == {"оплпта": "оплата", "арендатра": "арендатора"}
    # «договр» — в списке частых ошибок: на этом месте остаётся одна пометка, от того правила
    assert [f["replacement"] for f in _by_rule(result, "spelling") if f["quote"] == "договр"] == ["договор"]

