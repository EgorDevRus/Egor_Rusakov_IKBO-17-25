# Практические работы

В репозитории две практические работы:

- [practical_1/2_part](practical_1/2_part) — эмулятор командной
  оболочки UNIX-подобной ОС: REPL, разбор кавычек, команды `ls`, `cd`,
  `exit`, стартовые скрипты и виртуальная файловая система из CSV;
- [practical_2](practical_2) — визуализатор графа зависимостей пакетов
  Rust (Cargo): CLI, sparse-индекс Cargo, BFS-обход, фильтрация,
  циклы, порядок загрузки, DOT/SVG и ASCII-дерево.

## Быстрый запуск

Эмулятор оболочки:

```bash
cd practical_1/2_part
./run.sh --vfs data/vfs_full.csv --script data/startup.txt
```

Визуализатор зависимостей:

```bash
cd practical_2
mkdir -p out
./run.sh -p A -r examples/simple.txt -m test -o out/a.svg --ascii tree
```

## Проверка

```bash
cd practical_1/2_part
python3 -m unittest discover -s tests -t .

cd ../../practical_2
python3 -m unittest discover -s tests -t .
```

Подробности — в README соответствующих каталогов.
Сравнение второго задания с Cargo описано в
[practical_2/docs/COMPARISON.md](practical_2/docs/COMPARISON.md).
