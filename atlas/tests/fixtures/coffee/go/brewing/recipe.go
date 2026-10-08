package coffee

// All three files belong to package coffee when built together. The source
// call cycle is preview -> render -> portions, not a package import cycle.
func portions(name string) int {
	switch name {
	case "espresso":
		return 2
	case "filter":
		return 3
	default:
		return 0
	}
}

func preview(name string) string {
	return render([]string{name})
}
