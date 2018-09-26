import inspect
import os
from collections import OrderedDict

from PyQt5.QtCore import Qt, pyqtSignal, QSortFilterProxyModel, QModelIndex, QSysInfo, QSize

from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QDropEvent, QStandardItemModel

from PyQt5.QtWidgets import QGridLayout, QScrollArea, QWidget, QTableWidgetItem, QPushButton, QToolButton, \
    QLabel, QHBoxLayout, QVBoxLayout, QHeaderView, QTableWidget, QListWidget, QListWidgetItem, QComboBox, \
    QCompleter, QStyleOption, QStyle, QAbstractItemView, QSpinBox, QFrame, QDialog, QFormLayout, \
    QRadioButton, QButtonGroup, QSplitter, QLayout

from layout import FlowLayout
from tools import TournamentStageStatus


class WidgetTools:
    @staticmethod
    def find_stylesheet(widget, return_as_dict=False):
        def extract_styles(sheet):
            styles = {}
            if sheet is not None:
                for pair in sheet.split(';'):
                    try:
                        _key, _val = pair.split(':')
                        styles[_key.strip()] = _val.strip()
                    except ValueError:  # invalid pair
                        pass
            return styles

        def extract_selectors(sheet):
            selectors = OrderedDict()
            if sheet is not None:
                sels = sheet.split('}')
                for sel in sels:
                    if sel.__contains__('{'):
                        _key, _val = sel.split('{')
                        selectors[_key.strip()] = _val.strip()
            return selectors

        #widget_style = {}
        selector_style = OrderedDict()
        parent_list = [widget]
        p = widget
        while p.parent() is not None:
            p = p.parent()
            parent_list.append(p)
        parent_list.reverse()
        for p in parent_list:
            p_sels = extract_selectors(p.styleSheet())
            if not p_sels:
                style = extract_styles(p.styleSheet())
                if not selector_style.keys().__contains__('*'):
                    selector_style['*'] = {}
                for key in style:
                    selector_style['*'][key] = style[key]
            else:
                for sel in p_sels:
                    selector_style[sel] = {}
                    sel_style = extract_styles(p_sels[sel])
                    for key in sel_style:
                        selector_style[sel][key] = sel_style[key]
            #p_style = extract_styles(p.styleSheet())
            #for key in p_style:
            #    widget_style[key] = p_style[key]
        if return_as_dict:
            #return widget_style
            return selector_style
        else:
            #return ';'.join(['%s:%s' % (key, widget_style[key]) for key in widget_style])
            sheet = ''
            for selector in selector_style:
                sheet += '%s{%s}' % (selector,
                                     ';'.join(['%s:%s' % (key, selector_style[selector][key])
                                               for key in selector_style[selector]]))
            return sheet

    @staticmethod
    def css_color_to_rgb(css_color):
        if css_color.startswith('rgb('):
            triple = css_color.replace('rgb(', '').replace(')', '')
            r, g, b = [int(t.strip()) for t in triple.split(',')]
            return QColor(r, g, b, 255)
        elif css_color.startswith('rgba('):
            triple = css_color.replace('rgba(', '').replace(')', '')
            r, g, b, a = [int(t.strip()) for t in triple.split(',')]
            return QColor(r, g, b, a)
        else:
            return QColor(css_color)


