# ID Registry (tests)

Сквозной счётчик `PRJ-T-<n>` только для артефактов в `docs/tests/`
(test-case, test-suite, test-run).

Result отдельного номера не получает: ключ `(run, case)`.

Требования индексируются отдельно: [`docs/requirements/_registry.md`](../requirements/_registry.md).

| Поле | Значение |
|---|---|
| Last issued | 0 |
| Next | 1 |

Правило: взять **Next**, создать артефакт, затем сдвинуть оба поля.

`PRJ-10` и `PRJ-T-10` — разные ID, это нормально.
