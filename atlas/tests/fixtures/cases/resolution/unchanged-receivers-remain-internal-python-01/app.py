class Service:
 def persist(self):pass
class Holder:
 service:Service
def unrelated(holder):
 holder.service=other
def run(holder:Holder):
 holder.service.persist()