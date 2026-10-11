package app
import service.OrderService
class App { @Inject private lateinit var orderService: OrderService; fun run(){ orderService.persist(1) } }