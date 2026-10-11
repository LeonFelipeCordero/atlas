class Service:
 def persist(self): pass
class App:
 def __init__(self, injected: Service):
  self.service = injected
 def run(self):
  self.service.persist()