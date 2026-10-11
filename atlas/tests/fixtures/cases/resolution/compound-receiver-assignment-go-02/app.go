package main
type Service struct{}
func(s *Service) persist(){}
func run(local *Service){local++;local.persist()}