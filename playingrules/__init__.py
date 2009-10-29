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
      </menu>
      <menu name="EntryPlayingRulesMenu" action="UpdateEntryPlayingRulesMenu">
      </menu>
    </placeholder>
  </popup>

</ui>
"""

"""
  <menubar name="MenuBar">
    <menu name="ViewMenu" action="View">
      <placeholder name="ViewMenuModePlaceholder">
        <menuitem name="ViewMenuEditPlayingRules" action="EditPlayingRules"/>
      </placeholder>
    </menu>
  </menubar>
"""

playingrules_defaults = [
    { 'desc':'after the 15th', 'expr':"datetime.date.today().day > 15" },
    { 'desc':'not on sundays', 'expr':"datetime.date.today().weekday() == 2" }
]

class PlayingRulesPlugin (rb.Plugin):

    def log(self, message):
        sys.stderr.write(message + "\n")

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
        self.dbcursor.execute('create table if not exists playingrules_joins ( rule_id INTEGER NOT NULL, unit TEXT NOT NULL, unit_id INTEGER NOT NULL, PRIMARY KEY ( rule_id, unit, unit_id ) )')

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

        self.entry_add_rule(rule_id, 'artist', digests.get('artist'))

    def entry_add_rule(self, rule_id, unit, unit_id):
        self.dbcursor.execute('REPLACE INTO playingrules_joins VALUES ( ?, ?, ? )', (rule_id, unit, unit_id))
        self.db.commit()

    def entry_remove_rule(self, rule_id, unit, unit_id):
        self.dbcursor.execute('DELETE FROM playingrules_joins WHERE rule_id = ? AND unit = ? AND unit_id = ?', (rule_id, unit, unit_id))
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

    def create_song_info(self, shell, song_info, is_multiple):
        if is_multiple is False:
            self.update_song_info(song_info)

    def update_song_info(self, song_info):
        if song_info == False:
            raise Exception('Update !')

        selected = self.get_selected_entry()
        digests = self.get_entry_digests(selected)
        current_rules = { 'artist': self.get_rules_for('artist', digests.get('artist')), 'genre': self.get_rules_for('genre', digests.get('genre')) }
        song_info_pane = gtk.Frame(None)
        song_info_box = gtk.VBox()

        rules_store = gtk.ListStore(int, str, str, str, str, 'gboolean')
        for rule in current_rules.get('artist'):
            rules_store.append([ rule['id'], 'artist', rule['desc'], rule['expr'], 'artist', self.eval_rule(rule) ])
        for rule in current_rules.get('genre'):
            rules_store.append([ rule['id'], 'genre', rule['desc'], rule['expr'], 'artist', self.eval_rule(rule) ])
        rules_view = gtk.TreeView(rules_store)

        column_name = gtk.TreeViewColumn(u"Name")
        rules_view.append_column(column_name)
        cell = gtk.CellRendererText()
        column_name.pack_start(cell, True)
        column_name.add_attribute(cell, 'text', 2)

        column_test = gtk.TreeViewColumn(u"Test")
        rules_view.append_column(column_test)
        cell = gtk.CellRendererText()
        column_test.pack_start(cell, True)
        column_test.add_attribute(cell, 'text', 3)

        column_unit = gtk.TreeViewColumn(u"Apply on")
        rules_view.append_column(column_unit)
        cell = gtk.CellRendererText()
        column_unit.pack_start(cell, True)
        column_unit.add_attribute(cell, 'text', 4)

        column_pass = gtk.TreeViewColumn(u"Currently catched")
        rules_view.append_column(column_pass)
        cell = gtk.CellRendererToggle()
        column_pass.pack_start(cell, True)
        column_pass.add_attribute(cell, 'activatable', 5)
        column_pass.add_attribute(cell, 'active', 5)

        rules_view.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        rules_view.connect('button_press_event', self.song_info_popup, selected, rules_store)

        song_info_box.add(rules_view)
        song_info_pane.add(song_info_box)
        song_info.append_page(_("Playing rules"), song_info_pane)

    def song_info_popup_remove_entry_rule(self, widget, event, rule_id, unit, unit_id):
        if event.type != gtk.gdk.BUTTON_RELEASE or event.button != 3: return False
        self.entry_remove_rule(rule_id, unit, unit_id)

    def song_info_popup_new_rule(self, widget, event, parent, entry):
        if event.type != gtk.gdk.BUTTON_RELEASE: return False
        container = None
        while parent is not None:
            if parent.__class__ == gtk.VBox:
                container = parent
                break
            parent = parent.get_parent()
        if container is None: return False
        container.add(self.new_rule_frame(entry))
        container.show_all()

    def song_info_popup(self, widget, event, entry, rules_store):
        if event.button == 3:
            #selected = widget.get_selection_info(event.x,event.y)
            #widget.select_row(selected[0], selected[1])
            treeselection = widget.get_selection()
            (model, iter) = treeselection.get_selected()

            popup_menu = gtk.Menu()
            if iter is not None:
                digests = self.get_entry_digests(entry)
                rule_id = rules_store.get_value(iter, 0)
                unit = rules_store.get_value(iter, 1)

                popup_rule_menuitem = gtk.MenuItem(_('Delete'))
                popup_rule_menuitem.connect('event', self.song_info_popup_remove_entry_rule, rule_id, unit, digests.get(unit))
                popup_menu.append(popup_rule_menuitem)

            popup_rule_menuitem = gtk.MenuItem(_('Create a new rule'))
            popup_rule_menuitem.connect('event', self.song_info_popup_new_rule, widget, entry)
            popup_menu.append(popup_rule_menuitem)

            popup_menu.show_all()
            popup_menu.popup(None, None, None, event.button, event.time)

    def chek_syntax(self, widget, event, button):
        ret = False
        color_ok = gtk.gdk.Color(0,65000,0)
        color_nok = gtk.gdk.Color(65000,0,0)
        color_wait = gtk.gdk.Color(30000,30000,0)

        button.modify_bg(gtk.STATE_NORMAL, color_ok)

        try:
            text = widget.get_buffer()
            text = text.get_text(text.get_start_iter(), text.get_end_iter())
            ret = eval(text)
            if ret:
                button.modify_bg(gtk.STATE_NORMAL, color_ok)
            else:
                button.modify_bg(gtk.STATE_NORMAL, color_wait)
        except:
            button.modify_bg(gtk.STATE_NORMAL, color_nok)

        button.show_all()
        return ret

    def destroy_widget(self, widget, event, to_destroy):
        if event.type != gtk.gdk.BUTTON_RELEASE: return False
        to_destroy.destroy()

    def new_rule_frame(self, entry=None):
        frame = gtk.Frame()
        vbox = gtk.VBox(True, 10)
        hbox = gtk.HButtonBox()
        frame.add(vbox)

        for_this_entry = ''
        if entry is not None:
            for_this_entry = ' ' + _('for this entry')

        label = gtk.Label(_('Create a new rule' + for_this_entry))
        vbox.add(label)

        btn_ok = gtk.Button(_('Save'))
        hbox.add(btn_ok)

        btn_cancel = gtk.Button(_('Undo'))
        btn_cancel.connect('event', self.destroy_widget, frame)
        hbox.add(btn_cancel)

        textview = gtk.TextView(buffer=None)
        textview.set_editable(True)
        textview.add_events(gtk.gdk.KEY_PRESS_MASK)
        textview.connect('key_press_event', self.chek_syntax, btn_ok)
        vbox.add(textview)

        vbox.add(hbox)
        frame.show_all()
        return frame

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
        self.usi_id = shell.connect('notify::current-entry', self.update_song_info, False)

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
        self.log('Playing rules plugin activated')



    def deactivate(self, shell):
        self.dbcursor.close()
        shell.disconnect (self.csi_id)
        del self.action_update_menus
        del self.action_edit_rules
        del self.action_entry_current_rules
        del self.action_group
        del self.activate_id
        del self.ui_id
        del self.rhymthdb
        del self.csi_id
