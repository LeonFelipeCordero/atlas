package demo
class Service {
    @Deprecated("old")
    private fun run(): Int {
        fun helper(): Int = 1
        val value = helper()
        return value
    }
    companion object Factory {
        fun create(): Service = Service()
    }
}
