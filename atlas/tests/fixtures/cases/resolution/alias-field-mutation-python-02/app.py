class Service:
 def persist(self):pass
class Inner:
 service:Service
class Holder:
 inner:Inner
 def run(self):
  alias=self.inner
  alias.service=other
  self.inner.service.persist()