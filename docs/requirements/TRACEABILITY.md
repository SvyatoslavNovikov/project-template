# Трассировка

Три слоя связей. Декомпозиция отвечает на «из чего состоит», ассоциации — на зависимости и конфликты, реализация — на покрытие тестами, прогоны и код.

## Пространства ID

| Пространство | ID | Реестр |
|---|---|---|
| Требования | `PRJ-<n>` | [`_registry.md`](_registry.md) |
| Тесты | `PRJ-T-<n>` | [`docs/tests/_registry.md`](../tests/_registry.md) |

Связи между пространствами пишем на стороне тестов (`verifies`, `relates-to` эпик, `executes`, `results[].defect`). Result (`(run, case)`) в реестр не входит. Релизы и окружения — не ID и не связи, а значения справочников. Термины: [`GLOSSARY.md`](GLOSSARY.md).

## Справочники

### Релизы

Версии живут в [`_catalogs/releases.md`](_catalogs/releases.md). Это словарь ключей, как Versions в Jira, а не узлы трассировки.

| Где | Поле | Кардинальность |
|---|---|---|
| epic, user-story, sr, nfr | `releases` | список ключей (Fix Version) |
| bug | `affects_releases` / `releases` | где нашли / куда чиним |
| test-run | `release` | один ключ или пусто |
| test-case, test-suite | нет | кейс не привязан к версии |

Ключ обязан существовать в справочнике. Скоуп версии = тикеты с этим ключом в `releases`. На справочнике обратный список не храним.

Прогон с `release: 1.0.0` сертифицирует эту поставку. В нём могут быть кейсы по SR других версий (регресс). `build` — сборка продукта. `revision` — commit этого репозитория на старте прогона (какие шаги кейсов действовали). Их не путать.

Релиз не покрывает требования и не заменяет `verifies` / `executes`.

### Окружения

Стенды живут в [`_catalogs/environments.md`](_catalogs/environments.md).

| Где | Поле |
|---|---|
| test-run | `environment` |
| bug | `environment` (где воспроизвели) |

Ключ обязан быть в справочнике либо поле пустое (только черновой прогон).

## Слой 1. Декомпозиция

Тип: **состоит из**. Поля `parent` / `children`. Только требования.

```text
epic → user-story → system-requirement
                  ↘ nfr
```

- У эпика и бага `parent` пустой.
- У стори, SR и NFR — ровно один `parent` предыдущего уровня.
- NFR обычно висит на стори; на эпик — только если ограничение сквозное.
- SR не дробим на дочерние SR: одно требование = один SHALL.
- Папка на диске должна совпадать с `parent`.

Кейсы, сьюиты, прогоны и баги в это дерево **не входят**. Баг лежит в `bugs/`.

## Слой 2. Ассоциации

Пишем только каноническое направление. Обратную сторону не дублируем.

```yaml
links:
  - type: depends-on
    to: PRJ-7
```

| Тип | Смысл | Каноническая сторона | Кто с кем |
|---|---|---|---|
| `depends-on` | без `to` нельзя реализовать или проверить этот артефакт | у зависимого | US↔US, SR↔SR, tc↔tc |
| `constrains` | NFR накладывает ограничение на функционал | у NFR | NFR → US или SR |
| `relates-to` | смысловая связь без порядка | у меньшего ID внутри своего пространства; при связи test→requirement — на тесте | любой ↔ любой |
| `conflicts-with` | противоречие, пока не разрешено | у меньшего ID внутри пространства | любой ↔ любой |
| `supersedes` | этот артефакт заменяет `to` | у нового | тот же уровень и то же пространство; старый → `obsolete` |

Обратные (только для чтения / генерации): `required-by`, `constrained-by`, `superseded-by`. У `relates-to` и `conflicts-with` обратная совпадает с прямой.

Не используем отдельные типы `blocks`, `duplicates`, `refines`.

## Слой 3. Реализация, покрытие, прогоны

### Где лежат тесты

```text
docs/tests/cases/     PRJ-T-N-tc-….md
docs/tests/suites/    PRJ-T-N-ts-….md
docs/tests/runs/      PRJ-T-N-tr-…/PRJ-T-N-tr-….md
```

Шаблоны: [`docs/tests/_templates/`](../tests/_templates/). Правила каталога: [`docs/tests/README.md`](../tests/README.md).

Кейс не кладём под стори/SR и не кладём в папку сьюита. Прогон — снимок состава на момент старта, не живая проекция сьюита.

```yaml
id: PRJ-T-1
type: test-case
links:
  - type: verifies
    to: PRJ-4
```

```yaml
id: PRJ-T-2
type: test-suite
links:
  - type: contains
    to: PRJ-T-1
  - type: relates-to
    to: PRJ-1
```

```yaml
id: PRJ-T-3
type: test-run
release: "1.0.0"
environment: staging
revision: ""
build: ""
status: completed
outcome: failed
links:
  - type: executes
    to: PRJ-T-2
results:
  - case: PRJ-T-1
    status: failed
    defect: PRJ-20
```

```yaml
id: PRJ-20
type: bug
found_in: PRJ-T-3
found_on: PRJ-T-1
links:
  - type: defects
    to: PRJ-4
```

Result своего `PRJ-T-<n>` не имеет. Ключ: `PRJ-T-3 / PRJ-T-1`. Короткий итог — строка в `results` прогона; длинный отчёт — `runs/…/results/PRJ-T-1.md`.

