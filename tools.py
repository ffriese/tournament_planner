import math
from PyQt5.QtSql import QSqlQuery, QSqlDatabase


class DBException(Exception):
    def __init__(self, query):
        exec_q = query.executedQuery()
        for key in query.boundValues().keys():
            exec_q = exec_q.replace(key, str(query.boundValue(key)))
        super().__init__('%s -> %s' % (exec_q, query.lastError().text()))


class DataBaseManager:
    def __init__(self):
        self.db = QSqlDatabase.addDatabase('QSQLITE')
        self.db.setDatabaseName('flunkyrock.db')
        self.init()

    def init(self):
        self.db.open()
        query = QSqlQuery()
        if 'Teams' not in self.db.tables():

            query.exec_('CREATE TABLE Teams ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'name VARCHAR(40) NOT NULL UNIQUE '
                        ')')

            query.exec_('CREATE TABLE Tournaments ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'name VARCHAR(40) NOT NULL UNIQUE ,'
                        'stylesheet VARCHAR(50)'
                        ')')

            query.exec_('CREATE TABLE Tournament_Teams ('
                        'tournament INTEGER,'
                        'team INTEGER,'
                        'FOREIGN KEY (tournament) REFERENCES Tournaments(id) ON DELETE CASCADE,'
                        'FOREIGN KEY (team) REFERENCES Teams(id)'
                        ')')

            query.exec_('CREATE TABLE Tournament_Stages ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'tournament INTEGER,'
                        'stage_index INTEGER,'
                        'name VARCHAR(10),'
                        'FOREIGN KEY(tournament) REFERENCES Tournaments(id) ON DELETE CASCADE'
                        ')')

            query.exec_('CREATE TABLE Group_Stages ('
                        'tournament_stage INTEGER,'
                        'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id) ON DELETE CASCADE'
                        ')')

            query.exec_('CREATE TABLE KO_Stages ('
                        'tournament_stage INTEGER,'
                        'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id) ON DELETE CASCADE'
                        ')')

            query.exec_('CREATE TABLE Groups ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                        'group_stage INTEGER,'
                        'size INTEGER,'
                        'name VARCHAR(10),'
                        'FOREIGN KEY (group_stage) REFERENCES Group_Stages(tournament_stage) ON DELETE CASCADE'
                        ')')

            query.exec_('CREATE TABLE Group_Teams ('
                        'group_id INTEGER,'
                        'team INTEGER,'
                        'FOREIGN KEY (group_id) REFERENCES Groups(id) ON DELETE CASCADE,'
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
                        'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id) ON DELETE CASCADE'
                        ')')
        self.db.close()

    def get_current_id(self, table):
        assert self.db.isOpen()
        query = QSqlQuery()
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

    def add_team(self, team_name):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('INSERT INTO Teams(name) VALUES (:team_name)')
            query.bindValue(':team_name', team_name)
            if not query.exec_():
                raise DBException(query)
            else:
                team_id = self.get_current_id('Teams')
                self.db.close()
                return team_id

        except DBException as ex:
            print('db_error:', ex)
            self.db.close()
            return None

    def get_team_id(self, team_name):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('SELECT id FROM Teams WHERE name=:team_name')
            query.bindValue(':team_name', team_name)
            if query.exec_():
                seq = query.record().indexOf("id")
                query.next()
                ret = query.record().value(seq)
            else:
                raise DBException(query)
        finally:
            self.db.close()
        return ret

    def get_tournament_id(self, tournament_name):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('SELECT id FROM Tournaments WHERE name=:tournament_name')
            query.bindValue(':tournament_name', tournament_name)
            if query.exec_():
                seq = query.record().indexOf("id")
                query.next()
                ret = query.record().value(seq)
            else:
                raise DBException(query)
        finally:
            self.db.close()
        return ret

    def get_tournament_groups(self, tournament):
        self.db.open()
        query = QSqlQuery()
        query2 = QSqlQuery()
        query3 = QSqlQuery()

        if type(tournament) is int:
            query.prepare('SELECT id FROM Tournament_Stages WHERE tournament == :id AND stage_index == 1')
            query.bindValue(':id', tournament)

        else:
            query.prepare('SELECT id FROM Tournament_Stages WHERE id == '
                          '(SELECT id FROM Tournaments WHERE name == :name) AND stage_index == 1')
            query.bindValue(':name', tournament)
        if query.exec_():
            if query.next():
                stage_id = query.value('id')
            else:
                raise DBException(query)
        else:
            raise DBException(query)

        query2.prepare('SELECT name FROM Teams WHERE id == :t_id')
        groups = []

        query3.prepare('SELECT team, SUM(Win)+SUM(Loss) as games, SUM(Win) As won, SUM(Loss) as lost,'
                       'Sum(score)-Sum(against) as diff, SUM(score) as score , SUM(against) as conceded FROM'
                       '( SELECT team1 as team,'
                       ' CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END as Win, team2_score as against,'
                       ' CASE WHEN team1_score < team2_score THEN 1 ELSE 0 END as Loss, team1_score as score'
                       ' FROM Matches WHERE tournament_stage == :stage_id AND team1 in '
                       '(SELECT team from Group_Teams WHERE group_id == :g_id)'
                       ' UNION ALL'
                       ' SELECT team2 as team,'
                       ' CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END as Win, team1_score as against,'
                       ' CASE WHEN team2_score < team1_score THEN 1 ELSE 0 END as Loss, team2_score as score'
                       ' FROM Matches WHERE tournament_stage == :stage_id AND team2 in '
                       '(SELECT team from Group_Teams WHERE group_id == :g_id)'
                       ') t GROUP BY team'
                       ' ORDER By won DESC, diff DESC, score DESC, conceded')

        query3.bindValue(':stage_id', stage_id)

        if type(tournament) is int:
            query.prepare('SELECT * FROM Groups WHERE group_stage IN '
                          '(SELECT tournament_stage from Group_Stages WHERE tournament_stage IN '
                          '(SELECT id FROM Tournament_Stages WHERE tournament == :id))')
            query.bindValue(':id', tournament)

        else:
            query.prepare('SELECT * FROM Groups WHERE group_stage IN '
                          '(SELECT tournament_stage from Group_Stages WHERE tournament_stage IN '
                          '(SELECT id FROM Tournament_Stages WHERE id == '
                          '(SELECT id FROM Tournaments WHERE name == :name)))')
            query.bindValue(':name', tournament)
        if query.exec_():
            while query.next():
                query3.bindValue(':g_id', query.record().value('id'))
                teams = []
                if query3.exec_():
                    while query3.next():
                        query2.bindValue(':t_id', query3.record().value('team'))
                        if query2.exec_():
                            query2.next()
                            team_name = query2.value('name')
                        else:
                            print('TEAM not found')
                            raise DBException()
                        teams.append({
                            'id': query3.value('team'),
                            'name': team_name,
                            'games': query3.value('games'),
                            'won': query3.value('won'),
                            'lost': query3.value('lost'),
                            'diff': query3.value('diff'),
                            'score': query3.value('score'),
                            'conceded': query3.value('conceded')
                        })
                else:
                    raise DBException(query3)
                group = {
                    'name': query.record().value('name'),
                    'id': query.record().value('id'),
                    'size': query.record().value('size'),
                    'teams': teams}
                groups.append(group)
        else:
            raise DBException(query)
        return groups

    #  data.keys = ['group_size': int, 'name': str, 'teams_in_ko': int, 'teams': dict{name:id}}
    def import_two_stage_tournament(self, data):
        self.db.open()
        query = QSqlQuery()
        query2 = QSqlQuery()

        if 'Tournaments' not in self.db.tables():
            self.db.close()
            print('db_error: table Tournaments not found')
            return
        try:
            self.db.transaction()
            query.prepare('INSERT INTO Tournaments(name, stylesheet) VALUES (:name, :stylesheet)')
            query.bindValue(':name', data['name'])
            query.bindValue(':stylesheet', data['stylesheet'])
            if not query.exec_():
                raise DBException(query)
            tournament_id = self.get_current_id('Tournaments')

            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) '
                          'VALUES (:t_id, 1, :name)')
            query.bindValue(':t_id', tournament_id)
            query.bindValue(':name', 'GROUP')
            if not query.exec_():
                raise DBException(query)
            gs_id = self.get_current_id('Tournament_Stages')
            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', gs_id)
            if not query.exec_():
                raise DBException(query)
            query.prepare('INSERT INTO Groups(group_stage, size, name) VALUES(:gs_id, :size, :name)')
            query2.prepare('INSERT INTO Group_Teams(group_id, team) VALUES (:g_id, :team_id)')
            for g in sorted(data['groups'].keys()):
                query.bindValue(':gs_id', gs_id)
                query.bindValue(':size', data['group_size'])
                query.bindValue(':name', g)
                if not query.exec_():
                    raise DBException(query)
                g_id = self.get_current_id('Groups')
                for t in data['groups'][g]:
                    query2.bindValue(':g_id', int(g_id))
                    query2.bindValue(':team_id', int(data['teams'][t]))
                    if not query2.exec_():
                        raise DBException(query2)

            # create ko-stages

            ko_keys = sorted(data['ko_stages'].keys(), reverse=True)
            finals = sorted(data['finals'].keys(), reverse=True)
            for f in finals:
                data['ko_stages'][f] = -1
                ko_keys.append(f)

            index = 2
            for ko_stage in ko_keys:
                query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) '
                              'VALUES (:t_id, :idx, :name)')
                query.bindValue(':t_id', tournament_id)
                query.bindValue(':idx', index)
                query.bindValue(':name', ko_stage)
                if not query.exec_():
                    raise DBException(query)
                ts_id = self.get_current_id('Tournament_Stages')
                query.prepare('INSERT INTO KO_Stages(tournament_stage) VALUES (:ts_id)')
                query.bindValue(':ts_id', ts_id)
                if not query.exec_():
                    raise DBException(query)
                index += 1
                data['ko_stages'][ko_stage] = ts_id

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

            # add matches
            query.prepare('INSERT INTO Matches(team1, team2, team1_score, team2_score, status, tournament_stage) '
                          'VALUES (:t1, :t2, :t1s, :t2s, 2, :t_stage)')
            for stage in data['matches']:
                if stage in data['ko_stages']:
                    s_id = data['ko_stages'][stage]
                elif stage in data['groups']:
                    s_id = gs_id
                for match in data['matches'][stage]:
                    query.bindValue(':t1', data['teams'][match['team1']])
                    query.bindValue(':t2', data['teams'][match['team2']])
                    query.bindValue(':t1s', match['score1'])
                    query.bindValue(':t2s', match['score2'])
                    query.bindValue(':t_stage', s_id)
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

    # data.keys = ['group_size': int, 'name': str, 'teams_in_ko': int, 'teams': list(str)}
    def store_tournament(self, data):
        self.db.open()
        query = QSqlQuery()

        if 'Tournaments' not in self.db.tables():
            self.db.close()
            print('db_error: table Tournaments not found')
            return
        try:
            self.db.transaction()
            query.prepare('INSERT INTO Tournaments(name, stylesheet) VALUES (:name, :stylesheet)')
            query.bindValue(':name', data['name'])
            query.bindValue(':stylesheet', data['stylesheet'])
            if not query.exec_():
                raise DBException(query)
            tournament_id = self.get_current_id('Tournaments')
            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) VALUES (:t_id, 1, "GROUP")')
            query.bindValue(':t_id', tournament_id)
            if not query.exec_():
                raise DBException(query)
            ts_id = self.get_current_id('Tournament_Stages')
            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', ts_id)
            if not query.exec_():
                raise DBException(query)
            query.prepare('INSERT INTO Groups(group_stage, size, name) VALUES(:gs_id, :size, :name)')
            for g in range(0, int(math.ceil(len(data['teams'])/int(data['group_size'])))):
                query.bindValue(':gs_id', ts_id)
                query.bindValue(':size', data['group_size'])
                query.bindValue(':name', str(chr(g+65)))
                if not query.exec_():
                    raise DBException(query)

            # create ko-stages including 3rd place final
            teams_in_ko = data['teams_in_ko']
            index = 2
            while teams_in_ko >= 1:
                query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) VALUES (:t_id, :idx, :name)')
                query.bindValue(':t_id', tournament_id)
                query.bindValue(':idx', index)
                if teams_in_ko > 2:
                    query.bindValue(':name', 'KO%r' % int(teams_in_ko/2))
                elif teams_in_ko == 2:
                    if index > 2:
                        query.bindValue(':name', 'KO_FINAL_3')
                    else:
                        query.bindValue(':name', 'KO_FINAL_1')
                else:
                    if index > 3:
                        query.bindValue(':name', 'KO_FINAL_1')
                    else:
                        break

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
        query = QSqlQuery()
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


# IMPORTANT QUERYS:
#
# EWIGE TABELLE:
"""
SELECT team, SUM(Win)+SUM(Loss) as Games, SUM(Win) As Won, SUM(Loss) as Lost,
  Sum(score)-Sum(against) as Bierferenz, SUM(score) as Score , SUM(against) as Against FROM
( SELECT team1 as team,
     CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END as Win, team2_score as against,
     CASE WHEN team1_score < team2_score THEN 1 ELSE 0 END as Loss, team1_score as score
  FROM Matches
  UNION ALL
  SELECT team2 as team,
     CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END as Win, team1_score as against,
     CASE WHEN team2_score < team1_score THEN 1 ELSE 0 END as Loss, team2_score as score
  FROM Matches
) t
GROUP BY team
ORDER By Won DESC, Bierferenz DESC, Score DESC, Against
"""