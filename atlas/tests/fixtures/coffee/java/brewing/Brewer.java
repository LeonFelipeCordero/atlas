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

    public static void main(String[] args) {
        System.out.println(new Brewer().brew(List.of("espresso", "filter", "invalid")));
    }
}
