import sys
from PyQt5 import QtSql
from PyQt5.QtCore import QVariant
from PyQt5.QtSql import QSqlQuery

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout, QSizePolicy, QStyle
from PyQt5.QtGui import QIcon
from wizards import TournamentWizard


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.title = 'FlunkyRock Planner'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480
        self.tournament_wizard = None
        self.layout = None
        self.data = self.connect_to_database()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon('favicon.ico'))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold;')
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.layout = QGridLayout()
        self.layout.setSpacing(45)
        self.layout.setContentsMargins(45, 45, 45, 45)
        self.setLayout(self.layout)
        create_tournament_button = QPushButton('Create Tournament', self)
        create_tournament_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        create_tournament_button.setStyleSheet('background-color: rgb(190, 190, 190); color: rgb(0, 0, 0)')
        create_tournament_button.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_FileDialogNewFolder')))
        create_tournament_button.clicked.connect(self.show_tournament_wizard)
        r = 0
        c = 0
        for t in self.data['tournaments']:
            bt = QPushButton(t['name'])
            bt.setStyleSheet(t['stylesheet'])
            bt.setIcon(QIcon('favicon.ico'))
            bt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.layout.addWidget(bt, r, c)
            if c == 0:
                c = 1
            else:
                c = 0
                r += 1

        self.layout.addWidget(create_tournament_button, r, c)

        self.show()

    def show_tournament_wizard(self):
        if not self.tournament_wizard:
            self.tournament_wizard = TournamentWizard(self.data['teams'])

        def cleanup():
            self.tournament_wizard = None

        self.tournament_wizard.accepted.connect(cleanup)
        self.tournament_wizard.show()

    # todo: move this from here into model part of the code
    @staticmethod
    def connect_to_database():
        db = QtSql.QSqlDatabase.addDatabase('QSQLITE')
        db.setDatabaseName('flunkyrock.db')
        db.open()
        query = QtSql.QSqlQuery()

        # this is just for testing purposes, of course there won't be a full copy of the database as a python dict
        # in the finished version, but it is very convenient for now
        def read_data():
            data = {}
            for table in db.tables():

                data[table] = []
                keys = [db.record(table).field(x).name() for x in range(db.record(table).count())]
                query.exec_('SELECT * from %s' % table)

                while query.next():
                    entry = {}
                    for key in keys:
                        entry[key] = query.value(key)
                    data[table].append(entry)
            return data

        if 'teams' not in db.tables():
            # create tables
            query.exec_('CREATE TABLE teams(id INTEGER PRIMARY KEY, name VARCHAR(40) NOT NULL)')
            query.exec_('CREATE TABLE tournaments(id INTEGER PRIMARY KEY, name VARCHAR(40) NOT NULL, '
                        'stylesheet VARCHAR(50) NOT NULL )')

            # insert dummy tournaments, todo: remove, obviously
            query.prepare('INSERT INTO tournaments(name, stylesheet) VALUES (:tournament_name, :style_sheet)')
            tournaments = [
                            ('FlunkyRock 2015', 'background-color: rgb(30,143,158); color: rgb(0,0,80)'),
                            ('FlunkyRock 2016', 'background-color: rgb(70,190,130); color: rgb(0,80,0)'),
                            ('FlunkyRock 2017', 'background-color: rgb(174,56,52); color: rgb(255,255,255)')
            ]
            query.bindValue(':tournament_name', [QVariant(t[0]) for t in tournaments])
            query.bindValue(':style_sheet', [QVariant(t[1]) for t in tournaments])
            if not query.execBatch(mode=QSqlQuery.ValuesAsRows):
                print(query.lastError().text())
                db.close()
                return {'tournaments': [], 'teams': []}

            # insert dummy teams, todo: remove, obviously
            query.prepare('INSERT INTO teams(name) VALUES (:team_name)')
            teams = ['Flunkengötter', 'Beardy Beer', 'Sportfreunde Gartenhaus']
            query.bindValue(':team_name', [QVariant(t) for t in teams])
            if not query.execBatch(mode=QSqlQuery.ValuesAsRows):
                print(query.lastError().text())
                db.close()
                return {'tournaments': [], 'teams': []}
            else:
                print('created tables')
        else:
            print('found tables')
        data = read_data()
        db.close()
        return data


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
