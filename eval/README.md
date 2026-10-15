# Evaluation

    python eval/make_dataset.py                       # regenerate eval/datasets/v1 (deterministic, seeded)
    cd backend && uv run python ../eval/runner.py --config offline     # A + gate + kernel, no API keys
    cd backend && uv run python ../eval/runner.py --config B|C         # real models; needs DASHSCOPE_API_KEY, DEEPSEEK_API_KEY

Uses its own schema (`BK_EVAL_SCHEMA`, default `bk_eval`), **wiped at the start of every run** -- do not point it at data you care about.
Results: `eval/results/<date>/`. Interpreting them: `memory/evaluation/RESULTS.md`.
