package main
type Service struct{}
func (s *Service) persist() {}
func run(parameter *Service) { var local *Service; parameter.persist(); unknown.persist() }