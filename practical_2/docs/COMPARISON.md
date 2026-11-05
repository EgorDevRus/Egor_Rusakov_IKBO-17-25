# Сравнение с Cargo

Отчёт для этапов 4 и 5: сравнение графа, порядка загрузки и
визуализации с штатными инструментами Cargo. Проверка выполнена
07.11.2026 в окружении:

- Python 3.13.15;
- Cargo 1.95.0 и Rust 1.95.0;
- реестр `https://crates.io`;
- временный Cargo-проект с зависимостями `regex` и `serde_json`
  (в репозиторий не входит).

Эталонный проект создавался во временном каталоге:

```bash
mkdir -p /tmp/cargo-compare
cd /tmp/cargo-compare
cargo init --bin --name cargo-compare-demo
cargo add regex serde_json
```

Версии пакетов и вывод Cargo могут измениться после обновления
реестра, поэтому команды для повторной проверки приведены в конце.

## 1. Пакет serde_json

Команда Cargo:

```bash
cd /tmp/cargo-compare
cargo tree -p serde_json --locked
```

Вывод Cargo:

```text
serde_json v1.0.154
├── itoa v1.0.18
├── memchr v2.8.3
├── serde_core v1.0.229
└── zmij v1.0.23
```

Команда инструмента:

```bash
mkdir -p out/comparison
./run.sh -p serde_json -r https://crates.io -m cargo \
    -o out/comparison/serde_json.svg --ascii tree --load-order \
    --no-config
```

Вывод инструмента:

```text
serde_json 1.0.154
├── itoa 1.0.18
├── memchr 2.8.3
├── serde_core 1.0.229
└── zmij 1.0.23

Порядок загрузки для serde_json (сначала зависимости):
   1. itoa
   2. memchr
   3. serde_core
   4. zmij
   5. serde_json (корень)

Граф: пакетов — 5, рёбер — 4, циклических рёбер — 0
Изображение: out/comparison/serde_json.svg (рендерер: встроенный)
DOT-файл: out/comparison/serde_json.dot
```

Для этого пакета состав графа и версии полностью совпадают с
`cargo tree`. Отличается только оформление: Cargo добавляет префикс
`v` и рисует дерево без пометок о повторных узлах.

## 2. Пакет regex

Команда Cargo:

```bash
cargo tree -p regex --locked
```

Вывод Cargo:

```text
regex v1.13.1
├── aho-corasick v1.1.5
│   └── memchr v2.8.3
├── memchr v2.8.3
├── regex-automata v0.4.18
│   ├── aho-corasick v1.1.5 (*)
│   ├── memchr v2.8.3
│   └── regex-syntax v0.8.11
└── regex-syntax v0.8.11
```

Вывод инструмента с параметрами по умолчанию:

```text
regex 1.13.1
├── regex-automata 0.4.18
└── regex-syntax 0.8.11

Порядок загрузки для regex (сначала зависимости):
   1. regex-automata
   2. regex-syntax
   3. regex (корень)

Граф: пакетов — 3, рёбер — 2, циклических рёбер — 0
```

Здесь есть расхождение: в графе инструмента отсутствуют
`aho-corasick`, `memchr` и зависимости `regex-automata`.

Причина — features Cargo. В индексе `aho-corasick`, `memchr`,
`regex-syntax` и `log` объявлены необязательными зависимостями
соответствующих пакетов (`regex` и `regex-automata`). Cargo включает
их, потому что они входят в набор features по умолчанию (`perf`,
`unicode`, `meta` и другие). Инструмент не вычисляет граф features и
по умолчанию пропускает все необязательные зависимости.

Флаг `--include-optional` позволяет учесть такие зависимости, но он
включает **все** необязательные зависимости, а не только те, которые
включены выбранными features. Поэтому для точного совпадения с Cargo
нужен полноценный резолвер features, которого в учебном инструменте
нет.

