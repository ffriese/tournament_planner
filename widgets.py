import inspect
import os
from PyQt5.QtCore import QSize, Qt, pyqtSignal, QSortFilterProxyModel, QMimeData, QDataStream, QModelIndex, QPoint, \
    QCoreApplication
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QDropEvent, QStandardItemModel, QDragMoveEvent, \
    QDragLeaveEvent, QDragEnterEvent
from PyQt5.QtWidgets import QGridLayout, QScrollArea, QWidget, QTableWidgetItem, QSizePolicy, QPushButton, QToolButton, \
    QLabel, QHBoxLayout, QVBoxLayout, QHeaderView, QTableWidget, QListWidget, QListWidgetItem, QComboBox, \
    QCompleter, QStyleOption, QStyle, QAbstractItemView, QItemDelegate, QSpinBox

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
                        key, value = pair.split(':')
                        styles[key.strip()] = value.strip()
                    except ValueError:  # invalid pair
                        pass
            return styles

        widget_style = {}
        parent_list = [widget]
        p = widget
        while p.parent() is not None:
            p = p.parent()
            parent_list.append(p)
        parent_list.reverse()
        for p in parent_list:
            p_style = extract_styles(p.styleSheet())
            for key in p_style:
                widget_style[key] = p_style[key]
        if return_as_dict:
            return widget_style
        else:
            return ';'.join(['%s:%s' % (key, widget_style[key]) for key in widget_style])

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
        self.main_widget.button_clicked.connect(self.react_to_button)
        self.show_main_page()

    def show_main_page(self):
        for widget_name in self.widgets:
            self.widgets[widget_name].hide()
        self.main_widget.show()
        self.main_page_button.hide()

    def react_to_button(self, widget_name):
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
            self.widgets['groups'].set_groups(groups)
            self.widgets['draw_groups'].set_groups_and_teams(groups, t_teams)
        self.widgets['manage_teams'].set_teams(t_teams=t_teams, db_teams=db_teams, count=tournament['num_teams'])
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
            self.update_tournament()
        self.show_main_page()

    def update_tournament_groups(self, groups):
        self.database.update_tournament_groups(self.tournament['id'], groups)
        self.update_tournament()
        self.show_main_page()


