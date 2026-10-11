package main
type Service struct{}
func(s *Service) persist() {}
func run(local *Service) { if condition { local := other; local.persist() } }