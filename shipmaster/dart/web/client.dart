import 'dart:html';
import 'dart:convert';

main() {
    for (var log in ['build-log', 'job-log', 'deploy-log']) {

        DivElement log_div = querySelector('#${log}');
        if (log_div == null) continue;

        var ws = new WebSocket("ws://localhost:8080/logs");

        ws.onOpen.first.then((e) {
            ws.sendString(JSON.encode({'path': log_div.dataset['path']}));
        });

        ws.onMessage.listen((event) {
            log_div.appendHtml(event.data + '<br />');
        });
    }
}
