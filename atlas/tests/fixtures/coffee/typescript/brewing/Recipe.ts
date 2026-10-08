import { Report } from "../reporting/Report.ts";

export class Recipe {
  static portions(name: string): number {
    switch (name) {
      case "espresso": return 2;
      case "filter": return 3;
      default: return 0;
    }
  }

  static preview(name: string): string {
    return Report.render([name]);
  }
}
