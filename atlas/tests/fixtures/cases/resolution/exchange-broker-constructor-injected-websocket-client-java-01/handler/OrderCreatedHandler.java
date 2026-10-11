package handler;
import service.OrderService;
import client.OrderCreatedWebSocketClient;
class OrderCreatedHandler {
 private final OrderService orderService;
 private final OrderCreatedWebSocketClient orderCreatedWebSocketClient;
 @Inject OrderCreatedHandler(OrderService orderService, OrderCreatedWebSocketClient orderCreatedWebSocketClient) {
  this.orderService = orderService;
  this.orderCreatedWebSocketClient = orderCreatedWebSocketClient;
 }
 void onMessage(Order order, Event event) {
  Order savedOrder = orderService.saveOrder(order);
  orderCreatedWebSocketClient.sendAndWait(event);
 }
}