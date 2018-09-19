import sys

from PyQt5.QtCore import pyqtSignal, Qt, QSize

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout, QSizePolicy, QStyle, QMainWindow, QMenuBar, \
    QMenu, QAction, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QHBoxLayout, \
    QToolButton
from PyQt5.QtGui import QIcon

from layout import FlowLayout
from wizards import TournamentWizard
from tools import DataBaseManager, DBException, TournamentStageStatus


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'FlunkyRock Planner'
        self.left = 10
        self.top = 10
        self.width = 1280
        self.height = 800
        self.data = None
        self.database = DataBaseManager()
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon('favicon.ico'))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; color: white;')

        # self.homeMenu = self.menuBar().addMenu('Home')
        # self.testAction = self.homeMenu.addAction('test')
        self.homeAction = self.menuBar().addAction('Home')
        self.homeAction.triggered.connect(self.toggle_home)
        self.fetch_data()
        self.homeWidget = HomeWidget(self.data)
        self.tournamentWidget = TournamentWidget()
        self.setCentralWidget(self.homeWidget)

        self.homeWidget.tournament_opened.connect(self.open_tournament)
        self.homeWidget.tournament_created.connect(self.create_tournament)

        self.show()

    def fetch_data(self):
        self.data = self.database.read_data(['Tournaments', 'Teams'])

    def switch_central_widget(self, widget):
        self.centralWidget().setParent(None)  # prevent_deletion
        self.setCentralWidget(widget)

    def toggle_home(self):
        if type(self.centralWidget()) == HomeWidget:
            self.switch_central_widget(self.tournamentWidget)
        else:
            self.switch_central_widget(self.homeWidget)

    def open_tournament(self, tournament):
        try:
            groups = self.database.get_tournament_groups(tournament['id'])
            status = self.database.get_tournament_status(tournament['id'])
            self.tournamentWidget.set_tournament(tournament, groups, status)
            self.switch_central_widget(self.tournamentWidget)
            self.tournamentWidget.show_main_page()
        except DBException as e:
            print(e)

    def create_tournament(self, data):
        if self.database.store_tournament(data):
            self.fetch_data()
            if type(self.centralWidget()) == HomeWidget:
                self.homeWidget = HomeWidget(self.data)
                self.homeWidget.tournament_opened.connect(self.open_tournament)
                self.homeWidget.tournament_created.connect(self.create_tournament)
                self.setCentralWidget(self.homeWidget)


class HomeWidget(QWidget):
    tournament_opened = pyqtSignal(dict)
    tournament_created = pyqtSignal(dict)

    def __init__(self, data):
        super().__init__()
        self.tournament_wizard = None
        self.layout = None
        self.data = data
        self.init_ui()

    def init_ui(self):

        self.layout = QGridLayout()
        self.layout.setSpacing(45)
        self.layout.setContentsMargins(45, 45, 45, 45)
        self.setLayout(self.layout)
        create_tournament_button = QPushButton('Create Tournament', self)
        create_tournament_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        create_tournament_button.setStyleSheet('background-color: rgb(190, 190, 190); color: rgb(0, 0, 0)')
        create_tournament_button.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_FileDialogNewFolder')))
        create_tournament_button.clicked.connect(self.show_tournament_wizard)
        row = 0
        col = 0
        for t in self.data['Tournaments']:
            bt = QPushButton(t['name'])
            bt.setStyleSheet(t['stylesheet'])
            bt.setIcon(QIcon('favicon.ico'))
            bt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            bt.setProperty('tournament', t)
            bt.clicked.connect(self.tournament_clicked)
            self.layout.addWidget(bt, row, col)
            if col == 0:
                col = 1
            else:
                col = 0
                row += 1

        self.layout.addWidget(create_tournament_button, row, col)

    def tournament_clicked(self):
        self.tournament_opened.emit(self.sender().property('tournament'))

    def show_tournament_wizard(self):
        if not self.tournament_wizard:
            self.tournament_wizard = TournamentWizard(self.data['Teams'])
            self.tournament_wizard.tournament_created.connect(self.tournament_created)

        def cleanup():
            self.tournament_wizard = None

        self.tournament_wizard.accepted.connect(cleanup)
        self.tournament_wizard.show()


class TournamentWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.toolbar = QWidget()
        self.toolbar.setLayout(QHBoxLayout())
        self.toolbar.setMaximumHeight(30)
        self.nameLabel = QLabel()
        self.nameLabel.setMaximumHeight(30)
        self.main_page_button = QToolButton()
        self.main_page_button.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_ArrowBack')))
        self.main_page_button.clicked.connect(self.show_main_page)
        self.toolbar.layout().addWidget(self.nameLabel)
        self.toolbar.layout().addWidget(self.main_page_button)
        self.main_widget = TournamentMainWidget(self)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.main_widget)
        self.widgets = {
            'groups': GroupStageWidget()
        }
        for widget_name in self.widgets:
            self.layout.addWidget(self.widgets[widget_name])
        self.main_widget.button_clicked.connect(self.react_to_button)
        self.show_main_page()

    def show_main_page(self):
        for widget_name in self.widgets:
            self.widgets[widget_name].hide()
        self.main_widget.show()

    def react_to_button(self, widget_name):
        if widget_name in self.widgets:
            self.main_widget.hide()
            self.widgets[widget_name].show()

    def set_tournament(self, tournament, groups=None, status=None):
        self.setStyleSheet(tournament['stylesheet'])
        self.nameLabel.setText(tournament['name'])
        if groups is not None:
            self.widgets['groups'].set_groups(groups)
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
                'icon': self.style().standardIcon(getattr(QStyle, 'SP_ComputerIcon')),
                'enabled': lambda stage, status: True
                             },
            'manage_teams': {
                'bt': QPushButton('Manage Teams', self),
                'icon': self.style().standardIcon(getattr(QStyle, 'SP_FileDialogNewFolder')),
                'enabled': lambda stage, status: stage == 0
                             },
            'groups': {
                'bt': QPushButton('Groups', self),
                'icon': self.style().standardIcon(getattr(QStyle, 'SP_DirIcon')),
                'enabled': lambda stage, status: True
                             },
            'draw_groups': {
                'bt': QPushButton('Draw Groups', self),
                'icon': self.style().standardIcon(getattr(QStyle, 'SP_BrowserReload')),
                'enabled': lambda stage, status: stage == 0 and status == TournamentStageStatus.IN_PROGRESS
                             },
        }
        self.status = None
        self.init_ui()

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
            self.table.setItem(row, 0, QTableWidgetItem(team['name']))
            if not self.teams_only:
                self.table.setItem(row, 1, QTableWidgetItem(str(team['games'])))
                self.table.setItem(row, 2, QTableWidgetItem(str(team['won'])))
                self.table.setItem(row, 3, QTableWidgetItem(str(team['lost'])))
                self.table.setItem(row, 4, QTableWidgetItem('%r:%r' % (team['score'], team['conceded'])))
            for c in range(self.table.columnCount()):
                self.table.item(row, c).setFlags(self.table.item(row, c).flags() ^ Qt.ItemIsEnabled)
            row += 1


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
