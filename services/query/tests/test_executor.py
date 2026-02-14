"""Query service tests."""
from __future__ import annotations

import pytest

from services.query.app.executor import CostGuardError, Executor


def test_reject_non_select():
    ex = Executor()
    with pytest.raises(CostGuardError):
        ex.execute("DROP TABLE foo", plan_hash="h")


def test_result_cache_hit():
    ex = Executor()
    ex._con.execute("CREATE TABLE t AS SELECT * FROM range(100) r(x)")
    r1 = ex.execute("SELECT COUNT(*) AS c FROM t", plan_hash="h")
    r2 = ex.execute("SELECT COUNT(*) AS c FROM t", plan_hash="h")
    assert r1.cached is False
    assert r2.cached is True


def test_rls_segregates_cache():
    ex = Executor()
    ex._con.execute("CREATE TABLE t AS SELECT * FROM range(10) r(x)")
    r1 = ex.execute("SELECT COUNT(*) AS c FROM t", plan_hash="h", rls="tenant_a")
    r2 = ex.execute("SELECT COUNT(*) AS c FROM t", plan_hash="h", rls="tenant_b")
    assert r1.cached is False
    assert r2.cached is False
