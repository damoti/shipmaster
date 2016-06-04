import 'dart:html';
import 'dart:convert';

main() {

    var protocol = (window.location.protocol == 'https:') ? 'wss:' : 'ws:';
    var ws = new WebSocket("${protocol}//${window.location.host}/logs");
    ws.onOpen.first.then((e) {
        ws.sendString(JSON.encode({'path': 'foo/bar'}));
    });

    ws.onMessage.listen((event) {
        window.console.log(event.data);
        //window.c(event.data + '<br />');
    });

    /*
    for (var log in ['build-log', 'job-log', 'deploy-log']) {

        DivElement log_div = querySelector('#${log}');
        if (log_div == null) continue;
        if (log_div.dataset.containsKey('finished')) continue;

        var ws = new WebSocket("${protocol}//${window.location.host}/logs");

        ws.onOpen.first.then((e) {
            ws.sendString(JSON.encode({'path': log_div.dataset['path']}));
        });

        ws.onMessage.listen((event) {
            log_div.appendHtml(event.data + '<br />');
        });

    }*/
}
