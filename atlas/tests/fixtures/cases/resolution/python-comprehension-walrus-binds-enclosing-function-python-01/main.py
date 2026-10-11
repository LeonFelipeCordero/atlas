from tools import R
def run(items):
 [(R := item) for item in items]
 return R.work()
R.work(2)