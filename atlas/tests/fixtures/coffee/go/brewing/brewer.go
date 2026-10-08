package coffee

import "fmt"

func brew(names []string) string {
	if len(names) == 0 {
		return render(nil)
	}
	valid := make([]string, 0, len(names))
	accept := func(name string) bool { return portions(name) > 0 }
	for _, name := range names {
		if accept(name) {
			valid = append(valid, name)
		}
	}
	return render(valid)
}

func retry(attempts int) int {
	if attempts <= 0 {
		return 0
	}
	return 1 + retry(attempts-1)
}

func score(batches [][]string) int {
	result := 0
	for _, batch := range batches {
		for _, name := range batch {
			count := portions(name)
			if count > 0 && count <= 3 {
				result += count
			}
		}
	}
	return result
}

// Deliberately exceed the cyclomatic-complexity limit without deep nesting.
func classify(amount int) int {
	category := 0
	if amount > 0 { category++ }
	if amount > 1 { category++ }
	if amount > 2 { category++ }
	if amount > 3 { category++ }
	if amount > 4 { category++ }
	if amount > 5 { category++ }
	if amount > 6 { category++ }
	if amount > 7 { category++ }
	return category
}

// Deliberately exceed the decision-nesting limit without loops.
func ready(water, beans, cups, temperature int) bool {
	if water > 0 {
		if beans > 0 {
			if cups > 0 {
				if temperature > 0 {
					return true
				}
			}
		}
	}
	return false
}

// Main is callable by a runner after colocating these package coffee files.
func Main() {
	fmt.Println(brew([]string{"espresso", "filter", "invalid"}))
}
