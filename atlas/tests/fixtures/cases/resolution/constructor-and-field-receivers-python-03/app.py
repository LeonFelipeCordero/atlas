class Service:
 def persist(self): pass
class App:
 service: Service
 def run(self):
  self.service.persist()