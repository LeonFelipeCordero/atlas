import operator as op
lookup = op.attrgetter
extract = lookup
extract('_repository.list')(service)()