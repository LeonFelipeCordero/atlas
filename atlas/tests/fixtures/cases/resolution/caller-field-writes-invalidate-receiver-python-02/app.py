class Service:
 def persist(self):pass
class Holder:
 service:Service
def run(holder:Holder):
 alias=holder
 alias.service=other
 holder.service.persist()