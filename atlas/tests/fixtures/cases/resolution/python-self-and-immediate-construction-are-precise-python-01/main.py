class Maker:
 def retry(self, n): return self.retry(n-1) if n else 0
 def brew(self): return 1
class Other:
 def brew(self): return 2
Maker().brew()
unknown.brew()
factory().brew()
