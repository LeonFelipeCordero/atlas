package coffee.brewing;

import coffee.reporting.Report;
import java.util.List;

interface Brewing {
    String brew(List<String> names);
}

public final class Brewer implements Brewing {
    @Override
    public String brew(List<String> names) {
        if (names.isEmpty()) return Report.render(List.of());
        List<String> valid = names.stream()
            .filter(name -> Recipe.portions(name) > 0).toList();
        return Report.render(valid);
    }

    public int retry(int attempts) {
        if (attempts <= 0) return 0;
        return 1 + retry(attempts - 1);
    }

    public int score(List<List<String>> batches) {
        int result = 0;
        for (List<String> batch : batches) {
            for (String name : batch) {
                int count = Recipe.portions(name);
                if (count > 0 && count <= 3) {
                    result += count;
                }
            }
        }
        return result;
    }

    // Deliberately exceed the cyclomatic-complexity limit without deep nesting.
    public int classify(int amount) {
        int category = 0;
        if (amount > 0) category++;
        if (amount > 1) category++;
        if (amount > 2) category++;
        if (amount > 3) category++;
        if (amount > 4) category++;
        if (amount > 5) category++;
        if (amount > 6) category++;
        if (amount > 7) category++;
        return category;
    }

    // Deliberately exceed the decision-nesting limit without loops.
    public boolean ready(int water, int beans, int cups, int temperature) {
        if (water > 0) {
            if (beans > 0) {
                if (cups > 0) {
                    if (temperature > 0) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(new Brewer().brew(List.of("espresso", "filter", "invalid")));
    }
}
