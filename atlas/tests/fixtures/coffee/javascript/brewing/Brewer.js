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
}

export function main() {
  stdout.write(`${new Brewer().brew(["espresso", "filter", "invalid"])}\n`);
}

if (import.meta.main) main();
