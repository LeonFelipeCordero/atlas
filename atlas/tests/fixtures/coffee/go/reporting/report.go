package coffee

import (
	"fmt"
	"strings"
)

func total(names []string) int {
	result := 0
	for _, name := range names {
		result += portions(name)
	}
	return result
}

func render(names []string) string {
	entries := make([]string, 0, len(names))
	for _, name := range names {
		entries = append(entries, fmt.Sprintf("%s=%d", name, portions(name)))
	}
	return fmt.Sprintf("coffee:%s;total=%d", strings.Join(entries, ","), total(names))
}
