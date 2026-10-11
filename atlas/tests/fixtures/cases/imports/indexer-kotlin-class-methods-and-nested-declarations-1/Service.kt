package demo
interface Runner {
    fun run(): Int
}
class Service : Runner {
    override fun run(): Int {
        return helper()
    }
    fun run(value: Int): Int = value
    companion object {
        fun create(): Service = Service()
    }
    class Nested {
        fun work(): Int = helper()
    }
}
object Singleton {
    fun work(): Int = helper()
}
fun helper(): Int = 1
fun String.extension(): Int = helper()
