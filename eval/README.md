# Evaluation

    python eval/make_dataset.py                       # regenerate eval/datasets/v1 (deterministic, seeded)
    cd backend && uv run python ../eval/runner.py --config offline     # A + gate + kernel, no API keys
    cd backend && uv run python ../eval/runner.py --config B|C         # real models; B needs DASHSCOPE_API_KEY, C also DEEPSEEK_API_KEY
    BK_DATASET_SEED=20261016 BK_DATASET_VERSION=v2 python eval/make_dataset.py   # a fresh set (v2); run it with BK_DATASET_VERSION=v2

Uses its own schema (`BK_EVAL_SCHEMA`, default `bk_eval`), **wiped at the start of every run** -- do not point it at data you care about.
Results: `eval/results/<date>/`. Interpreting them: `memory/evaluation/RESULTS.md`.
