from __future__ import annotations

import logging

from skytemple.core.abstract_module import AbstractModule
from skytemple.core.item_tree import (
    ItemTree,
    ItemTreeEntryRef,
    ItemTreeEntry,
    RecursionType,
)
from skytemple.core.open_request import OpenRequest
from skytemple.core.rom_project import RomProject, BinaryName
from skytemple.core.string_provider import StringType
from skytemple.core.widget.status_page import StStatusPageData, StStatusPage
from skytemple.module.dungeon.module import DungeonModule
from skytemple_files.common.i18n_util import _
from skytemple_files.common.types.file_types import FileType
from skytemple_files.common.util import MONSTER_MD
from skytemple_files.data.md.protocol import MdProtocol, MdEntryProtocol
from skytemple_files.hardcoded.text_speed import HardcodedTextSpeed

from skytemple_example_plugin.util import REQUEST_OPEN_TYPE
from skytemple_example_plugin.widget.monster_spawns import (
    StExamplePluginMonsterSpawns,
    StExamplePluginMonsterSpawnsData,
)


logger = logging.getLogger(__name__)


# The "main view" of our plugin, or rather it's contents. That shows a big icon, a title and
# a description that describes our plugin.
MAIN_VIEW = StStatusPageData(
    icon_name="skytemple-illust-dungeons",
    # Use the `_` function for translatable strings. Right now custom localization is not supported
    # for plugins, but this may change in the future.
    title=_("Pokémon Spawns"),
    description=_(
        "Use this section to list and edit all spawns of a particular Pokémon."
    ),
)


