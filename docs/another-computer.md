# Проверка на другом компьютере

Нужны Git, uv, Python 3.13 и GnuCash. Импорт проверен на GnuCash 5.14; на другом компьютере запишите версию приложения и ОС. Все команды запускайте из корня репозитория.

## Получить рабочую ветку

Для новой копии репозитория:

```bash
git clone --branch feature/sberbank-gnucash git@github.com:dvoloskov/finreader.git
cd finreader
uv sync --locked
uv run pytest
```

Для существующей копии сначала проверьте `git status`: не переключайте ветку поверх несохранённых изменений. Затем получите `origin/feature/sberbank-gnucash` обычным fetch/switch без reset или force.

## Сначала синтетический пример

Создайте новую тестовую книгу. Команда откажет, если каталог уже существует, чтобы не затереть предыдущий импорт:

```bash
uv run python -c "from pathlib import Path; import shutil; p = Path('local/acceptance'); p.mkdir(parents=True, exist_ok=False); shutil.copyfile('tests/data/gnucash/opening.gnucash', p / 'disposable.gnucash')"
uv run python -m finreader export tests/data/sberbank_report_coherent.html --book local/acceptance/disposable.gnucash --mapping tests/data/gnucash/mapping.toml --output local/acceptance/import.csv
```

Откройте именно `local/acceptance/disposable.gnucash` через File → Open. Импортируйте CSV по [инструкции](gnucash-acceptance.md): GnuCash Export Settings без «4», Multi-split, запятая, UTF-8, одна строка заголовка, даты YYYY-MM-DD и десятичная точка. Проверьте назначения всех колонок, особенно Description, Notes, Amount и Value.

Ожидается восемь новых транзакций. Сохраните книгу и полностью закройте GnuCash, затем выполните:

```bash
uv run python -m finreader verify --book local/acceptance/disposable.gnucash --manifest local/acceptance/import.csv.manifest.json
uv run python -m finreader export tests/data/sberbank_report_coherent.html --book local/acceptance/disposable.gnucash --mapping tests/data/gnucash/mapping.toml --output local/acceptance/import.csv
```

Первая команда должна подтвердить проводки и остатки, вторая — сообщить `Already imported and verified: 8 transactions; no files written.` Не импортируйте CSV повторно вручную.

## Затем настоящий отчёт — только с копией книги

- Полностью закройте GnuCash перед копированием своей книги. Оригинал не используйте для импорта. Храните отдельную рабочую копию вне синхронизируемого каталога, в ignored `local/`.
- Отчёт, личный mapping, CSV и manifest тоже храните только в `local/`. Git их не переносит; при необходимости передавайте приватные файлы отдельно безопасным способом.
- Создайте личный mapping по [контракту](pipeline.md#mapping-and-snapshots). Синтетический mapping не подходит для вашей книги. Счета должны уже существовать в копии книги.
- Выберите период без уже проведённых и более поздних брокерских операций. Начальные количества и НКД должны совпадать с отчётом; стоимость облигаций берётся из учётной книги, не из рыночной оценки.
- Выполните export, импорт в копию, сохранение/закрытие, verify и повторный export по тому же порядку, заменив пути на личные. Число операций будет зависеть от отчёта.
- При отказе проверки остановитесь и сохраните текст ошибки без приватных данных. Не обходите проверки и не удаляйте блокировку открытой книги. Для нового импорта берите свежую копию, не исправляйте оригинал.

Продажи, полные погашения, валютные операции и налоговый расчёт пока не поддержаны. Успех синтетического теста не означает поддержку любого настоящего отчёта.