## 3. Порядок загрузки

Инструмент выдаёт детерминированный порядок: зависимости идут раньше
зависимых пакетов, а независимые пакеты сортируются по имени. Для
`serde_json` это:

```text
itoa, memchr, serde_core, zmij, serde_json
```

Cargo не предоставляет отдельной команды «порядок загрузки». Порядок
можно наблюдать по журналу сборки:

```bash
cargo clean
cargo build --locked -j1 -v
```

Фрагмент журнала:

```text
Compiling memchr v2.8.3
Compiling serde_core v1.0.229
Compiling zmij v1.0.23
Compiling aho-corasick v1.1.5
Compiling regex-syntax v0.8.11
Compiling serde_json v1.0.154
Compiling regex-automata v0.4.18
Compiling itoa v1.0.18
Compiling regex v1.13.1
Compiling cargo-compare-demo v0.1.0
```

Этот журнал не является гарантированным «порядком загрузки»: Cargo
строит пакеты параллельно, а порядок независимых пакетов зависит от
планировщика и кэша. Даже с `-j1` порядок вывода не документирован.
Поэтому сравнивать имеет смысл не точную последовательность
независимых пакетов, а отношение «зависимость раньше зависимого» и
состав графа.

Для `serde_json` множество пакетов совпадает, и все зависимости
действительно идут раньше корня. Для `regex` порядок инструмента
неполон по той же причине, что и граф: пропущены необязательные
зависимости, включаемые features Cargo.

## 4. Визуализация

Инструмент формирует:

- DOT-описание графа;
- SVG-изображение через Graphviz, а при его отсутствии — встроенным
  рендерером;
- ASCII-дерево при `--ascii tree`.

Cargo не имеет встроенного экспорта графа в SVG. Его штатные средства —
это текстовое дерево `cargo tree` и машиночитаемый JSON
`cargo metadata`. Поэтому сравнение визуализации выполняется так:

1. Структура ASCII-дерева сравнивается с `cargo tree` (разделы 1 и 2).
2. DOT-файл можно отрисовать стандартным Graphviz:

```bash
dot -Tsvg out/comparison/serde_json.dot \
    -o out/comparison/serde_json-graphviz.svg
```

3. `cargo metadata --format-version 1` можно использовать как
   независимый источник списка пакетов и зависимостей при проверке
   DOT-файла.

Для `serde_json` DOT и ASCII совпадают с `cargo tree` по составу
пакетов и рёбер. Для `regex` расхождение остаётся из-за features:
DOT-файл не содержит необязательные зависимости, которые Cargo
включает по умолчанию.

## 5. Ограничения инструмента

- Не вычисляются features Cargo; необязательные зависимости
  включаются только флагом `--include-optional` целиком.
- Не используется `Cargo.lock`: выбираются самые новые подходящие
  стабильные версии на момент запуска.
- Не вычисляются платформенные `cfg`-условия; отбрасываются только
  заведомо ложные цели.
- Граф хранит пакеты по имени, поэтому разные версии одного пакета
  могут схлопнуться в один узел.
- Циклические зависимости обрабатываются и помечаются, тогда как
  настоящий Cargo такие графы обычно не допускает.
- Порядок загрузки детерминирован, но не совпадает с порядком
  планировщика Cargo и не является его заменой.

## 6. Повторная проверка

```bash
cd practical_2
mkdir -p out/comparison

# Граф и порядок загрузки инструмента.
./run.sh -p serde_json -r https://crates.io -m cargo \
    -o out/comparison/serde_json.svg --ascii tree --load-order \
    --no-config

# Эталон Cargo (временный проект).
cd /tmp/cargo-compare
cargo tree -p serde_json --locked
cargo tree -p regex --locked

# Визуализация DOT через Graphviz.
cd - >/dev/null
dot -Tsvg out/comparison/serde_json.dot \
    -o out/comparison/serde_json-graphviz.svg
```

