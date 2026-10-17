"""Token bucket logic with an injectable clock (no sleeps, no database)."""
from budget_kernel.api.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(default=120, model=30, **kw):
    clock = Clock()
    return RateLimiter(default, model, clock=clock, trust_proxy=False, **kw), clock


def test_burst_then_refusal_with_whole_second_retry_after():
    rl, _ = make(default=60)
    assert all(rl.check("a") is None for _ in range(60))
    wait = rl.check("a")
    assert isinstance(wait, int) and wait == 1               # 60/min = one token per second


def test_bucket_recovers_after_the_wait_and_refusals_cost_nothing():
    rl, clock = make(default=60)
    for _ in range(60):
        rl.check("a")
    for _ in range(5):                                       # hammering while limited must not push recovery out
        assert rl.check("a") == 1
    clock.t += 1
    assert rl.check("a") is None and rl.check("a") == 1
    clock.t += 60
    assert all(rl.check("a") is None for _ in range(60))     # fully refilled, capped at the limit (no banking)


def test_keys_do_not_share_a_bucket():
    rl, _ = make(default=2)
    assert rl.check("a") is None and rl.check("a") is None and rl.check("a") is not None
    assert rl.check("b") is None


def test_model_bucket_is_separate_and_smaller():
    rl, _ = make(default=120, model=3)
    assert [rl.check("a", model=True) for _ in range(3)] == [None] * 3
    assert rl.check("a", model=True) is not None
    assert rl.check("a") is None                             # ordinary requests still pass
    # a refused model call is not charged to the default bucket
    rl2, _ = make(default=4, model=1)
    assert rl2.check("a", model=True) is None
    assert all(rl2.check("a", model=True) is not None for _ in range(5))
    assert all(rl2.check("a") is None for _ in range(3)) and rl2.check("a") is not None


def test_retry_after_for_the_slow_model_bucket():
    rl, _ = make(model=30)
    for _ in range(30):
        rl.check("a", model=True)
    assert rl.check("a", model=True) == 2                    # 30/min = one token per 2 s


def test_zero_disables_a_bucket():
    rl, _ = make(default=0)
    assert all(rl.check("a") is None for _ in range(1000)) and len(rl) == 0


def test_idle_buckets_expire_so_rotating_keys_cannot_grow_memory():
    rl, clock = make(default=5)
    for i in range(1000):
        rl.check(f"ip:{i}")
    assert len(rl) == 1000
    clock.t += 61
    rl.check("new")
    assert len(rl) == 1                                      # everything idle refilled and was dropped


def test_hard_cap_bounds_memory_even_inside_the_refill_window():
    rl, _ = make(default=5, max_buckets=100)
    for i in range(10_000):
        rl.check(f"ip:{i}")
    assert len(rl) <= 101
