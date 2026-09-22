from depgraphs.patches import is_test_path_9_2, parse

DIFF = """\
diff --git a/pkg/a.py b/pkg/a.py
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -1,3 +1,4 @@
 x = 1
-y = 2
+y = 3
+z = 4
diff --git a/pkg/new.py b/pkg/new.py
new file mode 100644
--- /dev/null
+++ b/pkg/new.py
@@ -0,0 +1,2 @@
+def f():
+    return 1
diff --git a/pkg/old.py b/pkg/old.py
deleted file mode 100644
--- a/pkg/old.py
+++ /dev/null
@@ -1 +0,0 @@
-gone = True
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
--- a heading that starts with dashes
+++ a line that starts with pluses
"""


def test_parse_counts():
    fs = {f.path: f for f in parse(DIFF)}
    assert set(fs) == {"pkg/a.py", "pkg/new.py", "pkg/old.py", "README.md"}
    a = fs["pkg/a.py"]
    assert (a.added, a.removed, a.is_new, a.is_deleted) == (2, 1, False, False)
    assert a.added_lines == ["y = 3", "z = 4"]
    n = fs["pkg/new.py"]
    assert (n.added, n.removed, n.is_new) == (2, 0, True)
    o = fs["pkg/old.py"]
    assert (o.added, o.removed, o.is_deleted) == (0, 1, True)


def test_hunk_lines_that_look_like_headers():
    r = {f.path: f for f in parse(DIFF)}["README.md"]
    assert (r.added, r.removed) == (1, 1)


def test_test_path_rule():
    assert is_test_path_9_2("tests/test_x.py")
    assert is_test_path_9_2("pkg/tests/helpers.py")
    assert is_test_path_9_2("pkg/testing/utils.py")
    assert is_test_path_9_2("pkg/test_x.py")
    assert is_test_path_9_2("pkg/x_test.py")
    assert is_test_path_9_2("conftest.py")
    assert not is_test_path_9_2("pkg/testsuite.py")
    assert not is_test_path_9_2("pkg/contest.py")
    assert not is_test_path_9_2("pytest/main.py")


def test_study_test_rule_adds_test_dir():
    from depgraphs.patches import is_test_path
    assert is_test_path("test/fixtures/a.py") and not is_test_path_9_2("test/fixtures/a.py")
    assert is_test_path("tests/x.py") and not is_test_path("pkg/testing_utils.py")
