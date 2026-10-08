import { stdout } from "node:process";
import { Report } from "../reporting/Report.ts";
import { Recipe } from "./Recipe.ts";

interface Brewing {
  brew: (names: Array<string>) => string;
}

export class Brewer implements Brewing {
  brew(names: Array<string>): string {
    if (names.length === 0) return Report.render([]);
    return Report.render(names.filter(name => Recipe.portions(name) > 0));
  }

  retry(attempts: number): number {
    if (attempts <= 0) return 0;
    return 1 + this.retry(attempts - 1);
  }

  score(batches: Array<Array<string>>): number {
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

export function main(): void {
  stdout.write(`${new Brewer().brew(["espresso", "filter", "invalid"])}\n`);
}

if (import.meta.main) main();