class TournamentWidget(QWidget):

    def __init__(self, database, parent=None):
        super().__init__(parent=parent)
        self.database = database
        self.db_teams = None
        self.tournament = None
        self.t_teams = None
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.toolbar = QWidget()
        self.toolbar.setLayout(QHBoxLayout())
        self.toolbar.setMinimumHeight(25)
        self.toolbar.setMaximumHeight(25)
        self.nameLabel = QLabel()
        self.nameLabel.setMaximumHeight(25)
        self.main_page_button = QToolButton()
        self.main_page_button.setFixedSize(20, 20)
        self.main_page_button.setIcon(QIcon('icons/arrow_left.png'))
        self.main_page_button.clicked.connect(self.show_main_page)
        self.toolbar.layout().setContentsMargins(5, 0, 0, 0)
        self.toolbar.layout().addWidget(self.main_page_button)
        self.toolbar.layout().addWidget(self.nameLabel)
        self.main_widget = TournamentMainWidget(self)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.main_widget)
        self.widgets = {
            'groups': GroupStageWidget(self),
            'manage_teams': ManageTeamsWidget(self),
            'draw_groups': GroupDrawWidget(self),
            'generate_matches': GenerateMatchesWidget(self)
        }
        for widget_name in self.widgets:
            self.layout.addWidget(self.widgets[widget_name])
        self.widgets['manage_teams'].teams_changed.connect(self.update_tournament_teams)
        self.widgets['draw_groups'].groups_drawn.connect(self.update_tournament_groups)
        self.widgets['generate_matches'].match_generation_requested.connect(self.generate_matches)
        self.widgets['groups'].match_edited.connect(self.update_match)
        self.main_widget.button_clicked.connect(self.show_widget)
        self.show_main_page()

    def show_main_page(self):
        for widget_name in self.widgets:
            self.widgets[widget_name].hide()
        self.main_widget.show()
        self.main_page_button.hide()

    def show_widget(self, widget_name):
        if widget_name in self.widgets:
            self.main_widget.hide()
            self.main_page_button.show()
            self.widgets[widget_name].show()

    def set_tournament(self, tournament, db_teams=None, t_teams=None, groups=None, status=None):
        print(status)
        self.tournament = tournament
        self.setStyleSheet(tournament['stylesheet'])
        self.nameLabel.setText(tournament['name'])
        if db_teams is None:
            db_teams = []
        if t_teams is None:
            t_teams = []
        self.db_teams = db_teams
        self.t_teams = t_teams
        if groups is not None:
            try:
                editable = status['name'] == 'GROUP'
            except KeyError:
                editable = False
            self.widgets['groups'].set_groups(groups, editable=editable)
            self.widgets['draw_groups'].set_groups_and_teams(groups, t_teams)
        self.widgets['manage_teams'].set_teams(t_teams=t_teams, db_teams=db_teams, count=tournament['num_teams'])
        self.widgets['generate_matches'].set_stage(status)
        if status is not None:
            self.main_widget.set_status(status)

    def update_tournament(self):
        db_teams = self.database.get_teams()
        t_teams = self.database.get_tournament_teams(self.tournament['id'])
        groups = self.database.get_tournament_groups(self.tournament['id'])
        status = self.database.get_tournament_status(self.tournament['id'])
        self.set_tournament(self.tournament, db_teams=db_teams,
                            t_teams=t_teams, groups=groups, status=status)

    def update_tournament_teams(self, teams, changed=False):
        if changed:
            self.database.update_tournament_teams(self.tournament['id'], teams)
            self.database.execute_remote_updates()
            self.update_tournament()
        self.show_main_page()

    def update_tournament_groups(self, groups):
        self.database.update_tournament_groups(self.tournament['id'], groups)
        self.database.execute_remote_updates()
        self.update_tournament()
        self.show_main_page()

    def generate_matches(self, data):
        self.database.generate_matches(self.tournament['id'], data)
        self.database.execute_remote_updates()
        self.update_tournament()
        self.show_main_page()

    def update_match(self, match):
        self.database.update_match(match)
        self.database.execute_remote_updates()
        self.update_tournament()


class TournamentMainWidget(QWidget):
    button_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setProperty('bg_img', 'true')
        self.box_layout = QVBoxLayout()
        self.settings_layout = FlowLayout()
        self.stage_layout = FlowLayout()
        self.view_layout = FlowLayout()
        self.settings_buttons = ['tournament_settings']
        self.stage_buttons = ['manage_teams', 'draw_groups', 'generate_matches']
        self.view_buttons = ['groups', 'ko_stage']
        self.buttons = {
            'tournament_settings': {
                'bt': QPushButton('Tournament Settings', self),
                'icon': QIcon('icons/application_edit.png'),
                'enabled': lambda stage, name, status: True
                             },
            'manage_teams': {
                'bt': QPushButton('Manage Teams', self),
                'icon': QIcon('icons/application_side_list.png'),
                'enabled': lambda stage, name, status: stage == 0 and status != TournamentStageStatus.COMPLETE
                # groups not yet drawn
                             },
            'groups': {
                'bt': QPushButton('Groups', self),
                'icon': QIcon('icons/table.png'),
                'enabled': lambda stage, name, status: True
                # always show, empty groups aren't a bad thing :P
                             },
            'draw_groups': {
                'bt': QPushButton('Draw Groups', self),
                'icon': QIcon('icons/text_padding_left.png'),
                'enabled': lambda stage, name, status: stage == 0 and status != TournamentStageStatus.INITIALIZED
                # as soon as teams are complete, until matches are generated
                             },
            'generate_matches': {
                'bt': QPushButton('Generate next Matches', self),
                'icon': QIcon('icons/application_form.png'),
                'enabled': lambda stage, name, status: status == TournamentStageStatus.COMPLETE and name != 'KO_FINAL_1'
                # show if current stage is complete, but not the final stage
                             },
            'ko_stage': {
                'bt': QPushButton('KO-Stage', self),
                'icon': QIcon('icons/sitemap.png'),
                'enabled': lambda stage, name, status: True
                             },
        }
        self.status = None
        self.init_ui()

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)

    def init_ui(self):
        self.box_layout.addLayout(self.settings_layout)
        self.box_layout.addLayout(self.stage_layout)
        self.box_layout.addLayout(self.view_layout)
        # self.box_layout.setSpacing(20)
        # self.box_layout.setContentsMargins(45, 45, 45, 45)
        self.setLayout(self.box_layout)

        def add_button(layout, button):
            # self.buttons[button]['bt'].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.buttons[button]['bt'].setIcon(self.buttons[button]['icon'])
            self.buttons[button]['bt'].setProperty('click_name', button)
            self.buttons[button]['bt'].clicked.connect(self.emit_bt_click)
            self.buttons[button]['bt'].setFixedSize(200, 200)
            layout.addWidget(self.buttons[button]['bt'])

        for bt in self.settings_buttons:
            add_button(self.settings_layout, bt)
        for bt in self.stage_buttons:
            add_button(self.stage_layout, bt)
        for bt in self.view_buttons:
            add_button(self.view_layout, bt)

    def emit_bt_click(self):
        self.button_clicked.emit(self.sender().property('click_name'))

    def set_status(self, status):
        self.status = status
        for button in self.buttons:
            if self.buttons[button]['enabled'](status['current_stage'], status['name'], status['status']):
                self.buttons[button]['bt'].show()
            else:
                self.buttons[button]['bt'].hide()


