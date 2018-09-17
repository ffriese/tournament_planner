import sys

from PyQt5.QtCore import pyqtSignal, Qt

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout, QSizePolicy, QStyle, QMainWindow, QMenuBar, \
    QMenu, QAction, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
from PyQt5.QtGui import QIcon
from wizards import TournamentWizard
from tools import DataBaseManager, DBException


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'FlunkyRock Planner'
        self.left = 10
        self.top = 10
        self.width = 1280
        self.height = 800
        self.database = DataBaseManager()
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon('favicon.ico'))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; color: white;')

        # self.homeMenu = self.menuBar().addMenu('Home')
        # self.testAction = self.homeMenu.addAction('test')
        self.homeAction = self.menuBar().addAction('Home')
        self.homeAction.triggered.connect(self.toggle_home)

        self.data = self.database.read_data()
        self.homeWidget = HomeWidget(self.data)
        self.tournamentWidget = TournamentWidget()
        self.setCentralWidget(self.homeWidget)

        self.homeWidget.tournament_opened.connect(self.open_tournament)
        self.homeWidget.tournament_created.connect(self.create_tournament)

        self.show()

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
        except DBException as e:
            print(e)
        self.tournamentWidget.set_tournament(tournament, groups)
        self.switch_central_widget(self.tournamentWidget)

    def create_tournament(self, data):
        if self.database.store_tournament(data):
            self.data = self.database.read_data()
            if type(self.centralWidget()) == HomeWidget:
                self.homeWidget = HomeWidget(self.data)
                self.homeWidget.tournament_opened.connect(self.open_tournament)
                self.homeWidget.tournament_created.connect(self.create_tournament)
                self.setCentralWidget(self.homeWidget)


class TournamentWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QGridLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.nameLabel = QLabel()
        self.group_widget = GroupStageWidget()
        self.layout.addWidget(self.nameLabel)
        self.layout.addWidget(self.group_widget)

    def set_tournament(self, tournament, groups=None):
        self.setStyleSheet(tournament['stylesheet'])
        self.nameLabel.setText(tournament['name'])
        if groups is not None:
            self.group_widget.set_groups(groups)


class GroupStageWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = None
    # groups = [
    #     {'name': 'A',
    #      'id': 2,
    #      'size': 4,
    #      'teams': [
    #           ('Team1', 3),
    #            ('Team2', 4)
    #      ]
    #     },
    #     {'name': 'B' }
    # ]

    def set_groups(self, groups):
        if self.layout is not None:
            for i in reversed(range(self.layout.count())):
                self.layout.itemAt(i).widget().setParent(None)
        else:
            self.layout = QGridLayout()
            self.setLayout(self.layout)
        for group in groups:
            tw = QTableWidget()
            tw.setRowCount(group['size'])
            tw.verticalHeader().setDefaultSectionSize(20)
            tw.setColumnCount(5)
            tw.setHorizontalHeaderLabels(['Name', 'G', 'W', 'L', 'BD'])
            tw.setColumnWidth(0, 180)
            tw.setColumnWidth(1, 20)
            tw.setColumnWidth(2, 20)
            tw.setColumnWidth(3, 20)
            tw.setColumnWidth(4, 40)
            row = 0
            for team in group['teams']:
                tw.setItem(row, 0, QTableWidgetItem(team['name']))
                tw.setItem(row, 1, QTableWidgetItem(str(team['games'])))
                tw.setItem(row, 2, QTableWidgetItem(str(team['won'])))
                tw.setItem(row, 3, QTableWidgetItem(str(team['lost'])))
                tw.setItem(row, 4, QTableWidgetItem('%r:%r' % (team['score'], team['conceded'])))
                row += 1
            # tw.sortByColumn(2, Qt.DescendingOrder)
            self.layout.addWidget(tw)

    def add_matches(self, matches):
        pass


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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
