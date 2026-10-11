package main
type Service struct{}
func(s *Service) persist(){}
type Holder struct{service *Service}
func run(holder *Holder){alias:=holder;alias.service=other;holder.service.persist()}