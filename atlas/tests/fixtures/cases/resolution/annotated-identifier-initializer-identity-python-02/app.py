class Service:
 def persist(self):pass
class Other:
 def persist(self):pass
def run():
 other=Service()
 local:Service=other
 local.persist()