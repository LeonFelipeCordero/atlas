import builtins as b
load = getattr(b, '__import__')
load('sqlite3')