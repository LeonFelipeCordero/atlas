from base import Base as Parent
class Maker(Parent):
 def run(self):
  value = 'class Fake extends Other'
  return value