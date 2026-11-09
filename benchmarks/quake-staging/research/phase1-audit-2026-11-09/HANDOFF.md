# HANDOFF — как продолжить (Phase 2)

Состояние на 2026-11-09. Документы этой фазы: [audit.md](audit.md),
[evidence.md](evidence.md), [candidates.md](candidates.md),
[experiment-plan.md](experiment-plan.md). Производные данные — `data/`.

## Где что лежит

| Что | Где |
|---|---|
| Тесты, инструменты, инструментирование, микробенчмарк | `kaaburgh/dosbox-staging`, ветка `claude/relaxed-lamport-nquiqb`, каталог `extras/jit-audit/` (README там же) |
| Отчёты и производные данные | `kaaburgh/engineering-lab`, ветка `claude/relaxed-lamport-nquiqb`, этот каталог |
| Существующие PR #1–#10 | не изменялись |

## Исходные ревизии

- Baseline: `kaaburgh/dosbox-staging` `main` = `27b1b7ca719c21ef3444f7ad1cf2d9cd439527cc`.
- PR #7 head `91774d582069d52f4d3bf04952cb6047dbdc073f`, PR #8 head
  `c50d2fa10e024aa4e90f10646e40f9b01d685c58`, PR #9 head
  `112e2b5eb2c9eb53363a1ff635bc7f5a61323954`, PR #10 head
  `7a850532ef5081f72d33060dab197d7ad5baf2ae`.
- PR #10 патч: `engineering-lab/benchmarks/quake-staging/research/fpu-read-study/experimental-inline.patch.b64`
  (decoded SHA-256 `6f0805fdcf658f018453833a89dca1e1891ed013fdd507bb433788d064ae54e6`).

## 1. Окружение сборки (как в этой сессии)

Хост — Ubuntu 24.04 без SDL3; сборка выполнялась в Debian 13 chroot
(GCC 14.2, как в предыдущих отчётах):

```bash
apt-get install -y debootstrap
debootstrap --variant=minbase --include=ca-certificates trixie /opt/trixie http://deb.debian.org/debian
for d in proc sys dev dev/pts; do mount --bind /$d /opt/trixie/$d; done
mount --bind /home/user /opt/trixie/home/user
chroot /opt/trixie apt-get install -y --no-install-recommends cmake ninja-build g++ gcc pkg-config python3 \
  libasound2-dev libfluidsynth-dev libiir-dev libpng-dev libopusfile-dev libspeexdsp-dev libsdl3-dev \
  libsdl3-image-dev libasio-dev zlib1g-dev libgl-dev nasm binutils linux-perf python3-capstone lhasa
ln -sf libiir.so /opt/trixie/usr/lib/x86_64-linux-gnu/libiir_static.a
```

Два SDK-shim (не CPU/JIT) — те же, что в PR #6/#7: заменить в
`src/gui/mapper.cpp` вызов `SDL_SetDefaultTextureScaleMode(...)` и в
`src/midi/fluidsynth.cpp` вызов `fluid_synth_set_portamento_time_mode(...)`
комментариями (скрипт — в workflow PR #6, шаг «Apply historical build
compatibility shims»).

```bash
git -C dosbox-staging worktree add --detach /home/user/work/ds main
# shims ...
chroot /opt/trixie bash -c "cd /home/user/work/ds && cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DUSE_SYSTEM_LIBS=ON -DOPT_MT32EMU=OFF -DOPT_TESTS=OFF \
  -DOPT_DOCUMENTATION=OFF -DIS_PRESET_USED=TRUE && cmake --build build -j4"
```

Ожидаемый SHA-256 baseline: `704f4628…029e` (сборка воспроизводима побайтно
в этом окружении). Варианты: PR #9 — однострочная правка `FPU_FLD_32`;
PR #10 — `base64 -d experimental-inline.patch.b64 | git apply`. Диагностика:
`extras/jit-audit/instrumentation/apply_jit_perf_map.py <checkout>` +
`-DCMAKE_CXX_FLAGS=-DDOSBOX_JIT_PERF_MAP=1`; счётчики —
`apply_jit_counters.py <checkout>` (только для подсчёта, не для времени).

## 2. Quake 1.06

Официальный benchmark ZIP (`github.com/user-attachments/...`) из
облачной сессии недоступен (GitHub-прокси ограничен репозиториями). Тот же
`QUAKE.EXE`/`PAK0.PAK` есть в shareware-дистрибутиве:

```bash
curl -L -o quake106.zip https://ftp.gwdg.de/pub/misc/ftp.idsoftware.com/idstuff/quake/quake106.zip
unzip quake106.zip resource.1 && mkdir ex && (cd ex && lha xq ../resource.1)
sha256sum ex/quake.exe ex/id1/pak0.pak
# 7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb  quake.exe
# 35a9c55e5e5a284a159ad2a62e0e8def23d829561fe2f54eb402dbc0a9a946af  id1/pak0.pak
mkdir -p game/ID1 && cp ex/quake.exe game/QUAKE.EXE && cp ex/cwsdpmi.exe game/CWSDPMI.EXE && cp ex/id1/pak0.pak game/ID1/PAK0.PAK
```

