# Promote Test Report

## Command

```powershell
python -m pytest tests/ -v -k promote 2>&1
```

## Pytest Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 117 items / 116 deselected / 1 selected

tests/test_hybrid.py::test_sprt_check_promote_high_scores ERROR          [100%]

=================================== ERRORS ====================================
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
=========================== short test summary info ===========================
ERROR tests/test_hybrid.py::test_sprt_check_promote_high_scores - sqlite3.Ope...
====================== 116 deselected, 1 error in 1.69s =======================
```

## Fallback Gate Verification

At least one promote test was selected, so fallback source verification was not required.
