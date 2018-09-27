import sys

from PyQt5.QtCore import pyqtSignal, QDir, QCoreApplication, Qt, QSize

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout, QSizePolicy, QStyle, QMainWindow, QToolBar
from PyQt5.QtGui import QIcon, QImage, QPainter, QColor

from widgets import TournamentWidget, AllTimeTableWidget
from wizards import TournamentWizard
from tools import DataBaseManager, DBException


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'FlunkyRock Planner'
        self.left = 10
        self.top = 10
        self.width = 1280
        self.height = 700
        self.data = None
        self.database = DataBaseManager()
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon('icons/favicon.ico'))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; '
                           'color: white')
        self.toolbar = QToolBar("Main")
        self.addToolBar(Qt.BottomToolBarArea, self.toolbar)
        self.homeAction = self.toolbar.addAction(QIcon('icons/home_large.png'), 'Home')
        self.syncAction = self.toolbar.addAction(QIcon('icons/web_database.png'), 'Sync with FlunkyRock.de')
        self.homeAction.triggered.connect(self.go_home)
        self.syncAction.triggered.connect(self.database.remote_queue.execute_updates)
        self.database.remote_queue.sync_status.connect(self.update_remote_icon)
        self.database.remote_queue.execute_updates()
        self.fetch_data()
        self.homeWidget = HomeWidget(self.data)
        self.tournamentWidget = TournamentWidget(self.database, self)
        self.allTimeTableWidget = AllTimeTableWidget(self)
        self.tournamentWidget.hide()
        self.allTimeTableWidget.hide()
        self.setCentralWidget(self.homeWidget)

        self.homeWidget.tournament_opened.connect(self.open_tournament)
        self.homeWidget.tournament_created.connect(self.create_tournament)
        self.homeWidget.show_all_time_table.connect(self.show_all_time_table)

        #directory = QDir('icons')
        #files = directory.entryList(["*.png"])
        #for file in files:
        #    #print(file)
        #    image = QImage()
        #    image.load("icons/" + file)
        #    image.save("icons/" + file)

        self.show()

    def fetch_data(self):
        self.data = self.database.read_data(['Tournaments', 'Teams'])

    def switch_central_widget(self, widget):
        self.centralWidget().setParent(None)  # prevent_deletion
        self.setCentralWidget(widget)
        widget.show()

    def go_home(self):
        self.switch_central_widget(self.homeWidget)

    def show_all_time_table(self):
        all_time_table = self.database.get_all_time_table()
        self.allTimeTableWidget.update_table(all_time_table)
        self.switch_central_widget(self.allTimeTableWidget)

    def open_tournament(self, tournament):
        try:
            t_teams = self.database.get_tournament_teams(tournament['id'])
            groups = self.database.get_tournament_groups(tournament['id'])
            ko_stages = self.database.get_tournament_ko_stages(tournament['id'])
            status = self.database.get_tournament_status(tournament['id'])
            self.tournamentWidget.set_tournament(tournament, db_teams=self.data['Teams'],
                                                 t_teams=t_teams, groups=groups, ko_stages=ko_stages, status=status)
            self.switch_central_widget(self.tournamentWidget)
            self.tournamentWidget.show_main_page()
        except DBException as e:
            print(e)

    def create_tournament(self, data):
        if self.database.store_tournament(data):
            self.database.remote_queue.execute_updates()
            self.fetch_data()
            if type(self.centralWidget()) == HomeWidget:
                self.homeWidget = HomeWidget(self.data)
                self.homeWidget.tournament_opened.connect(self.open_tournament)
                self.homeWidget.tournament_created.connect(self.create_tournament)
                self.go_home()

    def update_remote_icon(self, sync_status):
        icon = QIcon('icons/web_database.png')
        queue_size = sync_status['queue_size']
        if queue_size > 0:
            px = icon.pixmap(QSize(128, 128))
            painter = QPainter()
            painter.begin(px)
            painter.setPen(QColor(255, 0, 0))
            painter.setBrush(QColor(255, 0, 0))
            painter.drawEllipse(0, 60, 68, 68)

            painter.setPen(QColor(255, 255, 255))
            painter.setBrush(QColor(255, 255, 255))
            font = painter.font()
            font.setPixelSize(45)
            font.setWeight(40)
            painter.setFont(font)
            painter.drawText(0, 60, 68, 68, Qt.AlignHCenter | Qt.AlignVCenter, str(queue_size))
            painter.end()
            self.syncAction.setIcon(QIcon(px))
        else:
            self.syncAction.setIcon(icon)
        # self.syncAction.setEnabled(sync_status['internet'])


class HomeWidget(QWidget):
    tournament_opened = pyqtSignal(dict)
    tournament_created = pyqtSignal(dict)
    show_all_time_table = pyqtSignal()

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
        create_tournament_button.setIcon(QIcon('icons/application_add'))
        create_tournament_button.clicked.connect(self.show_tournament_wizard)
        all_time_table_button = QPushButton('All-Time-Table', self)
        all_time_table_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        all_time_table_button.setIcon(QIcon('icons/medal_gold_1.png'))
        all_time_table_button.clicked.connect(self.show_all_time_table)
        row = 0
        col = 0
        for t in self.data['Tournaments']:
            bt = QPushButton(t['name'])
            bt.setStyleSheet(t['stylesheet'])
            bt.setIcon(QIcon('icons/favicon.ico'))
            bt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            bt.setProperty('tournament', t)
            bt.setProperty('bg_img', 'true')
            bt.clicked.connect(self.tournament_clicked)
            self.layout.addWidget(bt, row, col)
            if col == 0:
                col = 1
            else:
                col = 0
                row += 1

        self.layout.addWidget(create_tournament_button, row, col)
        if col == 0:
            col = 1
        else:
            col = 0
            row += 1
        self.layout.addWidget(all_time_table_button, row, col)

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