class TournamentMainWidget(QWidget):
    button_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.layout = None
        # todo: maybe make this an ordered dict
        self.buttons = {
            'tournament_settings': {
                'bt': QPushButton('Tournament Settings', self),
                'icon': QIcon('icons/application_edit.png'),
                'enabled': lambda stage, status: stage > -1
                # tournament not completely finished
                             },
            'manage_teams': {
                'bt': QPushButton('Manage Teams', self),
                'icon': QIcon('icons/application_side_list.png'),
                'enabled': lambda stage, status: stage == 0
                # groups not yet drawn
                             },
            'groups': {
                'bt': QPushButton('Groups', self),
                'icon': QIcon('icons/table.png'),
                'enabled': lambda stage, status: True
                # always show, empty groups aren't a bad thing :P
                             },
            'draw_groups': {
                'bt': QPushButton('Draw Groups', self),
                'icon': QIcon('icons/text_padding_left.png'),
                'enabled': lambda stage, status: stage == 0 and status != TournamentStageStatus.INITIALIZED
                # as soon as teams are complete, until matches are generated
                             },
            'generate_matches': {
                'bt': QPushButton('Generate Matches', self),
                'icon': QIcon('icons/application_form.png'),
                'enabled': lambda stage, status: stage == 0 and status == TournamentStageStatus.COMPLETE
                # only after groups are drawn, not after matches are generated
                             },
            'ko_stage': {
                'bt': QPushButton('KO-Stage', self),
                'icon': QIcon('icons/sitemap.png'),
                'enabled': lambda stage, status: True
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
        self.layout = QGridLayout()
        self.layout.setSpacing(45)
        self.layout.setContentsMargins(45, 45, 45, 45)
        self.setLayout(self.layout)
        for button in self.buttons:
            self.buttons[button]['bt'].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.buttons[button]['bt'].setIcon(self.buttons[button]['icon'])
            self.buttons[button]['bt'].setProperty('click_name', button)
            self.buttons[button]['bt'].clicked.connect(self.emit_bt_click)
        # todo: add self.buttons to grid dynamically
        self.layout.addWidget(self.buttons['tournament_settings']['bt'], 0, 0)
        self.layout.addWidget(self.buttons['manage_teams']['bt'], 0, 1)
        self.layout.addWidget(self.buttons['groups']['bt'], 1, 0)
        self.layout.addWidget(self.buttons['draw_groups']['bt'], 1, 1)
        self.layout.addWidget(self.buttons['generate_matches']['bt'], 0, 2)
        self.layout.addWidget(self.buttons['ko_stage']['bt'], 1, 2)

    def emit_bt_click(self):
        self.button_clicked.emit(self.sender().property('click_name'))

    def set_status(self, status):
        self.status = status
        for button in self.buttons:
            if self.buttons[button]['enabled'](status['current_stage'], status['status']):
                self.buttons[button]['bt'].show()
            else:
                self.buttons[button]['bt'].hide()


class ManageTeamsWidget(QWidget):
    teams_changed = pyqtSignal(list, bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.layout = QVBoxLayout()
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
        self.t_teams = None
        self.db_teams = None
        sheet = WidgetTools.find_stylesheet(self, return_as_dict=True)
        self.number_color = None
        self.number_font_weight = None
        if 'color' in sheet.keys():
            self.number_color = WidgetTools.css_color_to_rgb(sheet['color'])
        if 'font-weight' in sheet.keys():
            weight = sheet['font-weight']
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
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.group_stage_widget = GroupStageWidget(parent=self, enable_drag_drop=True)
        self.team_list_widget = TeamDrawListWidget()
        self.team_list_widget.list_empty_changed.connect(self.list_empty_changed)
        self.layout.addWidget(self.group_stage_widget)
        self.layout.addWidget(self.team_list_widget)
        self.v_layout.addLayout(self.layout)
        self.accept_button = QPushButton('Accept')
        self.accept_button.clicked.connect(self.accepted)
        self.accept_button.setEnabled(False)
        self.v_layout.addWidget(self.accept_button)
        self.setLayout(self.v_layout)
        self.t_teams = {}
        self.groups = {}

    def accepted(self):
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
        self.groups = {}
        self.team_list_widget.clear()
        for t in t_teams:
            self.t_teams[t['name']] = t['id']
            item = QListWidgetItem(t['name'])
            self.team_list_widget.addItem(item)
        for g in groups:
            self.groups[g['name']] = g['id']

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)


class GroupStageWidget(QWidget):
    def __init__(self, parent=None, enable_drag_drop=False):
        super().__init__(parent=parent)
        self.flow_layout = FlowLayout()
        self.widget = QWidget(self)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.widget)
        self.scroll.setWidgetResizable(True)
        self.widget.setLayout(self.flow_layout)
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)
        self.layout().addWidget(self.scroll)
        self.group_widgets = []
        self.drag_drop_enabled = enable_drag_drop

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)

    def set_groups(self, groups, teams_only=False):
        for i in reversed(range(self.flow_layout.count())):
            self.flow_layout.itemAt(i).widget().setParent(None)
        self.group_widgets.clear()
        for group in groups:
            tw = GroupWidget(group, parent=self, teams_only=teams_only)
            if self.drag_drop_enabled:
                tw.table.setDefaultDropAction(Qt.MoveAction)
                tw.table.setDragDropMode(QAbstractItemView.DragDrop)
                tw.table.setDragDropOverwriteMode(False)
                tw.table.setDropIndicatorShown(False)
            self.group_widgets.append(tw)
            self.flow_layout.addWidget(tw)

    def get_groups(self):
        groups = []
        for w in self.group_widgets:
            group = []
            for r in range(w.table.rowCount()):
                item = w.table.item(r, 0)
                if item is not None:
                    group.append(item.text())
            groups.append({'name': w.table.model().headerData(0, Qt.Horizontal),
                           'teams': group, 'rounds': w.table.roundSpinBox.value()})
        return groups

    def add_matches(self, matches):
        pass


