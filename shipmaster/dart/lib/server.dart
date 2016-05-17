import 'package:shelf/shelf.dart' as shelf;
import 'package:shelf/shelf_io.dart' as io;
import 'package:shelf_route/shelf_route.dart' as route;
import 'package:shelf_proxy/shelf_proxy.dart';
import 'package:shelf_web_socket/shelf_web_socket.dart';
import 'package:shelf_exception_response/exception_response.dart';

void main() {

  var wshandler = webSocketHandler((webSocket) {
    webSocket.listen((message) {
      webSocket.add("echo $message");
    });
  });

  var proxy = proxyHandler("http://localhost:8000");

  var router = route.router()
      ..('/', proxy)
      ..get('/ws', wshandler);

  var handler = const shelf.Pipeline()
      .addMiddleware(exceptionResponse())
      .addMiddleware(shelf.logRequests())
      .addHandler(router.handler);

  route.printRoutes(router);

  io.serve(handler, 'localhost', 8080).then((server) {
    print('Serving at http://${server.address.host}:${server.port}');
  });

}