| Тип | Смысл | Каноническая сторона |
|---|---|---|
| `verifies` | этот кейс проверяет требование | у тест-кейса → `PRJ-<n>` (SR/NFR) |
| `contains` | этот сьюит включает кейс | у сьюита → `PRJ-T-<n>` (кейс) |
| `executes` | этот прогон исполняет сьюит | у прогона → `PRJ-T-<n>` (сьюит) |
| `defect` | этот fail/block заведён как баг | у `results[]` → `PRJ-<n>` (bug) |
| `defects` | этот баг ломает требование | у бага → `PRJ-<n>` (SR/NFR) |
| `implemented-in` | требование реализовано в модуле/коде | у SR / NFR / US |

Обратные (только для чтения / генерации): `verified-by`, `member-of`, `executed-by`, `defected-by`. Вручную не пишем.

Сьюит и прогон **не покрывают** требования. Баг тоже не покрывает: он фиксирует поломку. `relates-to` эпик — только навигация.

`revision` на прогоне обязателен с момента старта (`in-progress`): git commit репозитория, чтобы шаги кейсов на момент исполнения можно было восстановить. `build` — сборка продукта; пока кода нет, может быть пустым.

Если `results[].defect` = `PRJ-20`, у бага `found_in` / `found_on` должны указывать на этот прогон и кейс (повторные прогоны могут ссылаться на тот же баг; `found_*` — первое обнаружение).

`implemented-in` может указывать не на `PRJ-*`, а на код:

```yaml
- type: implemented-in
  to: "code:src/test-cases"
```

### Статусы

Кейс: `draft` → `review` → `approved` → `automated` → `obsolete`

| Статус кейса | Смысл для покрытия спецификации |
|---|---|
| `draft` / `review` | ещё не покрытие |
| `approved` | ручной кейс закрывает требование |
| `automated` | то же, плюс можно гонять автоматически |
| `obsolete` | не входит |

Сьюит: `draft` → `review` → `approved` → `obsolete` (без `automated`).

Прогон: `planned` → `in-progress` → `completed` | `aborted`.

Результат кейса в прогоне: `passed` | `failed` | `blocked` | `skipped` | `not-run`.

Баг: `open` → `in-progress` → `fixed` → `verified` → `closed`, либо `rejected`.

`failed` / `blocked` без `defect` допустим только пока баг ещё не заведён; после заведения строка результата обязана на него ссылаться.

Исход прогона (`outcome`) при `completed`: есть `failed` → `failed`; иначе есть `blocked` → `blocked`; иначе нет `not-run` → `passed`.

Живая матрица спецификации: [`docs/tests/coverage-matrix.canvas.tsx`](../tests/coverage-matrix.canvas.tsx).

### Два вида «покрытия»

| Вид | Вопрос | Откуда |
|---|---|---|
| Спецификация | есть ли утверждённый кейс на SR? | `verifies` + статус кейса `approved` / `automated` |
| Исполнение | чем кончился кейс в прогоне? | `results[].status` completed run |
| Поставка | что входит в версию / чем её гоняли? | `releases` на тикете / `release` на прогоне |

Их нельзя подменять друг другом.

1. Требование **покрыто** (спецификация), если есть хотя бы один кейс `approved` или `automated` с `verifies` на этот ID.
2. Стори покрыта, если покрыты все её дочерние SR/NFR с приоритетом `must`.
3. Эпик покрыт, если покрыты все дочерние стори с приоритетом `must`.
4. `approved` требование без такого кейса — пробел в покрытии.
5. Кейс без `verifies` — сирота, в покрытие не идёт.
6. Состав сьюита и результаты прогона не влияют на покрытие спецификации.
7. Баг не закрывает пробел покрытия: на SR по-прежнему нужен `verifies`.

Черновик в секции «Проверка» у SR/NFR — идея теста, не покрытие. Покрытие начинается с `docs/tests/cases/PRJ-T-*-tc-*` и связи `verifies`.

## Инварианты

1. У стори, SR и NFR есть `parent` допустимого типа. У эпика и бага `parent` пустой.
2. У `approved` стори есть хотя бы один SR.
3. Нет циклов в `parent` и в `depends-on`.
4. Пара в `conflicts-with` не может быть оба `approved`.
5. У `obsolete` есть входящий `supersedes` (на него ссылается новый артефакт того же пространства).
6. `relates-to` не заменяет `parent` и не заменяет `depends-on`.
7. `verifies` указывает только на `system-requirement` или `nfr` (`PRJ-<n>`).
8. `contains` указывает только на `test-case` (`PRJ-T-<n>`).
9. `executes` указывает только на `test-suite` (`PRJ-T-<n>`).
10. Кейс, сьюит, прогон и баг не имеют `parent` в дереве эпик → стори.
11. Сьюит и прогон не используются как единица покрытия спецификации.
12. Result не занимает номер в `_registry.md`; уникален как `(run, case)`.
13. Состав `results` прогона не меняют после старта, если изменился сьюит — создают новый run.
14. Значения `releases` / `release` / `affects_releases` есть в [`_catalogs/releases.md`](_catalogs/releases.md) либо поле пустое.
15. Релиз и окружение не являются тикетами и не занимают номер в `_registry.md`.
16. Значение `environment` есть в [`_catalogs/environments.md`](_catalogs/environments.md) либо поле пустое.
17. `defects` указывает только на `system-requirement` или `nfr`.
18. `results[].defect` указывает только на `bug`.
19. Если задан `results[].defect`, у бага `found_in` / `found_on` совпадают с этим прогоном и кейсом либо указывают на более раннее первое обнаружение того же бага.
20. С статуса `in-progress` у прогона заполнено `revision`.
21. Баг не используется как единица покрытия спецификации.
