# Quake 1.06 — стабильность времени в текущем окружении

2026-11-09. Начальный этап продолжения kaaburgh/dosbox-staging PR #7 и [гипотез H1–H5](hypotheses.md). Исторический источник гипотез — ветка configs `bench/quake-p0-p1-local-builds`.

**Вывод:** в этой серии время существенно колеблется. Малое ускорение на 1–3% локальный тест пока не позволяет убедительно отличить от шума. Оптимизация продукта не вносилась.

## Условия и происхождение

DOSBox Staging 0.84.0-alpha свежесобран **локально из форка**, ветка `experiments/quake-headless-aa-host-profile`, commit `91774d582069d52f4d3bf04952cb6047dbdc073f`. GCC 14.2.0, CMake 4.4.4, Release `-O3 -DNDEBUG`, `OPT_JIT_BLOCK_TRACE=OFF`, tests/MT32/documentation OFF. Бинарник SHA-256 `1fb0d1f17aac13b191f3f84f13b9fad042c6956b0180911a3257c6f54433cf44`.

Debian 13, AMD EPYC 7763, 3 vCPU доступны, cgroup `cpu.max=200000 100000` (2 CPU), память 8 GiB. CPU affinity не ограничивалась. SDK распакован в пользовательский каталог из Debian trixie .deb без установки в систему. Применены ровно два исторических SDK-shim из workflow PR #6/#7 (mapper и FluidSynth), CPU/JIT не изменён. `libiir_static.a` ссылается на shared libiir. Первая линковка не нашла транзитивную libsndio; повторная с LD_LIBRARY_PATH SDK успешна без изменения исходников. Подробности setup и результатов приведены в опубликованных manifest и данных.

Оригинальный benchmark ZIP из URL workflow репозитория: https://github.com/user-attachments/files/21488506/quake-benchmark.zip . Архив, EXE и PAK проверены `prepare_official_quake.py`; их хеши в [quake-provenance.json](evidence/2026-11-09-current-session/stability-aa48/quake-provenance.json). Quake EXE SHA-256 `7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb`, PAK0 SHA-256 `35a9c55e5e5a284a159ad2a62e0e8def23d829561fe2f54eb402dbc0a9a946af`.

SDL3 dummy video, software texture, dummy audio; dynamic core, Pentium, protected cycles max, 32 MiB RAM, demo1 320×200, `-nosound -nocdaudio`. Dummy выбран для сопоставимого с PR #7 протокола; недоступность X11 в **этом** окружении не проверялась и не утверждается.

## Протокол и результаты

Использованы исходные runner и analyzer из `extras/guest-block-mapping/headless-study/` PR #7 без изменений. 4 прогрева исключены из статистики, затем 48 измерений (12 квартетов ABBA). A и B — один бинарник. Для каждого запуска новый процесс и свежая копия игры. Все **52/52** прошли 969 кадров. Фоновая сборка закончилась до теста. Детали в [manifest.json](evidence/2026-11-09-current-session/stability-aa48/manifest.json), исходные наблюдения в [timedemos.csv](evidence/2026-11-09-current-session/stability-aa48/timedemos.csv).

| Метрика, 48 измерений | Результат |
|---|---:|
| Время timedemo, медиана | 5,35 с |
| Время timedemo, min–max | 4,9–7,3 с |
| Время timedemo, p10–p90 | 5,10–6,06 с |
| CV времени timedemo | 8,55% |
| Полное время процесса, медиана | 6,678 с |
| Полное время процесса, p10–p90 | 6,252–7,520 с |
| CV полного времени | 9,35% |
| FPS медиана | 181,15 |
| FPS min–max | 132,5–197,1 |
| FPS p10–p90 | 160,40–191,18 |
| Размах p10–p90 / медиана FPS | 16,99% |
| CV FPS | 7,53% |
| Placebo A/B, геометрический эффект A/B−1 | +1,663% |
| Описательный bootstrap-интервал квартетов | −0,406…+3,899% |
| Медианы FPS первой / второй половин | 181,40 / 180,15 |
| Lag-1 корреляция log(FPS) | 0,343 |
| Запуски с cgroup throttling | 0/48 |

Quake печатает секунды и FPS с одним десятичным знаком. Время выше — непосредственно напечатанное Quake; [time-summary.json](evidence/2026-11-09-current-session/stability-aa48/time-summary.json) также содержит 969/FPS как отдельную производную оценку, не дополнительное измерение. Полное wall/CPU-время включает загрузку и остановку процесса, поэтому не заменяет время самого demo.

Интервал — описательный, из 12 квартетов; корреляция между квартетами может нарушать номинальное покрытие. Это одна серия одного окружения, не оценка минимально различимого эффекта и не частоты ложных срабатываний. Нулевой throttling не доказывает отсутствия конкуренции на физическом хосте. Заметная вариация CPU-времени процесса также не даёт свести проблему только к ожиданию планировщика: причинный механизм не установлен.

В сгенерированном [summary.json](evidence/2026-11-09-current-session/stability-aa48/summary.json) унаследованная строка limitations упоминает GitHub Actions. **Этот запуск выполнен локально в managed cloud workspace, не в Actions**; ограничение об одной серии остаётся верным. Результаты PR #6/#7 не объединялись с этой серией; разные CPU/SDK/режимы не позволяют интерпретировать разницу абсолютного FPS как ускорение.

## Доступность дальнейшего профилирования и H1–H5

Минимальный вызов `perf_event_open` для software CPU clock собственного процесса с исключёнными kernel/hypervisor возвращает EPERM. Это ограничение профилировочного механизма, не ошибка DOSBox. Обычный perf-профиль со стеками здесь пока не доступен. Не проверялась возможность всех прочих профилировочных механизмов.

В исходниках подтверждено `X86_INLINED_MEMACCESS` (`src/cpu/core_dyn_x86/decoder.h:9`); статические call sites не равны выполненным вызовам helper. `FPU_FLD_32` действительно вызывает `mem_readd` (`dyn_fpu_dh.h:14`), но из этого не следует, что все прошлые samples mem_readd пришли из x87. `MakeCodePage` вызывается при входе/возврате в dispatcher (`core_dyn_x86.cpp:308`); sampling внутри неё не доказывает повторную компиляцию или SMC invalidation.

Следующий различающий эксперимент, сформулированный на этом этапе и впоследствии частично выполненный ([отчёт](caller-attribution-2026-11-09.md)): отдельная trace-enabled сборка того же source/SDK; одновременные selected snapshots + generation-aware SIGPROF с двумя периодами; проверка вызывающих helper call sites по живым native bytes и CFG. Отдельно считать dispatcher возвраты, компиляции и invalidations, чтобы различить H3 и H4. Сохранять знаменатели selected-JIT/other-JIT/non-JIT и временное окно demo. Сырые game/native bytes остаются private. До изменения JIT нужны конкретный выполняемый блок, объяснение стоимости и минимальный guest correctness test (page crossings, faults, SMC/x87 по затронутому пути). Эта серия не ранжирует H1–H5 и не измеряет выигрыш оптимизации.


## Продолжение и расположение данных

Проверены сборка, линковка, запуск и 52/52 полных demo. FPS недостаточно стабилен для оценки малых улучшений. Опубликованы только производные данные в [stability-aa48](evidence/2026-11-09-current-session/stability-aa48/) и [исследование x87](fpu-read-study/). Двоичные файлы, SDK, Quake и сырые данные не опубликованы. Исходный runner находится в [DOSBox PR #7](https://github.com/kaaburgh/dosbox-staging/pull/7).
