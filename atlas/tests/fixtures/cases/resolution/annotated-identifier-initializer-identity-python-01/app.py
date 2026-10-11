class Service:
 def persist(self):pass
class Other:
 def persist(self):pass
def run():
 other=Other()
 local:Service=other
 local.persist()