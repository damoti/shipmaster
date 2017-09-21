from pathlib import Path
from shipmaster.core.plugins import Plugin
from shipmaster.core.builder import ImageBuilder
from shipmaster.core.script import SCRIPT_PATH


class WaitForPlugin(Plugin):

    name = 'waitfor'

    base_path = Path(__file__).parent
    script_path = Path('wait-for-it', 'wait-for-it.sh')

    def _contribute_archive(self, image_builder):
        if self.name in image_builder.config.plugin_configs:
            image_builder.archive.add_bundled_file(self.base_path, self.script_path)
    after_build_archive = _contribute_archive
    after_run_archive = _contribute_archive
    after_start_archive = _contribute_archive

    def _contribute_command(self, image_builder: ImageBuilder, command: str):
        config = image_builder.config.plugin_configs.get(self.name)
        if config:
            return "{} {} -- {}".format(
                SCRIPT_PATH / self.script_path, config, command
            )
        return command
    contribute_to_run_command = _contribute_command
    contribute_to_start_command = _contribute_command
