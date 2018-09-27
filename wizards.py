from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWizard, QWizardPage, QGridLayout

from widgets import ManageTournamentWidget


class TournamentWizard(QWizard):

    tournament_created = pyqtSignal(dict)

    def __init__(self, teams):
        super().__init__()
        self.setWindowTitle('Create Tournament')
        self.setWindowIcon(QIcon('icons/application_add'))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; '
                           'color: rgb(255,255,255)')
        self.resize(700, 700)
        self.namePage = MainPage(teams, parent=self)
        self.addPage(self.namePage)
        self.accepted.connect(self.create_tournament)

    def create_tournament(self):
        data = self.namePage.mtw.get_data()
        self.tournament_created.emit(data)


class MainPage(QWizardPage):
    def __init__(self, teams, parent=None):
        super(MainPage, self).__init__(parent)
        self.setLayout(QGridLayout())
        self.mtw = ManageTournamentWidget(parent=self)
        self.mtw.set_teams(db_teams=teams, t_teams=[], tournament=None)
        self.layout().addWidget(self.mtw)


