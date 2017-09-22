import unittest
from shipmaster.cli import main
from shipmaster.cli.cli import argument_parser


class TestCLI(unittest.TestCase):

    def test_cli(self):
        with self.assertRaises(SystemExit):
            main()

    def test_graph(self):
        parser = argument_parser()
        parser.parse_args(['graph'])
