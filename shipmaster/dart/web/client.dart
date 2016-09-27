import 'dart:html';
import 'dart:convert' show HtmlEscape;

main() {
    var sanitizer = const HtmlEscape();
    DivElement log_div = querySelector('#log-output');
    if (!log_div.dataset.containsKey('finished')) {
        Element main = querySelector('main');
        var protocol = (window.location.protocol == 'https:') ? 'wss:' : 'ws:';
        var ws = new WebSocket("${protocol}//${window.location.host}/log/${log_div.dataset['path']}");
        ws.onMessage.listen((event) {
            log_div.appendHtml(sanitizer.convert(event.data).replaceAll("\n", "<br />"));
            main.scrollTop = main.scrollHeight;
        });
    }
}
