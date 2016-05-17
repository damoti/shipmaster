import 'dart:io';
import 'dart:async';
import 'dart:convert';

const int _BLOCK_SIZE = 64 * 1024;
const int _WAIT_INC_MS = 500;
const int _WAIT_MAX_MS = 5 * 60 * 1000;  // timeout after 5 minutes

class TailReader {

  File file;

  final _controller = new StreamController<List<int>>();
  Stream<List<int>> get stream => _controller.stream;

  TailReader(String path) {
    file = new File(path);
  }

  start() async {

    RandomAccessFile raf = await file.open();

    // read everything
    var length = await raf.length();
    await _controller.addStream(raf.read(length).asStream());

    var attempt_count = 0;
    var total_wait_time = 0;
    var wait_ms = _WAIT_INC_MS;

    // now poll the file for appends
    while (true) {

      var bytes = await raf.read(_BLOCK_SIZE);

      if (bytes.length > 0) {
        _controller.add(bytes);
        attempt_count = 0;
        total_wait_time = 0;
        wait_ms = _WAIT_INC_MS;
      }

      if (bytes.length < _BLOCK_SIZE) {
        await new Future.delayed(new Duration(milliseconds: wait_ms));
        total_wait_time += wait_ms;
        attempt_count += 1;
        // increase time after every 5 attempts to read
        if (attempt_count % 5 == 0) {
          wait_ms += _WAIT_INC_MS;
        }
        if (wait_ms >= _WAIT_MAX_MS) {
          break;
        }
      }

    }
  }
}

Stream<String> tail(String path) {
  var reader = new TailReader(path);
  reader.start();
  return reader.stream
      .transform(UTF8.decoder)
      .transform(new LineSplitter());
}

main() {
  tail('/tmp/fakelog').listen((line) {
    print(line);
  });
}