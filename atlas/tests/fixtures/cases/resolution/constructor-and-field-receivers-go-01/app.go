package main
type Service struct{}
func(s *Service) persist() {}
type App struct{ service *Service }
func(a *App) run(){ a.service.persist() }