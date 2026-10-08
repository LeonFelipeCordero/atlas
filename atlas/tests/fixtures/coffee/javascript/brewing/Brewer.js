import { stdout } from "node:process";
import { Recipe } from "./Recipe.js";
import { Report } from "../reporting/Report.js";

class Brewing {
  brew(_names) {
    throw new Error("Implement brew");
  }
}

export class Brewer extends Brewing {
  brew(names) {
    if (names.length === 0) return Report.render([]);
    return Report.render(names.filter(name => Recipe.portions(name) > 0));
  }

  retry(attempts) {
    if (attempts <= 0) return 0;
    return 1 + this.retry(attempts - 1);
  }

  score(batches) {
    let result = 0;
    for (const batch of batches) {
      for (const name of batch) {
        const count = Recipe.portions(name);
        if (count > 0 && count <= 3) {
          result += count;
        }
      }
    }
    return result;
  }

  // Deliberately exceed the cyclomatic-complexity limit without deep nesting.
  classify(amount) {
    let category = 0;
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
  ready(water, beans, cups, temperature) {
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
}

export function main() {
  stdout.write(`${new Brewer().brew(["espresso", "filter", "invalid"])}\n`);
}

if (import.meta.main) main();
