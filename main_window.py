import sys

import math
from PyQt5 import QtSql
from PyQt5.QtCore import QVariant, pyqtSignal
from PyQt5.QtSql import QSqlQuery

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout, QSizePolicy, QStyle, QMainWindow, QMenuBar, \
    QMenu, QAction, QVBoxLayout, QLabel
from PyQt5.QtGui import QIcon
from wizards import TournamentWizard


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'FlunkyRock Planner'
        self.left = 10
        self.top = 10
        self.width = 1280
        self.height = 800
        self.db = None
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon('favicon.ico'))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; color: white;')

        # self.homeMenu = self.menuBar().addMenu('Home')
        # self.testAction = self.homeMenu.addAction('test')
        self.homeAction = self.menuBar().addAction('Home')
        self.homeAction.triggered.connect(self.toggle_home)

        self.data = self.connect_to_database()
        self.homeWidget = HomeWidget(self.data)
        self.tournamentWidget = TournamentWidget()
        self.setCentralWidget(self.homeWidget)

        self.homeWidget.tournament_opened.connect(self.open_tournament)
        self.homeWidget.tournament_created.connect(self.create_tournament)

        self.show()

    def toggle_home(self):
        if type(self.centralWidget()) == HomeWidget:
            self.centralWidget().setParent(None)  # prevent_deletion
            self.setCentralWidget(self.tournamentWidget)
        else:
            self.centralWidget().setParent(None)  # prevent_deletion
            self.setCentralWidget(self.homeWidget)

    def open_tournament(self, tournament):
        self.tournamentWidget.set_tournament(tournament)
        self.centralWidget().setParent(None)  # prevent_deletion
        self.setCentralWidget(self.tournamentWidget)

    def create_tournament(self, data):
        print(data)
        self.save_tournament_to_database(data)

    # todo: move this from here into model part of the code

    def save_tournament_to_database(self, data):

        def get_current_id(table):
            query = QtSql.QSqlQuery()
            query.prepare('SELECT * FROM SQLITE_SEQUENCE WHERE name=:table')
            query.bindValue(':table', table)
            if query.exec_():
                seq = query.record().indexOf("seq")
                query.next()
                return query.record().value(seq)
            else:
                print("ERROR: request failed: ", query.lastError().text())
                return -2

        if self.db is None:
            self.db = QtSql.QSqlDatabase.addDatabase('QSQLITE')
            self.db.setDatabaseName('flunkyrock.db')
        self.db.open()
        query = QtSql.QSqlQuery()

        if 'Tournaments' not in self.db.tables():
            self.db.close()
            print('db_error: table Tournaments not found')
            return

        print('trying to add %s to db...' % data['name'])
        try:
            self.db.transaction()
            query.prepare('INSERT INTO Tournaments(name) VALUES (:name)')
            query.bindValue(':name', data['name'])
            query.exec_()
            tournament_id = get_current_id('Tournaments')
            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index) VALUES (:t_id, 1)')
            query.bindValue(':t_id', tournament_id)
            query.exec_()
            ts_id = get_current_id('Tournament_Stages')
            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', ts_id)
            query.exec_()
            query.prepare('INSERT INTO Groups(group_stage, size) VALUES(:gs_id, :size)')
            for g in range(0, int(math.ceil(len(data['teams'])/int(data['group_size'])))):
                query.bindValue(':gs_id', ts_id)
                query.bindValue(':size', data['group_size'])
                query.exec_()

            # create ko-stages
            teams_in_ko = data['teams_in_ko']
            index = 2
            while teams_in_ko > 1:
                query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index) VALUES (:t_id, :idx)')
                query.bindValue(':t_id', tournament_id)
                query.bindValue(':idx', index)
                query.exec_()
                ts_id = get_current_id('Tournament_Stages')
                query.prepare('INSERT INTO KO_Stages(tournament_stage) VALUES (:ts_id)')
                query.bindValue(':ts_id', ts_id)
                query.exec_()
                index += 1
                teams_in_ko /= 2

            # add teams
            query.exec_('SELECT * FROM Teams')
            db_teams = {}
            while query.next():
                db_teams[query.value('name')] = query.value('id')
            for team in data['teams']:
                if team != '':
                    if team in db_teams:
                        team_id = db_teams[team]
                    else:
                        query.prepare('INSERT INTO Teams(name) VALUES(:team)')
                        query.bindValue(':team', team)
                        query.exec_()
                        team_id = get_current_id('Teams')
                    query.prepare('INSERT INTO Tournament_Teams(tournament, team) VALUES(:tour_id, :team_id)')
                    query.bindValue(':tour_id', tournament_id)
                    query.bindValue(':team_id', team_id)
                    query.exec_()

            self.db.commit()

            print('added %s to db...' % data['name'])
            print('db close')
            self.db.close()
            self.data = self.connect_to_database()
            if type(self.centralWidget()) == HomeWidget:
                self.homeWidget = HomeWidget(self.data)
                self.homeWidget.tournament_opened.connect(self.open_tournament)
                self.homeWidget.tournament_created.connect(self.create_tournament)
                self.setCentralWidget(self.homeWidget)
        except IndexError:
            print('db_error:', query.lastError(), query.lastError().text())
            self.db.rollback()
            print('db close')
            self.db.close()

    def connect_to_database(self):
        if self.db is None:
            self.db = QtSql.QSqlDatabase.addDatabase('QSQLITE')
            self.db.setDatabaseName('flunkyrock.db')
        self.db.open()
        query = QtSql.QSqlQuery()

        # this is just for testing purposes, of course there won't be a full copy of the database as a python dict
        # in the finished version, but it is very convenient for now
        def read_data():
            data = {}
            for table in self.db.tables():

                data[table] = []
                keys = [self.db.record(table).field(x).name() for x in range(self.db.record(table).count())]
                query.exec_('SELECT * from %s' % table)
                while query.next():
                    entry = {}
                    for key in keys:
                        entry[key] = query.value(key)
                    data[table].append(entry)
            return data

        if 'Teams' not in self.db.tables():

            query.exec_('CREATE TABLE Teams ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'name VARCHAR(40) NOT NULL'
                        ')')

            query.exec_('CREATE TABLE Tournaments ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'name VARCHAR(40) NOT NULL,'
                        'stylesheet VARCHAR(50)'
                        ')')

            query.exec_('CREATE TABLE Tournament_Teams ('
                        'tournament INTEGER,'
                        'team INTEGER,'
                        'FOREIGN KEY (tournament) REFERENCES Tournaments(id),'
                        'FOREIGN KEY (team) REFERENCES Teams(id)'
                        ')')
            
            query.exec_('CREATE TABLE Tournament_Stages ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'tournament INTEGER,'
                        'stage_index INTEGER,'
                        'FOREIGN KEY(tournament) REFERENCES Tournaments(id)'
                        ')')

            query.exec_('CREATE TABLE Group_Stages ('
                        'tournament_stage INTEGER,'
                        'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id)'
                        ')')

            query.exec_('CREATE TABLE KO_Stages ('
                        'tournament_stage INTEGER,'
                        'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id)'
                        ')')

            query.exec_('CREATE TABLE Groups ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'group_stage INTEGER,'
                        'size INTEGER,'
                        'FOREIGN KEY (group_stage) REFERENCES Group_Stages(tournament_stage)'
                        ')')

            query.exec_('CREATE TABLE Group_Teams ('
                        'group_id INTEGER,'
                        'team INTEGER,'
                        'FOREIGN KEY (group_id) REFERENCES Groups(id),'
                        'FOREIGN KEY (team) REFERENCES Teams(id)'
                        ')')

            query.exec_('CREATE TABLE Matches ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'team1 INTEGER,'
                        'team2 INTEGER,'
                        'team1_score INTEGER,'
                        'team2_score INTEGER,'
                        'status INTEGER,'
                        'tournament_stage INTEGER,'
                        'FOREIGN KEY(team1) REFERENCES Teams(id),'
                        'FOREIGN KEY(team2) REFERENCES Teams(id),'
                        'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id)'
                        ')')

            # insert dummy tournaments, todo: remove, obviously
            query.prepare('INSERT INTO Tournaments(name, stylesheet) VALUES (:tournament_name, :style_sheet)')
            tournaments = [
                            ('FlunkyRock 2015', 'background-color: rgb(30,143,158); color: rgb(0,0,80)'),
                            ('FlunkyRock 2016', 'background-color: rgb(70,190,130); color: rgb(0,80,0)'),
                            ('FlunkyRock 2017', 'background-color: rgb(174,56,52); color: rgb(255,255,255)')
            ]
            query.bindValue(':tournament_name', [QVariant(t[0]) for t in tournaments])
            query.bindValue(':style_sheet', [QVariant(t[1]) for t in tournaments])
            if not query.execBatch(mode=QSqlQuery.ValuesAsRows):
                print(query.lastError().text())
                self.db.close()
                return {'Tournaments': [], 'Teams': []}

            # insert dummy teams, todo: remove, obviously
            query.prepare('INSERT INTO Teams(name) VALUES (:team_name)')
            teams = ['Flunkengötter', 'Beardy Beer', 'Sportfreunde Gartenhaus', 'Ralles Raketen',
                     'Die Bierprinzessinnen']
            query.bindValue(':team_name', [QVariant(t) for t in teams])
            if not query.execBatch(mode=QSqlQuery.ValuesAsRows):
                print(query.lastError().text())
                self.db.close()
                return {'Tournaments': [], 'Teams': []}
            else:
                print('created tables')
        else:
            print('found tables')
        data = read_data()
        self.db.close()
        return data


class TournamentWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QGridLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.nameLabel = QLabel()
        self.layout.addWidget(self.nameLabel)

    def set_tournament(self, tournament):
        self.setStyleSheet(tournament['stylesheet'])
        self.nameLabel.setText(tournament['name'])


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
        r = 0
        c = 0
        for t in self.data['Tournaments']:
            bt = QPushButton(t['name'])
            bt.setStyleSheet(t['stylesheet'])
            bt.setIcon(QIcon('favicon.ico'))
            bt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            bt.setProperty('tournament', t)
            bt.clicked.connect(self.tournament_clicked)
            self.layout.addWidget(bt, r, c)
            if c == 0:
                c = 1
            else:
                c = 0
                r += 1

        self.layout.addWidget(create_tournament_button, r, c)

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
