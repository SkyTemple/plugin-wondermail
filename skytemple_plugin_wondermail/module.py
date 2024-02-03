from __future__ import annotations

from skytemple.core.abstract_module import AbstractModule
from skytemple.core.item_tree import (
    ItemTree,
    ItemTreeEntry,
)
from skytemple.core.rom_project import RomProject
from skytemple_files.common.i18n_util import _

from skytemple_plugin_wondermail.widget.wonder_mail import StWonderMailPluginView


class WonderMailPluginModule(AbstractModule):
    rom_project: RomProject

    def __init__(self, rom_project: RomProject):
        self.rom_project = rom_project

    @classmethod
    def depends_on(cls) -> list[str]:
        return []

    @classmethod
    def sort_order(cls) -> int:
        return 0

    def load_tree_items(self, item_tree: ItemTree):
        item_tree.add_entry(
            None,
            ItemTreeEntry(
                icon="skytemple-e-worldmap-symbolic",
                name=_("Wonder Mail S"),
                module=self,
                view_class=StWonderMailPluginView,
                item_data=None,
            ),
        )
