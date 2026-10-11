from sqlalchemy.ext.compiler import compiles as render
@render(Statement)
def query(element, compiler, **kw):
    return fragment