class ManageTeamsWidget(QWidget):
    teams_changed = pyqtSignal(list, bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.layout = QVBoxLayout()
        self.setProperty('bg_img', 'true')
        self.layout.setContentsMargins(45, 0, 45, 0)
        self.teamTable = TeamSelectorWidget(self)
        self.accept_button = QPushButton('Accept')
        self.accept_button.clicked.connect(self.accepted)
        self.layout.addWidget(self.teamTable)
        self.layout.addWidget(self.accept_button)
        self.setLayout(self.layout)

    def accepted(self):
        if self.teamTable.get_teams() is None:
            self.teams_changed.emit([], False)
        else:
            self.teams_changed.emit(self.teamTable.get_teams(), True)

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)

    def set_teams(self, t_teams, db_teams, count):
        self.teamTable.set_teams(db_teams=db_teams, count=count, t_teams=t_teams)


class TeamSelectorWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setProperty('bg_img', 'true')
        self.t_teams = None
        self.db_teams = None
        sheet = WidgetTools.find_stylesheet(self, return_as_dict=True)
        self.number_color = None
        self.number_font_weight = None
        for selector in sheet.keys():
            if selector == '*':
                if 'color' in sheet[selector].keys():
                    self.number_color = WidgetTools.css_color_to_rgb(sheet[selector]['color'])
                if 'font-weight' in sheet[selector].keys():
                    weight = sheet[selector]['font-weight']
                    if weight == 'bold':
                        self.number_font_weight = 75
                    else:
                        self.number_font_weight = weight

    def set_teams(self, db_teams, count, t_teams=None):
        self.t_teams = t_teams
        self.db_teams = db_teams
        # clear old
        while 0 < self.count():
            self.remove_last_team_item()
        while count > self.count():
            if t_teams is not None and len(t_teams) > self.count():
                self.add_team_item(t_teams[self.count()]['name'])
            else:
                self.add_team_item()
        self.team_selected()

    def get_teams(self):
        teams = []
        db_ids = {}
        for t in self.db_teams:
            db_ids[t['name']] = t['id']
        for i in range(self.count()):
            name = self.itemWidget(self.item(i)).currentText().strip()
            if name in db_ids:
                teams.append({'name': name, 'id': db_ids[name]})
            elif name != '':
                teams.append({'name': name})
        if self.t_teams == teams:
            return None  # nothing has changed
        return teams

    def remove_last_team_item(self):
        self.takeItem(self.count()-1)

    def add_team_item(self, team_name=None):
        item = QListWidgetItem(self)
        team_item = FilteringComboBox(self)
        if team_name is not None:
            team_item.setCurrentText(team_name)
        team_item.currentTextChanged.connect(self.team_selected)
        px = QPixmap(16, 16)
        px.fill(QColor(0, 0, 0, 0))
        painter = QPainter()
        painter.begin(px)
        if self.number_color is not None:
            painter.setPen(self.number_color)
        if self.number_font_weight is not None:
            font = painter.font()
            font.setWeight(self.number_font_weight)
            painter.setFont(font)
        painter.drawText(0, 0, 16, 16, Qt.AlignRight | Qt.AlignVCenter, str(self.count()))
        painter.end()
        item.setIcon(QIcon(px))
        self.addItem(item)
        self.setItemWidget(item, team_item)
        item.setSizeHint(team_item.sizeHint())

    def team_selected(self):
        selections = {}
        for i in range(0, self.count()):
            item = self.itemWidget(self.item(i))

            item.blockSignals(True)
            if item.currentText() in selections.values() and item.currentText() != '':
                selections[item] = item.currentText()+' (2)'
            else:
                selections[item] = item.currentText()
            item.clear()
            item.blockSignals(False)
        for i in range(0, self.count()):
            item = self.itemWidget(self.item(i))
            item.blockSignals(True)
            item.addItem('')
            for t in self.db_teams:
                if t['name'] not in selections.values() or selections[item] == t['name']:
                    item.addItem(t['name'])
            item.setCurrentText(selections[item])
            item.blockSignals(False)


