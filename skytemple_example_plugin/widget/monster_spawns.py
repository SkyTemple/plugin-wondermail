from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, cast

from gi.repository import Gtk, Gdk
from range_typed_integers import u16
from skytemple.core.open_request import OpenRequest, REQUEST_TYPE_DUNGEON_FLOOR
from skytemple.core.string_provider import StringType
from skytemple_files.data.md.protocol import MdEntryProtocol
from skytemple_files.hardcoded.dungeons import DungeonDefinition

from skytemple_example_plugin.util import data_dir, REQUEST_OPEN_TYPE

# this is needed to avoid cyclic imports at runtime.
if TYPE_CHECKING:
    from skytemple_example_plugin.module import ExamplePluginModule


logger = logging.getLogger(__name__)


class StExamplePluginMonsterSpawnsData:
    entry: MdEntryProtocol

    def __init__(self, entry: MdEntryProtocol):
        self.entry = entry


# This is a GTK.Template. See the PyGObject documentation for details:
# https://pygobject.readthedocs.io/en/latest/guide/gtk_template.html
@Gtk.Template(filename=os.path.join(data_dir(), "widget", "monster_spawns.ui"))
class StExamplePluginMonsterSpawns(Gtk.Box):
    """
    The view to edit Pokémon Spawn data.
    """

    __gtype_name__ = "StExamplePluginMonsterSpawns"

    # `module` will always be your module.
    module: ExamplePluginModule
    # The format you expect your widget's data in. This can also just be a scalar.
    item_data: StExamplePluginMonsterSpawnsData

    # You can reference any widgets in your widget's XML file like this.
    # For the name use its ID.
    tree_spawn_list = cast(Gtk.TreeView, Gtk.Template.Child())
    store_spawn_list = cast(Gtk.ListStore, Gtk.Template.Child())
    button_box = cast(Gtk.Box, Gtk.Template.Child())
    button_previous = cast(Gtk.Button, Gtk.Template.Child())
    button_next = cast(Gtk.Button, Gtk.Template.Child())
    cr_normal_weight = cast(Gtk.CellRendererText, Gtk.Template.Child())
    cr_mh_weight = cast(Gtk.CellRendererText, Gtk.Template.Child())

    def __init__(
        self, module: ExamplePluginModule, item_data: StExamplePluginMonsterSpawnsData
    ):
        super().__init__()
        self.module = module
        self.item_data = item_data

        self._fill()

        logger.debug(f"Loaded view for {item_data.entry.md_index_base}")

    # A handler for a signal of that name. This one fire when pressing "Previous".
    @Gtk.Template.Callback()
    def on_button_previous_clicked(self, *args):
        # This tells SkyTemple to ask every module if it can process this request. If any module
        # can, SkyTemple will then switch the view. We implement this kind of open request ourselves,
        # see module.py. But we could use this to switch to other modules as well!
        logger.debug(f"Previous clicked.")
        self.module.rom_project.request_open(
            OpenRequest(REQUEST_OPEN_TYPE, self.item_data.entry.md_index_base - 1),
            # We just silently do nothing if nobody processes it. Setting this to true, we can handle an
            # exception if SkyTemple doesn't find a handler.
            raise_exception=False,
        )

    @Gtk.Template.Callback()
    def on_button_next_clicked(self, *args):
        # See above.
        logger.debug(f"Next clicked.")
        self.module.rom_project.request_open(
            OpenRequest(REQUEST_OPEN_TYPE, self.item_data.entry.md_index_base + 1),
            raise_exception=False,
        )

    # This fires when any row is clicked. On double click we send an OpenRequest to switch to that dungeon floor!
    @Gtk.Template.Callback()
    def on_tree_spawn_list_button_press_event(
        self, tree: Gtk.TreeView, event: Gdk.EventButton
    ):
        # A bit of a hack but we only accept the double click, if it's in the first 150px on the left side of the tree.
        # This is to make sure we don't interfere with the double click on the weight cells to edit them.
        # In your own plugin you can do this better :)
        if event.x >= 150:
            return
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            model, treeiter = tree.get_selection().get_selected()
            if treeiter is not None and model is not None:
                row = model[treeiter]
                logger.debug(
                    f"Double clicked on row for dungeon {row[2]}, floor {row[1]}."
                )
                self.module.rom_project.request_open(
                    OpenRequest(
                        REQUEST_TYPE_DUNGEON_FLOOR,
                        (int(row[2]), int(row[1])),
                    ),
                    raise_exception=False,
                )

    # This one fires when any of the "Normal Weight" cells gets edited. We save the weight.
    @Gtk.Template.Callback()
    def on_cr_normal_weight_edited(self, widget, path, value_raw):
        assert self.module.dungeon_module is not None
        # The value is a string, we need to convert it to an integer first. We just bail if
        # it's not an integer.
        try:
            value = int(value_raw)
        except ValueError:
            return

        row = self.store_spawn_list[path]

        # We now have a new relative weight for this entry. Get the old relative weights and refresh it.
        mappa = self.module.dungeon_module.get_mappa()
        monster_spawns = mappa.floor_lists[row[0]][row[1]].monsters
        self_index_in_monster_list = None
        for i, monster in enumerate(monster_spawns):
            if monster.md_index == self.item_data.entry.md_index_base:
                self_index_in_monster_list = i
                break
        assert self_index_in_monster_list is not None
        relative_weights = self.module.dungeon_module.calculate_relative_weights(
            [x.main_spawn_weight for x in monster_spawns]
        )
        # Set the new relative spawn weight both in the UI and the list.
        row[5] = value
        relative_weights[self_index_in_monster_list] = value
        # And now convert it back into absolute weights.
        absolute_weights = self._recalculate_monster_spawn_rates(relative_weights)
        for monster, weight in zip(monster_spawns, absolute_weights):
            monster.main_spawn_weight = u16(weight)
        # Just to be save we explictly write this back to the floor list.
        mappa.floor_lists[row[0]][row[1]].monsters = monster_spawns
        # And then we tell our module to save the mappa file.
        # Note that we don't need to give it the mappa model. The mappa model we loaded
        # is a global shared object that SkyTemple's file management automatically remembers.
        self.module.save(self.item_data.entry.md_index_base)

    # Same as above but for monster houses.
    @Gtk.Template.Callback()
    def on_cr_mh_weight_edited(self, widget, path, value_raw):
        # See above. This is mostly copy+paste.
        assert self.module.dungeon_module is not None
        try:
            value = int(value_raw)
        except ValueError:
            return
        row = self.store_spawn_list[path]
        mappa = self.module.dungeon_module.get_mappa()
        monster_spawns = mappa.floor_lists[row[0]][row[1]].monsters
        self_index_in_monster_list = None
        for i, monster in enumerate(monster_spawns):
            if monster.md_index == self.item_data.entry.md_index_base:
                self_index_in_monster_list = i
                break
        assert self_index_in_monster_list is not None
        relative_weights = self.module.dungeon_module.calculate_relative_weights(
            [x.monster_house_spawn_weight for x in monster_spawns]
        )
        row[6] = value
        relative_weights[self_index_in_monster_list] = value
        absolute_weights = self._recalculate_monster_spawn_rates(relative_weights)
        for monster, weight in zip(monster_spawns, absolute_weights):
            monster.monster_house_spawn_weight = u16(weight)
        mappa.floor_lists[row[0]][row[1]].monsters = monster_spawns
        self.module.save(self.item_data.entry.md_index_base)

    # This fills the list.
    def _fill(self):
        assert self.module.dungeon_module is not None
        # We get the dungeon floor lists and dungeon list from the module
        floor_lists = self.module.dungeon_module.get_mappa().floor_lists
        dungeons = self.module.dungeon_module.get_dungeon_list()

        # The dungeon list defines what floor list a dungeon uses. We now create a mapping of
        # <floor list id> -> <all dungeons using it> so we can later display the name of the dungeon in the list.
        floor_list_mapping: dict[int, list[tuple[int, DungeonDefinition]]] = {}
        for dungeon_id, dungeon in enumerate(dungeons):
            if dungeon.mappa_index not in floor_list_mapping:
                floor_list_mapping[dungeon.mappa_index] = []
            floor_list_mapping[dungeon.mappa_index].append((dungeon_id, dungeon))

        # Now let's go through each floor list and see what floors have this Pokémon on it.
        for fl_id, fl in enumerate(floor_lists):
            for floor_id, floor in enumerate(fl):
                self_index_in_monster_list = None
                for i, monster in enumerate(floor.monsters):
                    if monster.md_index == self.item_data.entry.md_index_base:
                        # This floor contains a spawn entry for this Pokémon
                        self_index_in_monster_list = i
                        break
                if self_index_in_monster_list is not None:
                    # The game stores the spawn weights in an absolute way. The dungeon module can decode this.
                    # We collect the relative weight for this Pokémon.
                    main_ws = self.module.dungeon_module.calculate_relative_weights(
                        [x.main_spawn_weight for x in floor.monsters]
                    )
                    self_w_main = main_ws[self_index_in_monster_list]
                    mh_ws = self.module.dungeon_module.calculate_relative_weights(
                        [x.monster_house_spawn_weight for x in floor.monsters]
                    )
                    self_w_mh = mh_ws[self_index_in_monster_list]

                    # We now need to get the dungeon ID.
                    d_id = self.get_dungeon_relative_ids(
                        floor_list_mapping, fl_id, floor_id
                    )
                    if d_id is None:
                        continue

                    # We now get the dungeon name via our mapping and the string provider.
                    dungeon_name = (
                        self.module.rom_project.get_string_provider().get_value(
                            StringType.DUNGEON_NAMES_MAIN, d_id
                        )
                    )

                    # We now add an entry to the TreeView.
                    self.store_spawn_list.append(
                        [
                            fl_id,  # Floor List ID
                            floor_id,  # Floor ID in floor list.
                            str(d_id),  # Dungeon ID
                            str(
                                floor_id + 1
                            ),  # Floor ID in dungeon as displayed. The UI starts counting at 1.
                            dungeon_name,  # Dungeon Name
                            self_w_main,  # Our relative main spawn weight
                            self_w_mh,  # Our relative monster house spawn weight
                        ]
                    )

    # This maps the floor group ID and floor group for ID to dungeon ID.
    # Sadly there is no central logic in the dungeon module we can use.
    @staticmethod
    def get_dungeon_relative_ids(
        floor_list_mapping: dict[int, list[tuple[int, DungeonDefinition]]],
        floor_group_id: int,
        floor_id_in_floor_group: int,
    ) -> int | None:
        try:
            possible_dungeons = floor_list_mapping[floor_group_id]
        except KeyError:
            # Some floor lists are not assigned.
            return None
        previously_highest_floor_id = -1
        d_id = None
        for pd_id, possible_dungeon in possible_dungeons:
            # We get the biggest dungeon floor starting index that is still possible
            if (
                floor_id_in_floor_group
                >= possible_dungeon.start_after
                > previously_highest_floor_id
            ):
                d_id = pd_id
        assert d_id is not None
        return d_id

    # This is more or less copied from the dungeon floor editor. Don't worry too much about it.
    # This recalculates the absolute spawn weights.
    @staticmethod
    def _recalculate_monster_spawn_rates(relative_weights: list[int]) -> list[int]:
        sum_of_weights_main = sum(relative_weights)

        output = []
        last_weight_main = 0
        last_weight_main_set_idx = 0
        for i, row in enumerate(relative_weights):
            weight_main = 0
            if row != 0:
                weight_main = last_weight_main + int(
                    10000 * (row / sum_of_weights_main)
                )
                last_weight_main = weight_main
                last_weight_main_set_idx = i
            output.append(weight_main)
        if last_weight_main != 0 and last_weight_main != 10000:
            # We did not sum up to exactly 10000, so the values we entered are not evenly
            # divisible. Find the last non-zero we set and set it to 10000.
            output[last_weight_main_set_idx] = 10000

        return output
