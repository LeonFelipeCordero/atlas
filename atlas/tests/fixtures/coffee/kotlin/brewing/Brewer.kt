package coffee.brewing

import coffee.reporting.render
import java.lang.StringBuilder

interface CoffeeMaker {
    fun brew(names: List<String>): String
}

class Brewer : CoffeeMaker {
    override fun brew(names: List<String>): String {
        if (names.isEmpty()) return render(emptyList())
        val accepted = names.filter { portions(it) > 0 }
        return render(accepted)
    }

    fun retry(attempts: Int): Int {
        if (attempts <= 0) return 0
        return 1 + retry(attempts - 1)
    }

    fun score(batches: List<List<String>>): Int {
        var total = 0
        for (batch in batches) {
            for (name in batch) {
                val amount = portions(name)
                if (amount > 0 && amount <= 3) total += amount
            }
        }
        return total
    }
}

fun main() {
    val output = StringBuilder(Brewer().brew(listOf("espresso", "filter", "invalid")))
    println(output.toString())
}
