package intake

class FirstUnrelatedService {
    fun globalPersist(value: Int) {}
    fun globalRecord(value: Int) {}
}

class SecondUnrelatedService {
    fun globalPersist(value: String) {}
    fun globalRecord() {}
}

fun missingImport(value: Int) {
    globalPersist(value)
    globalRecord(1)
}
