class Service:
 def persist(self):pass
class Holder:
 service:Service
def run(holder:Holder):
 alias=holder.service
 alias.persist=other
 holder.service.persist()