class GroupDrawWidget(QWidget):
    groups_drawn = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.v_layout = QVBoxLayout()
        self.setProperty('bg_img', 'true')
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.group_stage_widget = GroupStageWidget(parent=self, enable_drag_drop=True)
        self.team_list_widget = TeamDrawListWidget()
        self.team_list_widget.list_empty_changed.connect(self.list_empty_changed)
        self.layout.addWidget(self.group_stage_widget)
        self.layout.addWidget(self.team_list_widget)
        self.v_layout.addLayout(self.layout)
        self.accept_button = QPushButton('Accept')
        self.accept_button.clicked.connect(self.draw_accepted)
        self.accept_button.setEnabled(False)
        self.v_layout.addWidget(self.accept_button)
        self.setLayout(self.v_layout)
        self.t_teams = {}
        self.g_teams = []
        self.groups = {}

    def draw_accepted(self):
        groups = self.group_stage_widget.get_groups()
        for group in groups:
            teams = group['teams']
            team_ids = [self.t_teams[team] for team in teams]
            group['teams'] = team_ids
            group['id'] = self.groups[group['name']]
        self.groups_drawn.emit(groups)

    def list_empty_changed(self, empty):
        self.accept_button.setEnabled(empty)

    def set_groups_and_teams(self, groups, t_teams):
        self.group_stage_widget.set_groups(groups, teams_only=True)
        self.t_teams = {}
        self.g_teams = []
        self.groups = {}
        for g in groups:
            self.groups[g['name']] = g['id']
            for t in g['teams']:
                self.g_teams.append(t['id'])
        self.team_list_widget.clear()
        for t in t_teams:
            self.t_teams[t['name']] = t['id']
            if t['id'] not in self.g_teams:
                item = QListWidgetItem(t['name'])
                self.team_list_widget.addItem(item)
        if self.team_list_widget.count() == 0:
            self.team_list_widget.list_empty_changed.emit(True)

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)


class GroupStageWidget(QWidget):
    match_edited = pyqtSignal(dict)

    def __init__(self, parent=None, enable_drag_drop=False, show_upcoming_games=False):
        super().__init__(parent=parent)
        self.flow_layout = FlowLayout()
        self.widget = QWidget(self)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.widget)
        self.scroll.setWidgetResizable(True)
        self.widget.setProperty('bg_img', 'true')
        self.widget.setLayout(self.flow_layout)
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)

        if show_upcoming_games:
            self.splitter = QSplitter(self)
            self.layout().addWidget(self.splitter)
            self.splitter.addWidget(self.scroll)
            self.splitter.addWidget(MatchListWidget())
            self.splitter.setSizes([200, 100])
        else:
            self.layout().addWidget(self.scroll)
        self.group_widgets = []
        self.drag_drop_enabled = enable_drag_drop

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)

    def set_groups(self, groups, teams_only=False, editable=True):
        if self.flow_layout.count() != len(groups):
            for i in reversed(range(self.flow_layout.count())):
                self.flow_layout.itemAt(i).widget().setParent(None)
            self.group_widgets.clear()
            for group in groups:
                gw = GroupWidget(parent=self)
                gw.match_edited.connect(self.match_edited)
                if self.drag_drop_enabled:
                    gw.table.setDefaultDropAction(Qt.MoveAction)
                    gw.table.setDragDropMode(QAbstractItemView.DragDrop)
                    gw.table.setDragDropOverwriteMode(False)
                    gw.table.setDropIndicatorShown(False)
                self.group_widgets.append(gw)
                self.flow_layout.addWidget(gw)
        i = 0
        for gw in self.group_widgets:
            gw.set_group(groups[i], teams_only=teams_only, editable=editable)
            i += 1

    def get_groups(self):
        groups = []
        for w in self.group_widgets:
            group = []
            for r in range(w.table.rowCount()):
                item = w.table.item(r, 0)
                if item is not None and item.text() is not '':
                    group.append(item.text())
            groups.append({'name': w.table.model().headerData(0, Qt.Horizontal),
                           'teams': group, 'rounds': w.table.roundSpinBox.value()})
        return groups

    def show(self):
        super().show()
        for gw in self.group_widgets:
            gw.table.recalculate_size()


