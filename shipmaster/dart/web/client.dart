import 'dart:html';
import 'dart:convert';

main() {
  DivElement build_log = querySelector('#build-log');
  var ws = new WebSocket("ws://localhost:8080/logs");
  ws.onOpen.first.then((e) {
    ws.sendString(JSON.encode({'path': build_log.dataset['path']}));
  });
  ws.onMessage.listen((event) {
    build_log.appendHtml(event.data+'<br />');
  });
}
