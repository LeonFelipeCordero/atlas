import { Report } from "../reporting/Report.js";

export class Recipe {
  static portions(name) {
    switch (name) {
      case "espresso": return 2;
      case "filter": return 3;
      default: return 0;
    }
  }

  static preview(name) {
    return Report.render([name]);
  }
}