# todo: implement with retractable match-view
class GroupWidget(QFrame):
    match_edited = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        # self.setProperty('bg_img', 'true')
        self.table = GroupTable(parent=self, )
        self.match_table = MatchTable(parent=self)
        self.match_table.match_edited.connect(self.match_edited)
        self.layout().addWidget(self.table)
        self.layout().addWidget(self.match_table)
        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Sunken)
        # self.match_table.hide()

    def set_group(self, group, teams_only=False, editable=False):
        self.table.set_group(group, teams_only=teams_only)
        self.match_table.set_group(group, editable=editable)


class MatchTable(QTableWidget):
    match_edited = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.verticalHeader().setDefaultSectionSize(20)
        self.horizontalHeader().sectionPressed.disconnect()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().hide()
        self.verticalHeader().sectionPressed.disconnect()
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().hide()
        self.setFocusPolicy(Qt.NoFocus)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setFrameStyle(QFrame.NoFrame)
        self.dialog = None
        self.highlight_color = QColor(193, 8, 38)
        sheet = WidgetTools.find_stylesheet(self, return_as_dict=True)
        if '*[highlighted]' in sheet.keys():
            if 'color' in sheet['*[highlighted]'].keys():
                self.highlight_color = WidgetTools.css_color_to_rgb(sheet['*[highlighted]']['color'])

        self.setProperty('transp_bg', 'true')
        # self.setStyleSheet('background-color: rgba(255,255,255,0)')

        if QSysInfo.productVersion() == '10':
            self.setStyleSheet(
                    "QHeaderView::section{"
                    "border-top:0px solid #D8D8D8;"
                    "border-left:0px solid #D8D8D8;"
                    "border-right:1px solid #D8D8D8;"
                    "border-bottom: 1px solid #D8D8D8;"
                    "background-color:white;"
                    "padding:4px;"
                    "}"
                    "QTableCornerButton::section{"
                    "border-top:0px solid #D8D8D8;"
                    "border-left:0px solid #D8D8D8;"
                    "border-right:1px solid #D8D8D8;"
                    "border-bottom: 1px solid #D8D8D8;"
                    "background-color:white;"
                    "}")

    def set_group(self, group, editable=False):
        matches = group['matches'] if group['matches'] is not None else []
        self.clear()

        self.setColumnCount(7 if editable else 6)
        self.setRowCount(len(matches))
        self.setColumnWidth(0, 140 if editable else 150)
        self.setColumnWidth(1, 10)
        self.setColumnWidth(2, 140 if editable else 150)
        self.setColumnWidth(3, 20)
        self.setColumnWidth(4, 10)
        self.setColumnWidth(5, 20)
        if editable:
            self.setColumnWidth(6, 20)
        row = 0
        for match in matches:
            self.setItem(row, 0, QTableWidgetItem(match['team1']))
            self.item(row, 0).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 1, QTableWidgetItem('-'))
            self.item(row, 1).setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.setItem(row, 2, QTableWidgetItem(match['team2']))
            self.setItem(row, 3, QTableWidgetItem(str(match['team1_score'])
                                                  if str(match['team1_score']) != '' else '-'))

            self.item(row, 3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 4, QTableWidgetItem(':'))

            self.item(row, 4).setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.setItem(row, 5, QTableWidgetItem(str(match['team2_score'])
                                                  if str(match['team2_score']) != '' else '-'))
            if editable:
                button_widget = QWidget()
                btn_edit = QPushButton()
                btn_edit.setIcon(QIcon('icons/pencil.png'))
                btn_edit.setProperty('match', match)
                btn_edit.clicked.connect(self.edit_match)
                button_layout = QHBoxLayout(button_widget)
                button_layout.addWidget(btn_edit)
                button_layout.setAlignment(Qt.AlignCenter)
                button_layout.setContentsMargins(0, 0, 0, 0)
                button_widget.setLayout(button_layout)
                self.setCellWidget(row, 6, button_widget)
            for c in range(0, 6):
                if match['status'] == 1:
                    self.item(row, c).setForeground(self.highlight_color)
                self.item(row, c).setFlags(self.item(row, c).flags() ^ Qt.ItemIsSelectable)
                self.item(row, c).setFlags(self.item(row, c).flags() ^ Qt.ItemIsEditable)
            row += 1

        width = 4
        height = 4
        for column in range(self.model().columnCount()):
            width += self.columnWidth(column)
        for row in range(self.model().rowCount()):
            height += self.rowHeight(row)
        self.setMinimumWidth(width)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def edit_match(self):
        self.dialog = EditMatchDialog(self.sender().property('match'), parent=self)
        self.dialog.match_updated.connect(self.match_edited)
        self.dialog.show()


class GroupTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.team_count = 0
        self.verticalHeader().setDefaultSectionSize(20)
        self.horizontalHeader().sectionPressed.disconnect()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().sectionPressed.disconnect()
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setFocusPolicy(Qt.NoFocus)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setFrameStyle(QFrame.NoFrame)
        self.roundSpinBox = None
        self.total_column_width = 350

    def set_group(self, group, teams_only=False):
        if not teams_only:
            self.setColumnCount(5)
            self.setHorizontalHeaderLabels([group['name'], 'G', 'W', 'L', 'BD'])
            self.setColumnWidth(1, 20)
            self.setColumnWidth(2, 20)
            self.setColumnWidth(3, 20)
            self.setColumnWidth(4, 40)
        else:
            self.roundSpinBox = QSpinBox(self)
            self.roundSpinBox.setMinimum(1)
            self.roundSpinBox.setToolTip('Number of rounds for this group')
            self.setColumnCount(1)
            self.setHorizontalHeaderLabels([group['name']])
        self.setColumnWidth(0, 250)
        self.team_count = group['size']
        self.setRowCount(group['size'])

        row = 0
        for team in group['teams']:
            icon_path = 'icons/%s.png' % team['name']
            # if not os.path.isfile(os.path.abspath(icon_path)):
            #    icon_path = 'icons/trophy.png'
            self.setItem(row, 0, QTableWidgetItem(QIcon(icon_path), team['name']))
            if not teams_only:
                self.setItem(row, 1, QTableWidgetItem(str(team['games'])))
                self.setItem(row, 2, QTableWidgetItem(str(team['won'])))
                self.setItem(row, 3, QTableWidgetItem(str(team['lost'])))
                self.setItem(row, 4, QTableWidgetItem('%r:%r' % (team['score'], team['conceded'])))
            row += 1
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                if self.item(r, c) is None or not teams_only:
                    if self.item(r, c) is None:
                        self.setItem(r, c, QTableWidgetItem())
                    self.item(r, c).setFlags(self.item(r, c).flags() ^ Qt.ItemIsEditable)
                    self.item(r, c).setFlags(self.item(r, c).flags() ^ Qt.ItemIsSelectable)

        self.recalculate_size()

    def recalculate_size(self):
        resizable_width = 0
        for i in range(1, self.model().columnCount()):
            self.resizeColumnToContents(i)
            resizable_width += self.columnWidth(i)

        self.setColumnWidth(0, self.total_column_width-resizable_width)
        width = self.verticalHeader().width() + 4
        height = self.horizontalHeader().height() + 4
        for column in range(self.model().columnCount()):
            width += self.columnWidth(column)
        for row in range(self.model().rowCount()):
            height += self.rowHeight(row)
        self.setMinimumWidth(width)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def switch_item(self, original, new, icon=None, internal_switch=False):
        if internal_switch:
            idx1, idx2 = -1, -1
            for i in range(self.rowCount()):
                if self.item(i, 0) is not None:
                    if self.item(i, 0).text() == original:
                        idx1 = i
                    elif self.item(i, 0).text() == new:
                        idx2 = i
            if idx1 > -1 and idx2 > -1:
                cp_o = QTableWidgetItem(self.item(idx1, 0).icon(), self.item(idx1, 0).text())
                self.setItem(idx1, 0, QTableWidgetItem(self.item(idx2, 0).icon(), self.item(idx2, 0).text()))
                self.setItem(idx2, 0, cp_o)
                return True
        else:
            for i in range(self.rowCount()):
                if self.item(i, 0) is not None and self.item(i, 0).text() == original:
                    self.item(i, 0).setText(new)
                    if icon is not None:
                        self.item(i, 0).setIcon(icon)
                    return True
        return False

    def remove_item_by_text(self, text):
        for i in range(self.team_count):
            if self.item(i, 0) is not None:
                if self.item(i, 0).text() == text:
                    self.setItem(i, 0, QTableWidgetItem())
                    self.item(i, 0).setFlags(self.item(i, 0).flags() ^ Qt.ItemIsEditable)
                    self.item(i, 0).setFlags(self.item(i, 0).flags() ^ Qt.ItemIsSelectable)

    def dropEvent(self, event: QDropEvent):
        model = QStandardItemModel()
        model.dropMimeData(event.mimeData(), Qt.CopyAction, 0, 0, QModelIndex())
        source = event.source()
        index = self.indexAt(event.pos())
        row = index.row()
        if index.isValid() and self.team_count >= row+1:
            target_item = self.item(row, 0)
            if target_item is not None and target_item.text() != '':
                event.ignore()
                # swap manually
                source_data = model.item(0, 0).text()
                source_icon = model.item(0, 0).icon()
                target_data = target_item.text()
                target_icon = target_item.icon()
                if source == self:
                    self.switch_item(target_data, source_data, internal_switch=True)
                else:
                    self.switch_item(target_data, source_data, icon=source_icon)
                    source.switch_item(source_data, target_data, icon=target_icon)
            else:
                if type(source) == GroupTable or type(source) == TeamDrawListWidget:
                    # manually remove item from source
                    source.remove_item_by_text(model.item(0, 0).text())
                else:
                    # remove item from source
                    event.acceptProposedAction()
                # manually add item to target table (self)
                self.setItem(row, 0, QTableWidgetItem(model.item(0, 0).icon(), model.item(0, 0).text()))

        else:
            event.ignore()
        self.clearSelection()
        self.clearFocus()
        source.clearSelection()
        source.clearFocus()


class MatchListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # self.layout = QGridLayout()
        # self.layout.setContentsMargins(0, 0, 0, 0)
        # self.layout.setSpacing(0)
        # self.v_layout = QVBoxLayout()
        # self.widget = QWidget(self)
        # self.scroll = QScrollArea()
        # self.scroll.setWidget(self.widget)
        # self.scroll.setWidgetResizable(True)
        # self.widget.setLayout(self.v_layout)
        # self.setLayout(self.layout)
        # self.setProperty('bg_img', 'true')

        self.addItem(QListWidgetItem())
        self.widget = FieldWidget()
        #self.widget.set_group({'name':'A','size':4,'teams':[]})
        self.item(0).setSizeHint(self.widget.sizeHint())
        #self.item(0).setSizeHint(QSize(100,100))
        self.setItemWidget(self.item(0), self.widget)


class FieldWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.verticalHeader().setDefaultSectionSize(20)
        self.horizontalHeader().sectionPressed.disconnect()
        #self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        #self.verticalHeader().sectionPressed.disconnect()
        #self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        #self.verticalHeader().hide()
        self.setFocusPolicy(Qt.NoFocus)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setColumnCount(6)
        self.setRowCount(1)
        self.setHorizontalHeaderLabels(['Time', '#', 'Group', 'Team1', 'Team2', ''])
        self.init()

    def init(self):
        self.setItem(0, 0, QTableWidgetItem('12:15'))
        self.setItem(0, 1, QTableWidgetItem('1'))
        self.setItem(0, 2, QTableWidgetItem('A'))
        self.setItem(0, 3, QTableWidgetItem('Flunkengötter'))
        self.setItem(0, 4, QTableWidgetItem('Beardy Beer'))
        self.setItem(0, 5, QTableWidgetItem(''))
        self.setColumnWidth(0, 40)
        self.setColumnWidth(1, 15)
        self.setColumnWidth(2, 40)
        self.setColumnWidth(3, 100)
        self.setColumnWidth(4, 100)
        self.setColumnWidth(6, 20)
        self.recalculate_size()

    def recalculate_size(self):

        width = self.verticalHeader().width() + 4
        height = self.horizontalHeader().height() + 4
        for column in range(self.model().columnCount()):
            width += self.columnWidth(column)
        for row in range(self.model().rowCount()):
            height += self.rowHeight(row)
        self.setMinimumWidth(width)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)


class TeamDrawListWidget(QListWidget):
    list_empty_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(False)
        self.setProperty('bg_img', 'true')

    def dropEvent(self, event: QDropEvent):
        model = QStandardItemModel()
        model.dropMimeData(event.mimeData(), Qt.CopyAction, 0, 0, QModelIndex())
        drop_text = model.item(0, 0).text()
        drop_icon = model.item(0, 0).icon()
        if drop_text == '':
            event.ignore()
        else:
            source = event.source()
            if type(source) == GroupTable:
                self.addItem(QListWidgetItem(drop_icon, drop_text))
                source.remove_item_by_text(drop_text)
                self.list_empty_changed.emit(False)
            self.clearSelection()
            self.clearFocus()
            source.clearSelection()
            source.clearFocus()

    def remove_item_by_text(self, text):
        item_to_remove = None
        for i in range(self.count()):
            if self.item(i) is not None:
                if self.item(i).text() == text:
                    item_to_remove = i
        if item_to_remove is not None:
            self.takeItem(item_to_remove)
        if self.count() == 0:
            self.list_empty_changed.emit(True)

    def switch_item(self, original, new, icon=None):
        for i in range(self.count()):
            if self.item(i) is not None and self.item(i).text() == original:
                self.item(i).setText(new)
                if icon is not None:
                    self.item(i).setIcon(icon)
                return True
        return False


