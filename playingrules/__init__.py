#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rb, sys, datetime
import rhythmdb
import gtk.gdk
import sqlite3

ui_str = """
<ui>
  <popup name="BrowserSourceViewPopup">
    <placeholder name="PluginPlaceholder">
      <menu name="PlayingRulesMenu" action="UpdatePlayingRulesMenu">
        <menuitem name="PlayingRulesMenu" action="UpdatePlayingRulesMenu">
        </menuitem>
      </menu>
      <menu name="EntryPlayingRulesMenu" action="UpdateEntryPlayingRulesMenu">
      </menu>
    </placeholder>
  </popup>
</ui>
"""

playingrules_defaults = [
    { 'desc':'after the 15th', 'expr':"datetime.date.today().day > 15" },
    { 'desc':'not on sundays', 'expr':"datetime.date.today().weekday() == 2" }
]

class PlayingRulesPlugin (rb.Plugin):

    def __init__(self):
        rb.Plugin.__init__(self)

    def init_db(self):
        self.db = sqlite3.connect('/tmp/example.db')
        self.db.row_factory = sqlite3.Row
        self.dbcursor = self.db.cursor()

        newdb = False
        try:
            self.dbcursor.execute('SELECT 1 FROM playingrules_rules LIMIT 1')
        except:
            newdb = True

        self.dbcursor.execute("create table if not exists playingrules_rules ( id INTEGER NOT NULL PRIMARY KEY, desc TEXT NOT NULL, expr TEXT NOT NULL, expires INTEGER NULL )")
        self.dbcursor.execute('create table if not exists playingrules_joins ( rule_id INTEGER NOT NULL, unit TEXT NOT NULL, unit_id INTEGER NOT NULL )')

        if newdb:
            id = 1
            for rule in playingrules_defaults:
                self.dbcursor.execute("INSERT INTO playingrules_rules (id, desc, expr, expires) VALUES ( ?, ?, ?, NULL )", ( id, rule.get('desc'), rule.get('expr') ))
                id = id + 1

        self.db.commit()

        self.rules = self.dbcursor.execute('SELECT * FROM playingrules_rules').fetchall()

    def get_rules_for(self, unit, unit_id):
        return self.dbcursor.execute(
                    """
                        SELECT playingrules_rules.*
                          FROM playingrules_joins, playingrules_rules
                         WHERE playingrules_rules.id = playingrules_joins.rule_id
                           AND unit = ?
                           AND unit_id = ?
                    """, ( unit, unit_id )).fetchall()

    def get_entry_digests(self, entry):
        artist_name = self.rhymthdb.entry_get(entry, rhythmdb.PROP_ARTIST)
        artist_key = self.rhymthdb.entry_get(entry, rhythmdb.PROP_ARTIST_SORT_KEY)

        genre_name = self.rhymthdb.entry_get(entry, rhythmdb.PROP_GENRE)
        genre_key = self.rhymthdb.entry_get(entry, rhythmdb.PROP_GENRE_SORT_KEY)

        entry_id = self.rhymthdb.entry_get(entry, rhythmdb.PROP_ENTRY_ID)

        return { 'entry':entry_id, 'artist_name':artist_name, 'artist':artist_key, 'genre_name':genre_name, 'genre':genre_key }

    def get_selected_entry(self):
        source = self.shell.get_property("selected_source")
        entry = rb.Source.get_entry_view(source)
        selected = entry.get_selected_entries()
        return selected[0]

    def update_menu(self, action):
        """
        uim = self.shell.get_ui_manager()
        menu = uim.get_widget('/BrowserSourceViewPopup/PluginPlaceholder/PlayingRulesMenu').get_submenu()

        selected = self.get_selected_entry()
        digests = self.get_entry_digests(selected)
        if digests.get('entry') == self.current_selected: return False

        self.current_selected = digests.get('entry')
        self.current_selected_rules = []

        artist_rules = self.get_rules_for('artist', digests.get('artist'))
        if artist_rules is not None:
            for rule in artist_rules:
                wid = menu.append(gtk.MenuItem(_(rule['desc'])))
                self.current_selected_rules.append(wid)

        genre_rules = self.get_rules_for('genre', digests.get('genre'))
        if genre_rules is not None:
            for rule in genre_rules:
                wid = menu.append(gtk.MenuItem(_(rule['desc'])))
                self.current_selected_rules.append(wid)

        menu.show_all()
        """
        pass

    def apply_rule(self, widget, event, rule_id):
        if event.type != gtk.gdk.BUTTON_RELEASE: return False

        selected = self.get_selected_entry()
        digests = self.get_entry_digests(selected)

        self.dbcursor.execute('INSERT INTO playingrules_joins VALUES ( ?, ?, ? )', (rule_id, 'artist', digests.get('artist')))
        self.db.commit()

    def entry_pass(self, entry):
        digests = self.get_entry_digests(entry)
        rules = self.get_rules_for('artist', digests.get('artist')) + self.get_rules_for('genre', digests.get('genre'))
        if rules is None or len(rules)==0: return True

        for rule in rules:
            try:
                if self.eval_rule(rule):
                    raise Exception('this entry (%s,%s) has been catched by rules %s : %s = %s', ( digests.get('artist_name'), digests.get('genre_name'), rule['id'], rule['expr'], str(command.onecmd(rule['expr']))))
            except:
                return False

        return True

    def eval_rule(self, rule):
        return eval(rule['expr'], { 'datetime':datetime })

    def playing_changed(self, sp, playing):
        if not self.entry_pass(sp.get_playing_entry ()):
            self.shell.props.shell_player.do_next()

    def update_song_info(self):
        selected = self.get_selected_entry()
        digests = self.get_entry_digests(selected)
        current_rules = { 'artist': self.get_rules_for('artist', digests.get('artist')), 'genre': self.get_rules_for('genre', digests.get('genre')) }
        self.song_info_pane = gtk.Frame(None)

        rules_store = gtk.ListStore(str, str, str, 'gboolean')
        for rule in current_rules.get('artist'):
            rules_store.append([rule['desc'], rule['expr'], 'artist', self.eval_rule(rule)])
        for rule in current_rules.get('genre'):
            rules_store.append([rule['desc'], rule['expr'], 'artist', self.eval_rule(rule)])
        rules_view = gtk.TreeView(rules_store)

        column_name = gtk.TreeViewColumn(u"Name")
        rules_view.append_column(column_name)
        cell = gtk.CellRendererText()
        column_name.pack_start(cell, True)
        column_name.add_attribute(cell, 'text', 0)

        column_test = gtk.TreeViewColumn(u"Test")
        rules_view.append_column(column_test)
        cell = gtk.CellRendererText()
        column_test.pack_start(cell, True)
        column_test.add_attribute(cell, 'text', 1)

        column_unit = gtk.TreeViewColumn(u"Apply on")
        rules_view.append_column(column_unit)
        cell = gtk.CellRendererText()
        column_unit.pack_start(cell, True)
        column_unit.add_attribute(cell, 'text', 2)

        column_pass = gtk.TreeViewColumn(u"Currently catched")
        rules_view.append_column(column_pass)
        cell = gtk.CellRendererToggle()
        column_pass.pack_start(cell, True)
        column_pass.add_attribute(cell, 'activatable', 3)
        column_pass.add_attribute(cell, 'active', 3)

        self.song_info_pane.add(rules_view)
        self.song_info.append_page(_("Playing rules"), self.song_info_pane)

    def create_song_info(self, shell, song_info, is_multiple):
        if is_multiple is False:
            self.song_info_pane = None
            self.song_info = song_info
            self.update_song_info()

    def activate(self, shell):
        # Init SQLite
        self.init_db()

        # Keep a self ref on shell db
        self.rhymthdb = shell.props.db
        self.shell = shell

        # Internal refs
        self.rules_inserted = False
        self.current_selected = None
        self.current_selected_rules = []

        # Song info action
        self.csi_id = shell.connect('create_song_info', self.create_song_info)
        self.usi_id = shell.connect('notify::current-entry', self.update_song_info)

        # Playing events
        shell.get_player ().connect ('playing-changed', self.playing_changed)

        # Setting up actions
        self.action_update_menus = gtk.Action('UpdatePlayingRulesMenu', _('Playing rules'), _('Playing rules'), 'rb-edit-playingrules')
        self.action_edit_rules = gtk.Action('EditPlayingRules', _('Playing rules'), _('Edit rules for this entry'), 'rb-edit-playingrules')
        self.action_entry_current_rules = gtk.Action('UpdateEntryPlayingRulesMenu', _('Active playing rules'), _('Active playing rules rules for this entry'), 'rb-edit-playingrules')

        self.activate_id = self.action_update_menus.connect('activate', self.update_menu)

        self.action_group = gtk.ActionGroup('EditPlayingRulesPluginActions')

        self.action_group.add_action(self.action_update_menus)
        self.action_group.add_action(self.action_edit_rules)
        self.action_group.add_action(self.action_entry_current_rules)
        uim = shell.get_ui_manager ()
        uim.insert_action_group(self.action_group)
        self.ui_id = uim.add_ui_from_string(ui_str)

        menu = uim.get_widget('/BrowserSourceViewPopup/PluginPlaceholder/PlayingRulesMenu').get_submenu()
        for rule in self.rules:
            rule_menuitem = gtk.MenuItem(_(rule['desc']))
            rule_menuitem.connect('event', self.apply_rule, rule['id'])
            menu.append(rule_menuitem)
        menu.show_all()

        uim.ensure_update()



    def deactivate(self, shell):
        self.dbcursor.close()
        shell.disconnect (self.csi_id)
        del self.action
        del self.action_group
        del self.activate_id
        del self.ui_id
        del self.rhymthdb
        del self.csi_id
