from operator import methodcaller as invoke
invoke('__getattribute__', '_repository')(service)