# CX-01 (SPRT 테스트)

- Date: 2026-03-06 00:17:44 +09:00
- Working directory: C:\dev\01_projects\06_mcp-memory
- Step 1 command: python -m pytest tests/test_hybrid.py -v -k sprt
- Step 1 exit code: 1
- Step 1 status: **FAIL**
- SPRT tests found: **True.ToLower()**
- Fallback run executed: **False.ToLower()**
- Final exit code: 1

## Step 1 Output

~~~text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 22 items / 16 deselected / 6 selected

tests/test_hybrid.py::test_sprt_check_non_signal_skipped ERROR           [ 16%]
tests/test_hybrid.py::test_sprt_check_insufficient_obs ERROR             [ 33%]
tests/test_hybrid.py::test_sprt_check_promote_high_scores ERROR          [ 50%]
tests/test_hybrid.py::test_sprt_check_reject_low_scores ERROR            [ 66%]
tests/test_hybrid.py::test_sprt_check_updates_score_history ERROR        [ 83%]
tests/test_hybrid.py::test_sprt_constants ERROR                          [100%]

=================================== ERRORS ====================================
____________ ERROR at setup of test_sprt_check_non_signal_skipped _____________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:90: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_____________ ERROR at setup of test_sprt_check_insufficient_obs ______________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:90: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
____________ ERROR at setup of test_sprt_check_promote_high_scores ____________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:90: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
_____________ ERROR at setup of test_sprt_check_reject_low_scores _____________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:90: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
___________ ERROR at setup of test_sprt_check_updates_score_history ___________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:90: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _create_test_db():
        """\ud14c\uc2a4\ud2b8\uc6a9 DB \uc0dd\uc131 \u2014 nodes + edges + action_log."""
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_hybrid.py:19: OperationalError
____________________ ERROR at setup of test_sprt_constants ____________________

    @pytest.fixture(autouse=True)
    def setup_db():
        if _test_db.exists():
            _test_db.unlink()
>       _create_test_db()

tests\test_hybrid.py:90: 
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
ERROR tests/test_hybrid.py::test_sprt_check_non_signal_skipped - sqlite3.Oper...
ERROR tests/test_hybrid.py::test_sprt_check_insufficient_obs - sqlite3.Operat...
ERROR tests/test_hybrid.py::test_sprt_check_promote_high_scores - sqlite3.Ope...
ERROR tests/test_hybrid.py::test_sprt_check_reject_low_scores - sqlite3.Opera...
ERROR tests/test_hybrid.py::test_sprt_check_updates_score_history - sqlite3.O...
ERROR tests/test_hybrid.py::test_sprt_constants - sqlite3.OperationalError: u...
================ 16 deselected, 2 warnings, 6 errors in 0.11s =================
~~~