class ExamplePluginModule(AbstractModule):
    """
    This is the entry-point of your plugin.
    """

    rom_project: RomProject
    # This stores a mapping of all Pokémon IDs and the views to edit them.
    monster_entries: dict[int, ItemTreeEntryRef]
    # The monster database read from the ROM
    md: MdProtocol | None
    # A reference to the DungeonModule.
    dungeon_module: DungeonModule | None
    # The main item tree.
    item_tree: ItemTree | None

    def __init__(self, rom_project: RomProject):
        """
        Your plugin gets passed in the RomProject when it is created.
        This is your primary way to interact with the game and other modules.

        Note that `__init__` is called to create an instance of your module whenever a ROM
        is loaded. If you want to perform one-time initialization when SkyTemple starts
        use the classmethod load.
        """
        self.rom_project = rom_project
        self.monster_entries = {}
        self.md = None
        self.mappa = None

    @classmethod
    def depends_on(cls) -> list[str]:
        """
        This returns a list of modules that your plugin needs. This can be another plugin module
        or one of the built-in modules, which are listed in SkyTemple's setup.py
        (or in the future it's pyproject.toml).

        You can reference these other modules and rely on functionality in them.
        """
        return ["dungeon", "monster"]

    @classmethod
    def sort_order(cls) -> int:
        """
        A number that is used to sort all of the items in the main item tree of the SkyTemple UI.

        Experiment with this until you find a value you are happy with.
        """
        return 0

    def load_tree_items(self, item_tree: ItemTree):
        """
        This is the heart of your plugin (if your plugin's purpose is to show views in the UI.
        You can add new views to the main item tree on the left of SkyTemple's UI here.

        You must implement this, but you can also do just nothing,
        if your UI does not actually provide new views.

        You can also manipulate other items in the item tree, but this is not recommended, since
        it could easily break with updates.
        """

        # We return two kinds of things.
        # - The "root node" of our plugin uses `StStatusPage` to show a simple page with a big
        #   icon and text that explains the section to the user.
        # - All of its child nodes are an entry to edit the spawns for each Pokémon in.
        logger.info("Loading example plugin view.")

        # Root Node
        root = item_tree.add_entry(
            None,
            ItemTreeEntry(
                # The icon to show in the item tree.
                icon="skytemple-e-position-symbolic",
                # The name to display in the item tree. We use the same name we also use as title
                # in the view.
                name=MAIN_VIEW.title,
                module=self,
                # The view to display. This must be a subclass of `Gtk.Widget` that takes two parameters,
                # `module` and `item_data`.
                # `StStatusPage` displays the simple page with icon, title and description.
                view_class=StStatusPage,
                # `item_data` is the parameter passed to the widget for your view.
                # `StStatusPage` requires `StStatusPageData`.
                item_data=MAIN_VIEW,
            ),
        )

        # `open_file_in_rom` is the main way to load files from the game.
        # You need to tell it how to read the file, which is one of the constants
        # of `FileType`. In this case we want to open the monster database, which has the
        # MD type. Some files have constants that point to their path, such as the `MONSTER_MD`
        # constant, which is the same as writing "BALANCE/monster.md".
        #
        # The second parameter can actually not just be a `FileType`, it can be any class
        # that implements `skytemple_files.common.types.data_handler.DataHandler`. This means
        # you can also use this to implement your own file handling.
        # Any `kwarg`s passed into `open_file_in_rom` will be passed to the methods in your data handler.
        self.md = self.rom_project.open_file_in_rom(MONSTER_MD, FileType.MD)
        # Since we are depending on the `monster` module, we could also have used its
        # reference to the MD file. However in general try to keep coupling between the
        # modules to a minimum, since modules could change their internals with every update
        # and don't really have a stable API in most cases.
        #
        # >>> self.md = self.rom_project.get_module("monster").monster_md
        #
        # However it's probably still always a good idea to see what is already implemented in
        # existing modules.

        # For everything related to the dungeons, we directly use the `dungeon` module instead of
        # re-inventing the wheel. Be careful and take note of the warning above in your own plugin.
        self.dungeon_module = self.rom_project.get_module("dungeon")

        # We now iterate through all Pokémon in the monster database. We only care about
        # base forms. To do that we go through all entries and only take the first
        # form for a "base ID".
        # Note: This will not work properly like this with the "ExpandPokeList" patch applied.
        # See the "monster" module for how to make this work with that patch.
        monster_entries_by_base_id: dict[int, MdEntryProtocol] = {}
        for entry in self.md.entries:
            if entry.md_index_base not in monster_entries_by_base_id:
                monster_entries_by_base_id[entry.md_index_base] = entry

        # Now we go through all of them:
        for entry in monster_entries_by_base_id.values():
            # The "String Provider" can give you strings from the game for common things,
            # such as Pokémon names.
            name = self.rom_project.get_string_provider().get_value(
                StringType.POKEMON_NAMES, entry.md_index_base
            )

            # And now we create an entry for this Pokémon.
            tree_entry = item_tree.add_entry(
                root,
                ItemTreeEntry(
                    icon="skytemple-e-monster-symbolic",
                    name=name,
                    module=self,
                    # This is our custom widget for editing the spawn values.
                    view_class=StExamplePluginMonsterSpawns,
                    # Our custom plugin widget wants `StExamplePluginMonsterSpawnData`.
                    item_data=StExamplePluginMonsterSpawnsData(entry=entry),
                ),
            )
            # We remember this tree entry for future reference
            self.monster_entries[entry.md_index_base] = tree_entry

        # We remember a reference to the item tree. We need this later to mark
        # an entry as modified.
        self.item_tree = item_tree

        # Some more demonstrations of features.
        # The ROM module gives access to the "static data" of the ROM. This includes some metadata
        # and pmdsky-debug symbols.
        rom_module = self.rom_project.get_rom_module()
        static_data = rom_module.get_static_data()
        logger.debug(f"ROM region: {static_data.game_region}")
        logger.debug(
            f"Start of actor list in arm9: 0x{static_data.bin_sections.arm9.data.ACTOR_LIST.address:0x}"
        )
        # get arm9 as binary:
        arm9 = self.rom_project.get_binary(BinaryName.ARM9)
        # Get arm9, do something and save it back to ROM:
        # >>> def modify(arm9: bytearray): ...
        # >>> self.rom_project.modify_binary(BinaryName.ARM9, modify)
        # Get and set hardcoded data:
        val = HardcodedTextSpeed.get_text_speed(arm9, static_data)
        logger.debug(f"Text speed: {val}")
        # >>> self.rom_project.modify_binary(BinaryName.ARM9, lambda bin: HardcodedTextSpeed.set_text_speed(val, bin, static_data))

    def handle_request(self, request: OpenRequest) -> ItemTreeEntryRef | None:
        """
        This allows your plugin to handle a request to open something. Your module or other modules
        can send these requests to SkyTemple and SkyTemple will ask all modules whether they can
        handle the request. If your module can handle a request, return an entry you added to the
        item tree.
        Implementing this is optional.
        """

        # Our example module shows a "back" and "next" button in our Pokémon Spawn views, to
        # jump to another entry. This is a bit of silly, but this way we show off how this
        # works. Below is the implementation that understands that request and returns the
        # reference to the entry.

        logger.debug(f"Got open request: {request.type} -> {request.identifier}")
        if request.type == REQUEST_OPEN_TYPE:
            # request.identifier must in this case contain the number of the monster.
            if request.identifier in self.monster_entries:
                logger.debug(f"Found!")
                return self.monster_entries[request.identifier]

        # Otherwise we can't handle this request.
        return None

    #
    # All methods below are own methods.
    #
    def save(self, md_index_base: int):
        """Save the changes to the mappa file and mark the currently edited entry as modified."""
        assert self.dungeon_module is not None

        # We defer the saving to the dungeon module.
        self.dungeon_module.save_mappa()
        # This will do:
        # >>> self.rom_project.mark_as_modified(MAPPA_PATH)
        # This tells SkyTemple to save the mappa file again when the user saves.
        # Note that we don't need to provide the file type. SkyTemple remembers.
        # It will also do some extra things related to the mappa_g file, not super important here.

        # And we mark the entry as modified.
        if self.item_tree:
            # The second parameter tells SkyTemple to also mark all upper items in the item tree as modified.
            self.item_tree.mark_as_modified(
                self.monster_entries[md_index_base], RecursionType.UP
            )
