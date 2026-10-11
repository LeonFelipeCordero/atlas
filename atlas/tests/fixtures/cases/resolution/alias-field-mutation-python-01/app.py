class Service:
 def persist(self):pass
class Holder:
 service:Service
 def run(self):
  alias=self
  alias.service=other
  self.service.persist()