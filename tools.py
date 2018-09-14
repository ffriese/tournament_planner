import math
from PyQt5 import QtSql
from PyQt5.QtCore import QVariant
from PyQt5.QtSql import QSqlQuery


class DBException(Exception):
    def __init__(self, query):
        exec_q = query.executedQuery()
        for key in query.boundValues().keys():
            exec_q = exec_q.replace(key, str(query.boundValue(key)))
        super().__init__('%s -> %s' % (exec_q, query.lastError().text()))


class DataBaseManager:
    def __init__(self):
        self.db = QtSql.QSqlDatabase.addDatabase('QSQLITE')
        self.db.setDatabaseName('flunkyrock.db')
        self.init()

    def init(self):
        self.db.open()
        query = QtSql.QSqlQuery()
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
            else:
                print('created tables')
        else:
            print('found tables')
        self.db.close()

    def get_current_id(self, table):
        assert self.db.isOpen()
        query = QtSql.QSqlQuery()
        query.prepare('SELECT * FROM SQLITE_SEQUENCE WHERE name=:table')
        query.bindValue(':table', table)
        if query.exec_():
            seq = query.record().indexOf("seq")
            query.next()

            ret = query.record().value(seq)
        else:
            print("ERROR: request failed: ", query.lastError().text())
            ret = -2
        return ret

    # data.keys = ['group_size': int, 'name': str, 'teams_in_ko': int, 'teams': list(str)}
    def store_tournament(self, data):
        self.db.open()
        query = QtSql.QSqlQuery()

        if 'Tournaments' not in self.db.tables():
            self.db.close()
            print('db_error: table Tournaments not found')
            return
        try:
            self.db.transaction()
            query.prepare('INSERT INTO Tournaments(name) VALUES (:name)')
            query.bindValue(':name', data['name'])
            if not query.exec_():
                raise DBException(query)
            tournament_id = self.get_current_id('Tournaments')
            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index) VALUES (:t_id, 1)')
            query.bindValue(':t_id', tournament_id)
            if not query.exec_():
                raise DBException(query)
            ts_id = self.get_current_id('Tournament_Stages')
            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', ts_id)
            if not query.exec_():
                raise DBException(query)
            query.prepare('INSERT INTO Groups(group_stage, size) VALUES(:gs_id, :size)')
            for g in range(0, int(math.ceil(len(data['teams'])/int(data['group_size'])))):
                query.bindValue(':gs_id', ts_id)
                query.bindValue(':size', data['group_size'])
                if not query.exec_():
                    raise DBException(query)

            # create ko-stages
            teams_in_ko = data['teams_in_ko']
            index = 2
            while teams_in_ko > 1:
                query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index) VALUES (:t_id, :idx)')
                query.bindValue(':t_id', tournament_id)
                query.bindValue(':idx', index)
                if not query.exec_():
                    raise DBException(query)
                ts_id = self.get_current_id('Tournament_Stages')
                query.prepare('INSERT INTO KO_Stages(tournament_stage) VALUES (:ts_id)')
                query.bindValue(':ts_id', ts_id)
                if not query.exec_():
                    raise DBException(query)
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
                        if not query.exec_():
                            raise DBException(query)
                        team_id = self.get_current_id('Teams')
                    query.prepare('INSERT INTO Tournament_Teams(tournament, team) VALUES(:tour_id, :team_id)')
                    query.bindValue(':tour_id', tournament_id)
                    query.bindValue(':team_id', team_id)
                    if not query.exec_():
                        raise DBException(query)

            self.db.commit()
            print('added %s to db' % data['name'])
            self.db.close()
            return True
        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
            self.db.close()
            return False

    # this is just for testing purposes, of course there won't be a full copy of the database as a python dict
    # in the finished version, but it is very convenient for now
    def read_data(self):
        self.db.open()
        query = QtSql.QSqlQuery()
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
        self.db.close()
        return data
