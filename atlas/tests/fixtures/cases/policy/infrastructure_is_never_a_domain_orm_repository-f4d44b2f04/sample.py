from sqlalchemy.orm import Session as S
s = S(engine)
s.query(Row).all()