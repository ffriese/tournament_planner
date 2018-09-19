import os
from PyQt5.QtCore import QSize, Qt, pyqtSignal, QSortFilterProxyModel
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt5.QtWidgets import QGridLayout, QScrollArea, QWidget, QTableWidgetItem, QSizePolicy, QPushButton, QToolButton, \
    QLabel, QHBoxLayout, QVBoxLayout, QHeaderView, QTableWidget, QListWidget, QListWidgetItem, QComboBox, \
    QCompleter, QStyleOption, QStyle

from layout import FlowLayout
from tools import TournamentStageStatus


class TournamentWidget(QWidget):

    def __init__(self):
        super().__init__()
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
            'groups': GroupStageWidget(),
            'manage_teams': TeamSelectionWidget()
        }
        for widget_name in self.widgets:
            self.layout.addWidget(self.widgets[widget_name])
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
        self.setStyleSheet(tournament['stylesheet'])
        self.nameLabel.setText(tournament['name'])
        if groups is not None:
            self.widgets['groups'].set_groups(groups)
        if db_teams is None:
            db_teams = []
        if t_teams is None:
            t_teams = []
        self.widgets['manage_teams'].set_teams(t_teams=t_teams, db_teams=db_teams, count=tournament['num_teams'])
        if status is not None:
            self.main_widget.set_status(status)


class TournamentMainWidget(QWidget):
    button_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.layout = None
        self.buttons = {
            'tournament_settings': {
                'bt': QPushButton('Tournament Settings', self),
                'icon': QIcon('icons/application_edit.png'),
                'enabled': lambda stage, status: stage > -1  # tournament not completely finished
                             },
            'manage_teams': {
                'bt': QPushButton('Manage Teams', self),
                'icon': QIcon('icons/application_side_list.png'),
                'enabled': lambda stage, status: stage == 0  # groups not yet drawn
                             },
            'groups': {
                'bt': QPushButton('Groups', self),
                'icon': QIcon('icons/table.png'),
                'enabled': lambda stage, status: True  # always show, empty groups aren't a bad thing :P
                             },
            'draw_groups': {
                'bt': QPushButton('Draw Groups', self),
                'icon': QIcon('icons/text_padding_left.png'),
                'enabled': lambda stage, status: stage == 0 and status == TournamentStageStatus.IN_PROGRESS  # obvious
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
        self.layout.addWidget(self.buttons['tournament_settings']['bt'], 0, 0)
        self.layout.addWidget(self.buttons['manage_teams']['bt'], 0, 1)
        self.layout.addWidget(self.buttons['groups']['bt'], 1, 0)
        self.layout.addWidget(self.buttons['draw_groups']['bt'], 1, 1)

    def emit_bt_click(self):
        self.button_clicked.emit(self.sender().property('click_name'))

    def set_status(self, status):
        self.status = status
        for button in self.buttons:
            if self.buttons[button]['enabled'](status['current_stage'], status['status']):
                self.buttons[button]['bt'].show()
            else:
                self.buttons[button]['bt'].hide()


class TeamSelectionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.teamTable = QListWidget(self)

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)

    def set_teams(self, t_teams, db_teams, count):
        print(t_teams)
        print(db_teams)
        # clear old
        while 0 < self.teamTable.count():
            self.teamTable.takeItem(self.teamTable.count()-1)
        while count > self.teamTable.count():
            item = QListWidgetItem(self.teamTable)
            team_item = FilteringComboBox(self)
            # team_item.currentTextChanged.connect(self.team_selected)
            px = QPixmap(16, 16)
            px.fill(QColor(0, 0, 0, 0))
            painter = QPainter()
            painter.begin(px)
            painter.drawText(0, 0, 16, 16, Qt.AlignRight | Qt.AlignVCenter, str(self.teamTable.count()))
            painter.end()
            item.setIcon(QIcon(px))
            self.teamTable.addItem(item)
            self.teamTable.setItemWidget(item, team_item)
            item.setSizeHint(team_item.sizeHint())


class GroupStageWidget(QWidget):
    def __init__(self):
        super().__init__()
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

    def paintEvent(self, q_paint_event):
        opt = QStyleOption()
        opt.initFrom(self.parent())
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget,  opt,  p, self)

    def set_groups(self, groups, teams_only=False):
        for i in reversed(range(self.flow_layout.count())):
            self.flow_layout.itemAt(i).widget().setParent(None)
        for group in groups:
            tw = GroupWidget(group, parent=self, teams_only=teams_only)
            self.flow_layout.addWidget(tw)

    def add_matches(self, matches):
        pass


# todo: implement with retractable match-view
class GroupWidget(QWidget):
    def __init__(self, group, parent=None, teams_only=False):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.teams_only = teams_only
        self.table = QTableWidget()
        self.table.setRowCount(group['size'])
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().sectionPressed.disconnect()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().sectionPressed.disconnect()
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.setFocusPolicy(Qt.NoFocus)
        if not self.teams_only:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels([group['name'], 'G', 'W', 'L', 'BD'])
            self.table.setColumnWidth(1, 20)
            self.table.setColumnWidth(2, 20)
            self.table.setColumnWidth(3, 20)
            self.table.setColumnWidth(4, 40)
            size = QSize(250 + 20 + 20 + 20 + 40 + 13,  20 * group['size'] + 22)
            self.table.setMinimumSize(size)
            self.table.setMaximumSize(size)
        else:
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels([group['name']])#
            size = QSize(250 + 13,  20 * group['size'] + 22)
            self.table.setMinimumSize(size)
            self.table.setMaximumSize(size)
        self.table.setColumnWidth(0, 250)
        self.set_group(group)
        self.layout().addWidget(self.table)

    # todo: maybe ensure that group-size matches
    def set_group(self, group):
        row = 0
        for team in group['teams']:
            icon_path = 'icons/%s.png' % team['name']
            #if not os.path.isfile(os.path.abspath(icon_path)):
            #    icon_path = 'icons/trophy.png'
            self.table.setItem(row, 0, QTableWidgetItem(QIcon(icon_path), team['name']))
            if not self.teams_only:
                self.table.setItem(row, 1, QTableWidgetItem(str(team['games'])))
                self.table.setItem(row, 2, QTableWidgetItem(str(team['won'])))
                self.table.setItem(row, 3, QTableWidgetItem(str(team['lost'])))
                self.table.setItem(row, 4, QTableWidgetItem('%r:%r' % (team['score'], team['conceded'])))
            for c in range(self.table.columnCount()):
                self.table.item(row, c).setFlags(self.table.item(row, c).flags() ^ Qt.ItemIsEditable)
                self.table.item(row, c).setFlags(self.table.item(row, c).flags() ^ Qt.ItemIsSelectable)
            row += 1


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
        p = self._completer
        stylesheet = self.styleSheet()
        while p.parent() is not None:
            stylesheet = p.parent().styleSheet()
            p = p.parent()

        self._completer.popup().setStyleSheet(stylesheet)
        self.setCompleter(self._completer)

        self.lineEdit().textEdited.connect(self._proxy.setFilterFixedString)

    def on_completer_activated(self, text):
        if not text: return
        self.setCurrentIndex(self.findText(text))
        self.activated[str].emit(self.currentText())
