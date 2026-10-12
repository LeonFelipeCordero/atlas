package intake

class ScalarService {
    fun persist(value: Int) {}
    fun persist(value: String) {}
}

class GenericPersistence<Int>(private val service: ScalarService) {
    fun persist(value: Int) {
        service.persist(value)
    }
}