class GenerateMatchesWidget(QWidget):
    match_generation_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setProperty('bg_img', 'true')
        self.stage = None
        self.generate_button = QPushButton('Generate', parent=self)
        self.generate_button.clicked.connect(self.generate)

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)

    def set_stage(self, stage):
        self.stage = stage

    def generate(self):
        self.match_generation_requested.emit(self.stage)


class EditMatchDialog(QDialog):
    match_updated = pyqtSignal(dict)

    def __init__(self, match, parent=None):
        super(EditMatchDialog, self).__init__(parent)
        self.setProperty('bg_img', 'true')
        self.match = match
        self.setGeometry(self.geometry().x(), self.geometry().y(), 400, 150)
        self.setWindowTitle('Edit Match')
        self.setWindowIcon(QIcon('icons/pencil.png'))
        self.setWindowModality(Qt.ApplicationModal)
        self.layout = QFormLayout(self)
        self.t1_spin = QSpinBox(self)
        self.t1_spin.setMinimum(0)
        if str(match['team1_score']) != '':
            self.t1_spin.setValue(int(match['team1_score']))
        self.t2_spin = QSpinBox(self)
        self.t2_spin.setMinimum(0)
        if str(match['team2_score']) != '':
            self.t2_spin.setValue(int(match['team2_score']))
        self.radio_scheduled = QRadioButton('Scheduled', self)
        self.radio_in_progress = QRadioButton('In Progress', self)
        self.radio_finished = QRadioButton('Finished', self)
        self.radios = [self.radio_scheduled, self.radio_in_progress, self.radio_finished]
        self.status_group = QButtonGroup()
        self.status_widget = QWidget(self)
        self.status_widget.setLayout(QVBoxLayout())
        self.status_widget.setProperty('transp_bg', 'true')
        for i in range(3):
            self.status_group.addButton(self.radios[i])
            self.radios[i].setProperty('status', i)
            self.status_widget.layout().addWidget(self.radios[i])
        self.radios[match['status'] + 1 if match['status'] != 2 else match['status']].setChecked(True)
        self.accept_button = QPushButton('Accept')
        self.accept_button.clicked.connect(self.match_accepted)
        self.layout.addRow(match['team1'], self.t1_spin)
        self.layout.addRow(match['team2'], self.t2_spin)
        self.layout.addRow('Status:', self.status_widget)
        self.layout.addRow('', self.accept_button)
        self.setLayout(self.layout)

    def match_accepted(self):
        score1 = self.t1_spin.value()
        score2 = self.t2_spin.value()
        status = self.status_group.checkedButton().property('status')

        if status == 2 and \
                not (0 == score1 < score2 or 0 == score2 < score1):
            print('MATCH INVALID!!!!')
        else:
            if status == 0:
                self.match['team1_score'] = None
                self.match['team2_score'] = None
            else:
                self.match['team1_score'] = score1
                self.match['team2_score'] = score2
            self.match['status'] = status
            self.match_updated.emit(self.match)
            self.accept()


# todo: implement match view next to group-stage-widget
class AllTimeTableWidget(GroupStageWidget):
    def __init__(self, database, parent=None):
        super().__init__(parent, False)
        self.database = database

    def update_table(self):
        all_time_table = self.database.get_all_time_table()
        self.set_groups(all_time_table, editable=False)

#  ----------------------------------------------------------------------------
#
#  FilteringComboBox class taken from http://www.gulon.co.uk/2013/05/07/a-filtering-qcombobox/
#
#  "THE BEER-WARE LICENSE" (Revision 42):
#  Rob Kent from http://www.gulon.co.uk wrote this class.  As long as you retain this notice you
#  can do whatever you want with this stuff. If we meet some day, and you think
#  this stuff is worth it, you can buy me a beer in return.
#  ----------------------------------------------------------------------------


class FilteringComboBox(QComboBox):
    def __init__(self, parent=None, *args):
        QComboBox.__init__(self, parent, *args)
        self.setEditable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setSourceModel(self.model())

        self._completer = QCompleter(self._proxy, self)
        self._completer.activated.connect(self.on_completer_activated)
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._completer.popup().setStyleSheet(WidgetTools.find_stylesheet(self))
        self.setCompleter(self._completer)

        self.lineEdit().textEdited.connect(self._proxy.setFilterFixedString)

    def on_completer_activated(self, text):
        if not text: return
        self.setCurrentIndex(self.findText(text))
        self.activated[str].emit(self.currentText())