# todo: implement with retractable match-view
class GroupWidget(QWidget):
    def __init__(self, group, parent=None, teams_only=False):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.teams_only = teams_only
        self.table = GroupTable(group=group, parent=self, teams_only=teams_only)
        self.layout().addWidget(self.table)


class GroupTable(QTableWidget):
    def __init__(self, group, parent=None, teams_only=False):
        super().__init__(parent=parent)
        self.teams_only = teams_only
        self.team_count = group['size']
        self.setRowCount(group['size'])
        self.verticalHeader().setDefaultSectionSize(20)
        self.horizontalHeader().sectionPressed.disconnect()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().sectionPressed.disconnect()
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setFocusPolicy(Qt.NoFocus)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        if not self.teams_only:
            self.setColumnCount(5)
            self.setHorizontalHeaderLabels([group['name'], 'G', 'W', 'L', 'BD'])
            self.setColumnWidth(1, 20)
            self.setColumnWidth(2, 20)
            self.setColumnWidth(3, 20)
            self.setColumnWidth(4, 40)
            size = QSize(250 + 20 + 20 + 20 + 40 + 13, 20 * group['size'] + 22)
            self.setMinimumSize(size)
            self.setMaximumSize(size)
        else:
            self.roundSpinBox = QSpinBox(self)
            self.roundSpinBox.setMinimum(1)
            self.roundSpinBox.setToolTip('Number of rounds for this group')
            self.setColumnCount(1)
            self.setHorizontalHeaderLabels([group['name']])  #
            size = QSize(250 + 13, 20 * group['size'] + 22)
            self.setMinimumSize(size)
            self.setMaximumSize(size)
        self.setColumnWidth(0, 250)
        row = 0
        for team in group['teams']:
            icon_path = 'icons/%s.png' % team['name']
            # if not os.path.isfile(os.path.abspath(icon_path)):
            #    icon_path = 'icons/trophy.png'
            self.setItem(row, 0, QTableWidgetItem(QIcon(icon_path), team['name']))
            if not self.teams_only:
                self.setItem(row, 1, QTableWidgetItem(str(team['games'])))
                self.setItem(row, 2, QTableWidgetItem(str(team['won'])))
                self.setItem(row, 3, QTableWidgetItem(str(team['lost'])))
                self.setItem(row, 4, QTableWidgetItem('%r:%r' % (team['score'], team['conceded'])))
            row += 1
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                if self.item(r, c) is None:
                    self.setItem(r, c, QTableWidgetItem())
                self.item(r, c).setFlags(self.item(r, c).flags() ^ Qt.ItemIsEditable)
                self.item(r, c).setFlags(self.item(r, c).flags() ^ Qt.ItemIsSelectable)

    def switch_item(self, original, new):
        for i in range(self.rowCount()):
            if self.item(i, 0) is not None and self.item(i, 0).text() == original:
                self.item(i, 0).setText(new)
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
                target_data = target_item.text()
                self.switch_item(target_data, source_data)
                source.switch_item(source_data, target_data)
            else:
                if type(source) == GroupTable or type(source) == TeamDrawListWidget:
                    # manually remove item from source
                    source.remove_item_by_text(model.item(0, 0).text())
                else:
                    # remove item from source
                    event.acceptProposedAction()
                # manually add item to target table (self)
                self.setItem(row, 0, QTableWidgetItem(model.item(0, 0).text()))

        else:
            event.ignore()
        self.clearSelection()
        self.clearFocus()
        source.clearSelection()
        source.clearFocus()


class TeamDrawListWidget(QListWidget):
    list_empty_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event: QDropEvent):
        model = QStandardItemModel()
        model.dropMimeData(event.mimeData(), Qt.CopyAction, 0, 0, QModelIndex())
        drop_data = model.item(0, 0).text()
        if drop_data == '':
            event.ignore()
        else:
            source = event.source()
            if type(source) == GroupTable:
                self.addItem(drop_data)
                source.remove_item_by_text(drop_data)
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

    def switch_item(self, original, new):
        for i in range(self.count()):
            if self.item(i) is not None and self.item(i).text() == original:
                self.item(i).setText(new)
                return True
        return False


class GenerateMatchesWidget(QWidget):
    pass


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



