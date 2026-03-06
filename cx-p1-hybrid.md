# Task 2: python -m pytest tests/test_hybrid.py -v

- Date: 2026-03-05 23:34:17 +09:00
- Exit code: 1
- Status: **FAIL**

## Output

~~~text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 16 items

tests/test_hybrid.py::test_auto_ucb_c_focus_mode ERROR                   [  6%]
tests/test_hybrid.py::test_auto_ucb_c_dmn_mode ERROR                     [ 12%]
tests/test_hybrid.py::test_auto_ucb_c_long_query_auto ERROR              [ 18%]
tests/test_hybrid.py::test_auto_ucb_c_short_query_auto ERROR             [ 25%]
tests/test_hybrid.py::test_auto_ucb_c_medium_query_auto ERROR            [ 31%]
tests/test_hybrid.py::test_bcm_update_frequency_changes ERROR            [ 37%]
tests/test_hybrid.py::test_bcm_update_theta_m_changes ERROR              [ 43%]
tests/test_hybrid.py::test_bcm_update_visit_count_incremented ERROR      [ 50%]
tests/test_hybrid.py::test_bcm_update_reconsolidation ERROR              [ 56%]
tests/test_hybrid.py::test_bcm_update_empty_ids ERROR                    [ 62%]
tests/test_hybrid.py::test_bcm_update_no_query_skips_reconsolidation ERROR [ 68%]
tests/test_hybrid.py::test_get_graph_cache ERROR                         [ 75%]
tests/test_hybrid.py::test_ucb_traverse_basic ERROR                      [ 81%]
tests/test_hybrid.py::test_ucb_traverse_empty_seeds ERROR                [ 87%]
tests/test_hybrid.py::test_ucb_traverse_dmn_prefers_unvisited ERROR      [ 93%]
tests/test_hybrid.py::test_log_recall_activations ERROR                  [100%]

=================================== ERRORS ====================================
________________ ERROR at setup of test_auto_ucb_c_focus_mode _________________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_________________ ERROR at setup of test_auto_ucb_c_dmn_mode __________________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
______________ ERROR at setup of test_auto_ucb_c_long_query_auto ______________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_____________ ERROR at setup of test_auto_ucb_c_short_query_auto ______________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_____________ ERROR at setup of test_auto_ucb_c_medium_query_auto _____________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_____________ ERROR at setup of test_bcm_update_frequency_changes _____________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
______________ ERROR at setup of test_bcm_update_theta_m_changes ______________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
__________ ERROR at setup of test_bcm_update_visit_count_incremented __________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
______________ ERROR at setup of test_bcm_update_reconsolidation ______________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_________________ ERROR at setup of test_bcm_update_empty_ids _________________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
______ ERROR at setup of test_bcm_update_no_query_skips_reconsolidation _______

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
___________________ ERROR at setup of test_get_graph_cache ____________________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
__________________ ERROR at setup of test_ucb_traverse_basic __________________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_______________ ERROR at setup of test_ucb_traverse_empty_seeds _______________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
__________ ERROR at setup of test_ucb_traverse_dmn_prefers_unvisited __________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
________________ ERROR at setup of test_log_recall_activations ________________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:88: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
============================== warnings summary ===============================
..\..\..\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:475
  C:\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:475: PytestCacheWarning: could not create cache path C:\dev\01_projects\06_mcp-memory\.pytest_cache\v\cache\nodeids: [WinError 5] �׼����� �źεǾ����ϴ�: 'C:\\dev\\01_projects\\06_mcp-memory\\.pytest_cache\\v\\cache'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

..\..\..\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:429
  C:\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:429: PytestCacheWarning: could not create cache path C:\dev\01_projects\06_mcp-memory\.pytest_cache\v\cache\lastfailed: [WinError 5] �׼����� �źεǾ����ϴ�: 'C:\\dev\\01_projects\\06_mcp-memory\\.pytest_cache\\v\\cache'
    config.cache.set("cache/lastfailed", self.lastfailed)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/test_hybrid.py::test_auto_ucb_c_focus_mode - sqlite3.OperationalE...
ERROR tests/test_hybrid.py::test_auto_ucb_c_dmn_mode - sqlite3.OperationalErr...
ERROR tests/test_hybrid.py::test_auto_ucb_c_long_query_auto - sqlite3.Operati...
ERROR tests/test_hybrid.py::test_auto_ucb_c_short_query_auto - sqlite3.Operat...
ERROR tests/test_hybrid.py::test_auto_ucb_c_medium_query_auto - sqlite3.Opera...
ERROR tests/test_hybrid.py::test_bcm_update_frequency_changes - sqlite3.Opera...
ERROR tests/test_hybrid.py::test_bcm_update_theta_m_changes - sqlite3.Operati...
ERROR tests/test_hybrid.py::test_bcm_update_visit_count_incremented - sqlite3...
ERROR tests/test_hybrid.py::test_bcm_update_reconsolidation - sqlite3.Operati...
ERROR tests/test_hybrid.py::test_bcm_update_empty_ids - sqlite3.OperationalEr...
ERROR tests/test_hybrid.py::test_bcm_update_no_query_skips_reconsolidation - ...
ERROR tests/test_hybrid.py::test_get_graph_cache - sqlite3.OperationalError: ...
ERROR tests/test_hybrid.py::test_ucb_traverse_basic - sqlite3.OperationalErro...
ERROR tests/test_hybrid.py::test_ucb_traverse_empty_seeds - sqlite3.Operation...
ERROR tests/test_hybrid.py::test_ucb_traverse_dmn_prefers_unvisited - sqlite3...
ERROR tests/test_hybrid.py::test_log_recall_activations - sqlite3.Operational...
======================= 2 warnings, 16 errors in 0.12s ========================
~~~