Игровые файлы держать вне репозиториев.

## 3. Воспроизведение ключевых результатов

```bash
# Семантика #PF (normal/dynamic × base/pr9/pr10)
nasm -f bin -o PFPREC.COM extras/jit-audit/tests/pfprec.asm
python3 extras/jit-audit/tools/run_dos_test.py --dosbox build/dosbox --com PFPREC.COM --core dynamic --runtime-cwd <checkout>

# Размер блока
nasm -f bin -o JITSIZE.COM extras/jit-audit/tests/jitsize.asm
DOSBOX_JIT_PERF_MAP=1 DOSBOX_JIT_DUMP=/tmp/js.dump python3 extras/jit-audit/tools/run_dos_test.py --dosbox <map-build> --com JITSIZE.COM --runtime-cwd <checkout>

# Профиль окна demo + атрибуция
python3 extras/jit-audit/tools/profile_quake.py --dosbox <map-build> --game game --runtime-cwd <checkout> --private <new-private-dir> --dump
perf script -i <dir>/perf.data -F tid,time,ip,sym,dso > <dir>/perf.txt
python3 extras/jit-audit/tools/analyze_jit.py --dump <dir>/jit.dump --perf-script <dir>/perf.txt > summary.json
python3 extras/jit-audit/tools/sanitize_summary.py summary.json   # публикуемая версия

# Интерлив-бенчмарк (fixed cycles → детерминированная гостевая работа)
python3 extras/jit-audit/tools/bench_quake.py --variant base=<base> --variant base2=<base> \
  --variant pr9=<pr9> --variant pr10=<pr10> --game game --runtime-cwd <checkout> \
  --cycles 1000000 --blocks 8 --warmups 2 --seed 20261109 --out fixed1m.csv
python3 extras/jit-audit/tools/summarize_bench.py fixed1m.csv

# Точные счётчики событий окна demo (сборка с apply_jit_counters.py)
python3 extras/jit-audit/tools/count_quake.py --dosbox <counters-build> --game game --runtime-cwd <checkout>
```

## 4. Известные ловушки

- **callgrind на DOSBox JIT:** с `--smc-check=none` Valgrind исполняет
  устаревшие трансляции (тестовая программа не выводит результат) —
  непригодно. С `--smc-check=all-non-file` корректно, но Quake не доходит
  до консоли за 6 минут на этом хосте — непрактично (запуск:
  `valgrind --tool=callgrind --instr-atstart=no --smc-check=... dosbox ...`
  с переключением `callgrind_control -i on` по строке «Playing demo»). Для
  частот используйте `apply_jit_counters.py` + `tools/count_quake.py`, для
  стоимости — микробенчмарки и инъекцию (`apply_flag_injection.py`).
- **Счётчики в сгенерированном коде:** не вставлять код внутрь inline slow
  path `dyn_read_word`/`dyn_write_word` — его обходит 8-битный short jump
  (первая версия счётчиков падала с SIGSEGV).
- **perf:** нет hardware PMU в Firecracker VM — только `cpu-clock`;
  сэмплы группируются после микрокодовых инструкций (`PUSHFQ`), сэмпл ≠
  стоимость. Используйте `--clockid monotonic` для сопоставления с дампом.
- **DWARF unwind** восстанавливает только первый JIT-кадр (JIT использует
  RBP как `&cpu_regs`).
- **Шум хоста:** CV 7–10% CPU-времени на одинаковую гостевую работу;
  плацебо до ±6%. Выводы о времени — только на выделенном хосте с A/A.
- **SDL презентация** ≈14% main thread в харнессе; фиксируйте её
  конфигурацию между A и B.
- DOSBox при выходе перезапускает себя с `--wait_pid` (логирование) —
  учитывать при `pgrep`.

## 5. Следующие шаги (порядок)

1. M0 из [experiment-plan.md](experiment-plan.md): выделенный хост, A/A,
   hardware counters, если есть; повторить счётчики на нём.
2. E1 (C1a — x87 m32 fast path с legacy промахом): `pfprec` должен совпасть
   с baseline побайтно; legacy slow path ≈ 31 k вызовов вместо 152 M.
3. E2 (C2 — PUSH/POP inline): сначала guest-тесты стека, затем счётчики
   (`push_helper_calls`/`pop_helper_calls` → ~0), затем время.
4. E3 (C4 — флаги): стоимость `POPFQ` на AMD (микробенчмарк + инъекция),
   распределение по блокам, дифференциальный тест флагов — до реализации.
5. E4 (C3 — dispatcher): прототип «skip MakeCodePage» (67.5% входов — та же
   code page) с тестами SMC/CR3/CS. E5 (C6): `BT`/`SETcc`/`SAHF`/`LAHF` в
   dynamic core — самый дешёвый PR, гейт `tests/bitops.asm`; учесть
   [проверку dosbox-staging#11 и engineering-lab#2](peer-review-dosbox11-lab2.md).
6. Отдельное correctness-изменение: точные #PF для всех x87 memory-форм
   (тест `pfprec` → везде `E=I R=ok`), независимо от производительности.
