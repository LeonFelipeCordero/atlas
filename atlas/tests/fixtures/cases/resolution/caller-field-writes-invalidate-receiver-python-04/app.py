class Service:
 def persist(self):pass
class Holder:
 service:Service
def run(holder:Holder):
 alias:Holder=holder
 holder.service=other
 alias.service.persist()