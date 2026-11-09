# Phase 1 — проверенные утверждения (evidence)

Независимый аудит, 2026-11-09. Каждая строка — одно утверждение, источник,
способ проверки и статус. Статусы:

- **CONFIRMED** — воспроизведено в этой сессии прямым измерением или
  детерминированным тестом;
- **LIKELY** — согласуется с несколькими независимыми наблюдениями, но
  прямое измерение отсутствует;
- **HYPOTHESIS** — правдоподобно, проверочный эксперимент сформулирован,
  но не выполнен;
- **UNSUPPORTED** — не воспроизведено или противоречит данным.

Сырые native/guest байты, perf.data, адреса хост-процесса и игровые файлы
не публикуются. Здесь только производные числа.

## 0. Окружение и сборки

| Параметр | Значение |
|---|---|
| Хост | Intel Xeon (family 6, model 207, Emerald Rapids), 4 vCPU, Firecracker VM, без hardware PMU (`perf_event_open` hardware → ENOENT; software `cpu-clock` работает) |
| Toolchain | Debian 13 (trixie) chroot на Ubuntu 24.04: GCC 14.2.0, CMake 3.31.6, SDL 3.2.10, perf (linux-perf), valgrind 3.24.0 |
| Исходники | `kaaburgh/dosbox-staging` `main` = `27b1b7ca719c21ef3444f7ad1cf2d9cd439527cc` (= base PR #1). С `OPT_JIT_BLOCK_TRACE=OFF` код ядра идентичен PR #7 head `91774d58` (все изменения PR #1–#7 в `src/` под `#ifdef DOSBOX_JIT_BLOCK_TRACE`) |
| Конфигурация | `-DCMAKE_BUILD_TYPE=Release -DUSE_SYSTEM_LIBS=ON -DOPT_MT32EMU=OFF -DOPT_TESTS=OFF -DOPT_DOCUMENTATION=OFF`, те же два SDK-shim (mapper, FluidSynth), что и в PR #6/#7; `libiir_static.a → libiir.so` |
| base | SHA-256 `704f46286e0f87a1cdb2b226c72b680d7cc49a64ba687db9da3f2b73bb1b029e` (пересборка дала побайтно тот же файл) |
| pr9 | base + однострочное изменение PR #9 (`FPU_FLD_32` → `mem_readd_inline<WithBreakpoints>`), SHA-256 `bd44debcbca743548c55c9bc8e32f7f18e950cdd8718ef72677b82c42601cdc8` |
| pr10 | base + `experimental-inline.patch.b64` из PR #10 (decoded SHA-256 `6f0805fd…54e6`), SHA-256 `527ce4c6f5f54a23c04026d5390cba72ffa3f256009759d67ef38fa1886da667`; компилятор предупреждает `FPU_FLD_32 defined but not used` |
| map-base / map-pr10 | то же + исследовательский `jit_perf_map.h` (`-DDOSBOX_JIT_PERF_MAP=1`): perf JIT map + дамп блоков; генерацию кода не меняет. SHA-256 `fe935f59…e639` / `6cfe79eb…477b` |
| Quake | shareware 1.06 с зеркала `ftp.gwdg.de/.../idstuff/quake/quake106.zip` (SHA-256 архива `ec6c9d34…3239`); `QUAKE.EXE` `7cdb2441…161fb`, `PAK0.PAK` `35a9c55e…946af` — совпадают с хешами предыдущих отчётов. Официальный benchmark ZIP (`github.com/user-attachments/…`) недоступен через GitHub-прокси этой сессии |
| Запуск | dynamic core, `cputype=pentium`, 32 MiB, SDL dummy video/audio, software texture, `quake.exe -nosound -nocdaudio -condebug -width 320 -height 200 +timedemo demo1`; CWSDPMI из дистрибутива (paging включён) |

## 1. Цепочка guest → JIT → native → helper → стоимость

| # | Утверждение (источник) | Как проверено | Статус |
|---|---|---|---|
| E1 | Горячие guest-блоки Quake: `0x10572`, `0x2f5cf`, `0x306bd`, `0x10d3b`, `0x10f4a`, `0x10ca0`, `0x3e455`, `0x12dd0`, `0x1143f`, `0x112cc`, `0x3e29a`, `0x11343`… (PR #1–#5, hotspot-functions.md) | perf `cpu-clock` 1999 Hz только в окне demo, атрибуция по (время, RIP) к живому поколению блока из собственного дампа; 14 672 сэмпла main thread | **CONFIRMED** (тот же набор и порядок величин на другом хосте/CPU) |
| E2 | Атрибуция native RIP к guest-блоку по поколениям надёжна | Дамп пишет время создания и `Clear()` каждого поколения (CLOCK_MONOTONIC = `perf --clockid monotonic`). 8 339 из 8 693 JIT-сэмплов (95.9%) попали в живое поколение; 354 — в код кэша вне блоков (link/runcode-заглушки). За весь прогон 7 733 поколения и 183 очистки | **CONFIRMED** для блочного уровня. Инструкционный уровень — только с оговоркой о skid (см. E9) |
| E3 | Static размеры: span-блоки 2 219–3 160 B и 28–42 call sites; Z-span `0x10d3b` 516 B и 4 call sites (PR #2/#4) | Дамп: `0x1143f` 2 224 B/28 call, `0x11343` 3 136/42, `0x11216` 3 168/42, `0x10d3b` 528/4 (выравнивание 16 B) | **CONFIRMED** |
| E4 | `surf8` блоки содержат живую подменённую константу `0x0018007c` вместо `0x12345678` (H3) | В native коде `0x3e455` присутствует `lea r15d,[rax+r14+0x18007c]` | **CONFIRMED** |
| E5 | `0x10572` — цикл `REP MOVSD` в VGA chained-память (PR #8) | helper→caller: `VGA_ChainedVGA_Handler::writed` 106, `mem_writed_checked_dcx64` 97, `PageHandler::writed_checked` 27 сэмплов с вызывающим блоком `0x10572`; блок 2.2% времени | **CONFIRMED** |
| E6 | `mem_readd` в профиле в основном вызывается из `FPU_FLD_32` (caller-attribution: 153/216) | DWARF unwind (`--call-graph dwarf`): 668 из 734 сэмплов `mem_readd` имеют непосредственным вызывающим `FPU_FLD_32` (91%), 39 — `FPU_FLD_64` | **CONFIRMED** (сильнее, чем прежняя оценка по frame pointers) |
| E7 | x87-путь чтения m32 — заметная доля времени (H5, PR #7/#8/#10) | Включительная доля `FPU_FLD_32` (self + callees) = 1 073/14 672 = **7.3%** окна demo. `FPU_FST_32` 0.6%, `FPU_FLD_64` 0.4% | **CONFIRMED** как верхняя граница времени helper-части. Затраты на подготовку вызова в самом JIT сюда не входят |
| E8 | Вызывающие x87 helper блоки: `0x306bd`, `0x10f4a`, `0x10ca0`, `0x30b20`, `0x112cc`, `0x2f5cf` (PR #8/#10) | helper→caller, см. `data/perf-demo-window-base.json` | **CONFIRMED** |
| E9 | «Сэмплы на PUSHFQ/flag-save» указывают на стоимость сохранения флагов (PR #4: «4 flag-save samples») | 11.6% JIT-сэмплов имеют IP сразу после `PUSHFQ`, 5.7% — после `POPFQ`. Микробенчмарк в той же последовательности (`microbench/flags_save.c`): `PUSHFQ+LEA` ≈ +0.3–0.8 нс, `POPFQ` ≈ **+10 нс** (Emerald Rapids) | `POPFQ` дорогой — **CONFIRMED** (микро + инъекция in situ, §4). `PUSHFQ` дешёвый на одно исполнение (≈0.3 нс), но исполняется 604 M раз за окно → ≈3%; 6.6% сэмплов после `PUSHFQ` частично объясняются частотой, остальное — вероятная концентрация timer-сэмплов (**LIKELY**) |
| E10 | ld-linux ≈14% и libc ≈13–16% сэмплов (PR #7 headless study) | perf: ld.so — 0 сэмплов, libc 2.4%, SDL3 12.3%, ядро 0.5% | ld.so-доля **UNSUPPORTED** (вероятно артефакт SIGPROF-preload профайлера); вклад SDL-презентации в харнессе **CONFIRMED** |
| E11 | Хост-презентация кадров (SDL software renderer, dummy) занимает значимую долю main thread | Включительно `RENDER_EndUpdate` 14.1%, `GFX_MaybePresentFrame` 12.8% | **CONFIRMED**; размывает любые JIT-эффекты в FPS/CPU-метриках (Амдал) |
| E12 | Стековые PUSH/POP всегда вызывают out-of-line checked helper | Исходник: `dyn_push` → `gen_call_function(mem_writed_checked)`, `dyn_pop` → `mem_readd_checked` (`decoder.h` ~716–760); профиль: self 2.6% + 2.0% с вызывающим JIT | **CONFIRMED** |
| E13 | RET near и косвенные переходы уходят в C++ dispatcher | Исходник: `dyn_ret_near` → `gen_return(BR_Normal)`; `restart_core` вызывает `MakeCodePage` на каждом входе. Профиль: `CPU_Core_Dyn_X86_Run` self 2.2%, `MakeCodePage` 1.4% (205 сэмплов, все из dispatcher); частота — 18.0 M входов за окно (§4) | **CONFIRMED** |
| E14 | `MakeCodePage` в профиле не означает повторной компиляции/SMC (stability report) | Исходник `core_dyn_x86.cpp` (restart_core) | **CONFIRMED** |
| E15 | Переходы dyn → normal core с полной синхронизацией FPU | `CPU_Core_Normal_Run` 0.65% incl., `sync_dh_fpu_and_run_normal_core` 0.57% incl., `FPU_SetPRegsFrom`/`GetPRegsTo` 0.44% | **CONFIRMED** как ~1.3%; какие guest-инструкции вызывают fallback — не установлено |

## 2. Семантика PR #9 и PR #10

| # | Утверждение | Как проверено | Статус |
|---|---|---|---|
| S1 | PR #9 не меняет семантику: `mem_readd<op>` определён как `return mem_readd_inline<op>(address)` | Исходник `memory.cpp:612–616`; тест `PFPREC` даёт побайтно одинаковый вывод для base и pr9 на обоих ядрах | **CONFIRMED** |
| S2 | PR #9: helper растёт с 20 до 120 B, лишний вызов `mem_readd` исчезает | `nm`/`objdump` base vs pr9: `FPU_FLD_32` 0x14 → 0x78 B; в base быстрый путь = 2 call/ret + 4 push/pop в `mem_readd`; в pr9 = 1 call/ret без push/pop | **CONFIRMED** |
| S3 | В baseline x87-загрузка из отсутствующей страницы обрабатывается вложенным `PAGING_PageFault` (legacy), а не точным исключением | Исходник: `FPU_FLD_32` → `mem_readd` → `InitPageHandler::readd` → `InitPage` → `PAGING_PageFault` → `DOSBOX_RunMachine` | **CONFIRMED** |
| S4 | **Новое:** в dynamic core baseline guest-обработчик #PF для x87 memory-операнда видит **неверный EIP** (начало JIT-блока) и **устаревшие** регистры | `tests/pfprec.asm`: 8 случаев; normal core — все `E=I R=ok`; dynamic base/pr9 — integer load `E=I R=ok` (позитивный контроль), все x87 (FLD/FADD/FILD/FIADD m32, cross-page FLD m32, FLD m64, FSTP m32) — `E=B R=stale` | **CONFIRMED** (детерминированный тест) |
| S5 | PR #10 меняет наблюдаемую guest-семантику загрузок m32 | `PFPREC` на pr10/dynamic: FLD/FADD/FILD/FIADD m32 и cross-page FLD m32 → `E=I R=ok` (как normal core и железо); FLD m64 и FSTP m32 остаются `E=B R=stale` | **CONFIRMED**: изменение в сторону архитектурной корректности, но это изменение поведения, а не «нейтральная оптимизация» |
| S6 | 36/36 оракулов PR #10 и fault-тесты PR #9 подтверждают корректность | Обработчики в `FPU_PF*.asm`, `pagefault.asm` не проверяют сохранённый EIP и регистры; дифференциальные сравнения base↔candidate не видят общих отклонений от архитектуры | Утверждения о прохождении — верны; как доказательство эквивалентности/корректности — **UNSUPPORTED** (тесты нечувствительны к S4/S5) |
| S7 | Финальные значения после #PF корректны во всех вариантах | `PFPREC`: `V=ok`, ровно один #PF во всех 48 комбинациях | **CONFIRMED** |
| S8 | PR #10 не меняет побочные эффекты MMIO | Исходник: `PageHandler::readd_checked` по умолчанию вызывает `readd`; cross-page пути и там и там побайтные (4 вызова handler) | **CONFIRMED** (по исходнику; отдельного MMIO-теста с побочными эффектами чтения не выполнялось) |
| S9 | PR #10 теряет heavy-debugger memory-read breakpoints для x87 m32 в dynamic core | Быстрый путь `dyn_read_word` не вызывает `DEBUG_UpdateMemoryReadBreakpoints`; `FPU_FLD_32` вызывал. Так же уже ведут себя integer-загрузки dynamic core | **CONFIRMED по исходнику**, не исполнялось (нужна сборка `OPT_HEAVY_DEBUGGER`) |
| S10 | PR #10 увеличивает код (PR #10 README) | `0x10f4a` 832 → 2 144 B, `0x306bd` 832 → 2 384, `0x112cc` 2 512 → 2 944; весь JIT за прогон 3.98 → 4.21 MB (+5.8%), 7 733/7 731 поколений, max блок 4 384 B в обоих | **CONFIRMED** |
| S11 | Риск переполнения блока (`CacheBlock overrun`, E_Exit) | `tests/jitsize.asm`: блок из 33 x87-загрузок с SIB+segment: base 1 120 B, pr10 4 608 B; вариант с грязными GPR: 1 152 → 4 368 B. Лимит резервирования 12 288 B (`CACHE_MAXSIZE`) | Риск низкий (запас ~2.7×) — **CONFIRMED** для PR #10; при расширении на m64/m80/stores нужно перепроверять |
| S12 | #MF/FWAIT не доставляются (pre-existing) | Исходник: host CW всегда `|0x3f` (`FPU_FLDCW_DH`), `WAIT` — no-op. Не регрессия PR #9/#10 | **CONFIRMED** (по исходнику; отдельно от регрессий) |

## 3. Производительность и шум

| # | Утверждение | Как проверено | Статус |
|---|---|---|---|
| P1 | Малый эффект (1–3%) нельзя доказать FPS-прогонами на общем хосте (PR #6/#7) | Новый протокол: fixed `cpu_cycles_protected=1000000` (выше устойчивой скорости → «lag mode»), метрика — CPU-время main thread от «Playing demo» до результата (`/proc/<pid>/task/<pid>/schedstat`). Guest-время **детерминировано**: 3.0 s / 326.7 fps во всех 34 прогонах. Тем не менее CV CPU-времени 7–10%, плацебо base2 vs base **−6.0%** [−12.7, +0.4] (8 блоков) | **CONFIRMED**, и шум — в скорости хоста, не в гостевой работе и не в планировщике (runqueue wait ≈0.3 ms) |
| P2 | PR #9: +4.08% [−0.36, +10.37] | Тот же протокол: pr9 vs base **−3.3%** [−10.8, +4.7] | Не воспроизведено; **UNSUPPORTED** как ускорение (внутри шума) |
| P3 | PR #10: +9.59% [−3.27, +26.26] | Тот же протокол: pr10 vs base **+1.0%** [−5.0, +7.1] | Не воспроизведено; **UNSUPPORTED** как ускорение (внутри шума) |
| P4 | Верхняя граница выигрыша от удаления x87 helper | E7: 7.3% окна demo в `FPU_FLD_32`+callees. +9.59% требует, чтобы JIT-сторона сэкономила ещё ≥2–3% | Заявка PR #10 выше границы helper-части — **LIKELY завышена** |
| P5 | Детерминированная метрика работы через callgrind Ir | `--smc-check=none`: тестовая DOS-программа под Valgrind не выводит результат (исполняются устаревшие трансляции JIT, несмотря на W^X `mprotect`); `--smc-check=all-non-file`: корректно, но Quake не дошёл до консоли за 6 мин | **UNSUPPORTED в этом окружении** — заменено точными счётчиками (§4) |

## 4. Точные частоты событий и стоимость на событие

Сборка `JitCounters` (`instrumentation/apply_jit_counters.py`, SHA-256
`eca86831…2711`): счётчики в C++ и в сгенерированном коде (последовательность
`push/mov/lea/mov/pop`, флаги не трогает). Guest-результаты совпадают с base
(969 кадров, 3.0 s, 326.7 fps; `PFPREC` и `JITSIZE` — побайтно тот же вывод).
Окно — от «Playing demo» до строки результата (SIGUSR1-снимки), fixed cycles
1 000 000. Два независимых прогона совпадают в пределах 0.01–0.3%
(остаток — задержка снимка). Данные: `data/counts-demo-window-base.json`.

| Событие в окне demo | Количество | На кадр | Доля времени (perf, §1) | Оценка стоимости на событие |
|---|---:|---:|---:|---:|
| `PUSHFQ` в JIT-коде (`gen_protectflags`) | 604 M | 624 k | — | ≈0.3 нс in situ (инъекция, ниже) → **≈3%** окна |
| `POPFQ` в JIT-коде (`gen_needflags`) | 37.3 M | 38.5 k | 3.2% (сэмплы после `POPFQ`) | ≈10–12 нс in situ → **≈6%** окна |
| `FPU_FLD_32` вызовы | 152.4 M | 157 k | 7.3% incl. | ≈2.8 нс helper-части |
| `FPU_FST_32` вызовы | 36.1 M | 37 k | 0.6% incl. | ≈1 нс |
| `FPU_FLD_64` вызовы | 2.5 M | 2.5 k | 0.4% incl. | — |
| helper PUSH (`mem_write{w,d}_checked`) | 65.4 M | 67 k | 2.6% self | ≈2.4 нс (вместе с POP) |
| helper POP (`mem_read{w,d}_checked`) | 39.5 M | 41 k | 2.0% self | |
| входы в C++ dispatcher (`MakeCodePage` на каждом) | 18.0 M | 18.6 k | 3.6% self | ≈11 нс |
| fallback в normal core (с синхронизацией FPU) | 1.95 M | 2.0 k | ≈1.3% | ≈35–40 нс |
| inline-запись → handler (TLB-промах, VGA) | 15.75 M | 16.3 k (= 320×200/4) | ≈2.2% | ≈8 нс |
| inline-чтение → handler (TLB-промах) | 0.16 M | 163 | — | — |
| созданные JIT-блоки | 3 730 | 3.8 | — | компиляция в окне пренебрежима |

Стоимость на событие = (доля времени × CPU-время окна ≈ 5.9–6.0 s) / число
событий; это оценка, а не измерение, кроме строк с инъекцией.

**Инъекция стоимости флагов** (`instrumentation/apply_flag_injection.py`):
после каждого `POPFQ` добавлено 4× `PUSHFQ;POPFQ` (флаги восстанавливаются
теми же → семантика не меняется, `PFPREC` идентичен); отдельно после каждого
`PUSHFQ` — 4× `PUSHFQ;LEA RSP,+8`. Интерлив 6 блоков, 18 прогонов, guest
результаты одинаковы во всех. `data/bench-flag-injection-*`.

| Вариант | Медиана demo CPU | vs base (внутриблочно, геом.) | Доп. событий | Стоимость одного в situ |
|---|---:|---:|---:|---:|
| base | 6.03 s | — | — | — |
| +4×`POPFQ` | 7.45 s | время ×1.31 [1.19, 1.42] | 149 M пар | **≈10–12 нс** |
| +4×`PUSHFQ` | 6.46 s | время ×1.13 [1.03, 1.24] | 2.42 G | **≈0.3 нс** (0.06–0.6) |

Вывод: сохранение/восстановление guest-флагов вокруг inline-доступа к
памяти — **≈9% окна demo** на этом Intel-хосте (≈6% `POPFQ` + ≈3% `PUSHFQ`):
**CONFIRMED** (частота точная, стоимость измерена инъекцией и
микробенчмарком). Эффект слабо зависит от шума хоста, т.к. инъекция даёт
сдвиг в 3–4 раза больше A/A-плацебо. На AMD стоимость `POPFQ` иная — не
измерялась.

**PR #10 по счётчикам** (`JitCounters` + PR #10 патч): `FPU_FLD_32` вызовов
152 409 081 → **0**; TLB-промахов inline-чтения +30 768 (99.98% x87 m32
загрузок на быстром пути); счётчики `PUSHFQ`/`POPFQ`, PUSH/POP, dispatcher —
без изменений (±0.03%); guest-результаты идентичны. Механизм PR #10
**CONFIRMED**; он не затрагивает самую большую статью (флаги).
