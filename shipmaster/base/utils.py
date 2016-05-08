class UnbufferedLineIO(object):
    def __init__(self, stream):
        self.stream = stream

    def write(self, data, newline=True):
        self.stream.write(data)
        if newline:
            self.stream.write('\n')
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)
