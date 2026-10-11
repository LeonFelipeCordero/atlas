from tools import R
def run(other):
 with other as R: pass
 return R.work()
R.work(2)
