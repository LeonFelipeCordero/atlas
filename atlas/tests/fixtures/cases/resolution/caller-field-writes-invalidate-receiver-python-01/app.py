class Service:
 def persist(self):pass
class Holder:
 service:Service
def run(holder:Holder):
 holder.service=other
 holder.service.persist()