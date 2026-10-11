package recipe

import "fmt"

func Tasting(name string) string {
	servings := Portions(name)
	return fmt.Sprintf("Tasting flight: %s, %d portions", name, servings)
}
