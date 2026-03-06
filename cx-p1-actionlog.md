# Task 1: python -m pytest tests/test_action_log.py -v

- Date: 2026-03-05 23:34:08 +09:00
- Exit code: 1
- Status: **FAIL**

## Output

~~~text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 7 items

tests/test_action_log.py::test_record_basic ERROR                        [ 14%]
tests/test_action_log.py::test_record_full_params ERROR                  [ 28%]
tests/test_action_log.py::test_record_with_external_conn ERROR           [ 42%]
tests/test_action_log.py::test_record_silent_fail ERROR                  [ 57%]
tests/test_action_log.py::test_record_default_params_result ERROR        [ 71%]
tests/test_action_log.py::test_taxonomy_count ERROR                      [ 85%]
tests/test_action_log.py::test_record_created_at_populated ERROR         [100%]

=================================== ERRORS ====================================
_____________________ ERROR at setup of test_record_basic _____________________

    @pytest.fixture(autouse=True)
    def setup_test_db():
        """�� �׽�Ʈ���� ������ DB ����."""
        if _test_db.exists():
            _test_db.unlink()
    
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_action_log.py:22: OperationalError
__________________ ERROR at setup of test_record_full_params __________________

    @pytest.fixture(autouse=True)
    def setup_test_db():
        """�� �׽�Ʈ���� ������ DB ����."""
        if _test_db.exists():
            _test_db.unlink()
    
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_action_log.py:22: OperationalError
______________ ERROR at setup of test_record_with_external_conn _______________

    @pytest.fixture(autouse=True)
    def setup_test_db():
        """�� �׽�Ʈ���� ������ DB ����."""
        if _test_db.exists():
            _test_db.unlink()
    
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_action_log.py:22: OperationalError
__________________ ERROR at setup of test_record_silent_fail __________________

    @pytest.fixture(autouse=True)
    def setup_test_db():
        """�� �׽�Ʈ���� ������ DB ����."""
        if _test_db.exists():
            _test_db.unlink()
    
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_action_log.py:22: OperationalError
_____________ ERROR at setup of test_record_default_params_result _____________

    @pytest.fixture(autouse=True)
    def setup_test_db():
        """�� �׽�Ʈ���� ������ DB ����."""
        if _test_db.exists():
            _test_db.unlink()
    
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_action_log.py:22: OperationalError
____________________ ERROR at setup of test_taxonomy_count ____________________

    @pytest.fixture(autouse=True)
    def setup_test_db():
        """�� �׽�Ʈ���� ������ DB ����."""
        if _test_db.exists():
            _test_db.unlink()
    
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_action_log.py:22: OperationalError
_____________ ERROR at setup of test_record_created_at_populated ______________

    @pytest.fixture(autouse=True)
    def setup_test_db():
        """�� �׽�Ʈ���� ������ DB ����."""
        if _test_db.exists():
            _test_db.unlink()
    
>       conn = sqlite3.connect(str(_test_db))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlite3.OperationalError: unable to open database file

tests\test_action_log.py:22: OperationalError
============================== warnings summary ===============================
..\..\..\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:475
  C:\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:475: PytestCacheWarning: could not create cache path C:\dev\01_projects\06_mcp-memory\.pytest_cache\v\cache\nodeids: [WinError 5] �׼����� �źεǾ����ϴ�: 'C:\\dev\\01_projects\\06_mcp-memory\\.pytest_cache\\v\\cache'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

..\..\..\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:429
  C:\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:429: PytestCacheWarning: could not create cache path C:\dev\01_projects\06_mcp-memory\.pytest_cache\v\cache\lastfailed: [WinError 5] �׼����� �źεǾ����ϴ�: 'C:\\dev\\01_projects\\06_mcp-memory\\.pytest_cache\\v\\cache'
    config.cache.set("cache/lastfailed", self.lastfailed)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/test_action_log.py::test_record_basic - sqlite3.OperationalError:...
ERROR tests/test_action_log.py::test_record_full_params - sqlite3.Operational...
ERROR tests/test_action_log.py::test_record_with_external_conn - sqlite3.Oper...
ERROR tests/test_action_log.py::test_record_silent_fail - sqlite3.Operational...
ERROR tests/test_action_log.py::test_record_default_params_result - sqlite3.O...
ERROR tests/test_action_log.py::test_taxonomy_count - sqlite3.OperationalErro...
ERROR tests/test_action_log.py::test_record_created_at_populated - sqlite3.Op...
======================== 2 warnings, 7 errors in 0.09s ========================
~~~

