import math
from enum import Enum

from PyQt5.QtCore import QVariant
from PyQt5.QtSql import QSqlQuery, QSqlDatabase


class TournamentStageStatus(Enum):
    INITIALIZED = 1  # Stage 0: NOT YET ENOUGH TEAMS    , Stage 1+: MATCHES GENERATED
    IN_PROGRESS = 2  # Stage 0: INITIAL DRAW TO BE DONE , Stage 1+: STAGE IN PROGRESS
    COMPLETE = 3      # Stage 0: DRAW COMPLETE           , Stage 1+: STAGE COMPLETE


class DBException(Exception):
    def __init__(self, query):
        super().__init__(query.lastError().text())
        self.query = query

    def get_last_query(self):
        exec_q = self.query.executedQuery()
        for key in self.query.boundValues().keys():
            exec_q = exec_q.replace(key, str(self.query.boundValue(key)))
        return exec_q


class InsertNotUniqueException(DBException):
    def __init__(self, query):
        super().__init__(query)


# taken from ih84ds:
# https://gist.github.com/ih84ds/be485a92f334c293ce4f1c84bfba54c9
def create_balanced_round_robin(list):
    """ Create a schedule for the teams in the list and return it"""
    s = []
    if len(list) % 2 == 1: list = list + ["BYE"]
    # manipulate map (array of indexes for list) instead of list itself
    # this takes advantage of even/odd indexes to determine home vs. away
    map = [i for i in range(len(list))]
    mid = int(len(map) / 2)
    for i in range(len(map) - 1):
        l1 = map[:mid]
        l2 = map[mid:]
        l2.reverse()
        round = []
        for match in zip(l1, l2):
            # team 1 is team with lower index
            t1 = list[min(match)]
            # team 2 is team with higher index
            t2 = list[max(match)]
            # this will equalize home/away for each team +/- 1
            swap = ((match[0] + match[1]) % 2) == 1
            if swap:
                round.append((t2, t1))
            else:
                round.append((t1, t2))
        s.append(round)
        # rotate list, except for first element
        map.insert(1, map.pop())
    return s


class DataBaseManager:
    def __init__(self):
        self.db = QSqlDatabase.addDatabase('QSQLITE')
        self.db.setDatabaseName('flunkyrock.db')
        self.init()

    def init(self):
        self.db.open()
        query = QSqlQuery()
        try:
            if 'Teams' not in self.db.tables():
                query.exec_('CREATE TABLE Teams ('
                            'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                            'name VARCHAR(40) NOT NULL UNIQUE '
                            ')')

                query.exec_('CREATE TABLE Tournaments ('
                            'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                            'name VARCHAR(40) NOT NULL UNIQUE ,'
                            'num_teams INTEGER NOT NULL,'
                            'stylesheet VARCHAR(50)'
                            ')')

                query.exec_('CREATE TABLE Tournament_Teams ('
                            'tournament INTEGER,'
                            'team INTEGER,'
                            'FOREIGN KEY (tournament) REFERENCES Tournaments(id) ON DELETE CASCADE,'
                            'FOREIGN KEY (team) REFERENCES Teams(id)'
                            ')')

                query.exec_('CREATE TABLE Tournament_Fields ('
                            'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                            'tournament INTEGER,'
                            'name VARCHAR(30),'
                            'FOREIGN KEY (tournament) REFERENCES Tournaments(id) ON DELETE CASCADE'
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
                            'best_of INTEGER NOT NULL DEFAULT 1,'
                            'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id) ON DELETE CASCADE'
                            ')')

                query.exec_('CREATE TABLE Groups ('
                            'id INTEGER PRIMARY KEY AUTOINCREMENT ,'
                            'group_stage INTEGER,'
                            'size INTEGER,'
                            'name VARCHAR(10),'
                            'rounds INTEGER NOT NULL DEFAULT 1,'
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
                            'tournament_stage INTEGER, '
                            'field INTEGER,'
                            'FOREIGN KEY(team1) REFERENCES Teams(id),'
                            'FOREIGN KEY(team2) REFERENCES Teams(id),'
                            'FOREIGN KEY(field) REFERENCES Tournament_Fields(id),'
                            'FOREIGN KEY(tournament_stage) REFERENCES Tournament_Stages(id) ON DELETE CASCADE'
                            ')')
        finally:
            self.db.close()

    @staticmethod
    def execute_query(query, batch=False):
        def execute():
            if batch:
                return query.execBatch(mode=QSqlQuery.ValuesAsRows)
            else:
                return query.exec_()

        if not execute():
            if query.lastError().text().startswith('UNIQUE constraint failed'):
                raise InsertNotUniqueException(query)
            else:
                raise DBException(query)

    @staticmethod
    def simple_get(query, key):
        assert query.next()
        return query.value(key)

    @staticmethod
    def simple_get_multiple(query, keys):
        result = []
        while query.next():
            row = {}
            for key in keys:
                row[key] = query.value(key)
            result.append(row)
        return result

    def get_current_id(self, table):
        assert self.db.isOpen()
        query = QSqlQuery()
        query.prepare('SELECT * FROM SQLITE_SEQUENCE WHERE name=:table')
        query.bindValue(':table', table)
        self.execute_query(query)
        return self.simple_get(query, 'seq')

    def add_team(self, team_name):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('INSERT INTO Teams(name) VALUES (:team_name)')
            query.bindValue(':team_name', team_name)
            self.execute_query(query)
            team_id = self.get_current_id('Teams')
            return team_id
        except DBException as ex:
            print('db_error:', ex)
            return None
        finally:
            self.db.close()

    def update_tournament_groups(self, tournament_id, groups):
        g_ids = []
        t_ids = []
        for g in groups:
            for t in g['teams']:
                t_ids.append(t)
                g_ids.append(g['id'])
        self.db.open()
        self.db.transaction()
        try:
            query = QSqlQuery()
            # delete all entries in Group_Teams
            query.prepare('DELETE FROM Group_Teams WHERE group_id IN (SELECT Groups.id FROM Groups JOIN '
                          'Tournament_Stages ON Tournament_Stages.id==Groups.group_stage '
                          'WHERE Tournament_Stages.tournament==:tournament_id)')
            query.bindValue(':tournament_id', tournament_id)
            self.execute_query(query)

            # update Group_Teams
            query.prepare('INSERT INTO Group_Teams(group_id, team) VALUES (:group_id, :team_id)')
            query.bindValue(':group_id', [QVariant(g) for g in g_ids])
            query.bindValue(':team_id', [QVariant(t) for t in t_ids])
            self.execute_query(query, batch=True)

            # update Groups (rounds etc)
            query.prepare('UPDATE Groups SET rounds = :rounds WHERE id==:g_id')
            for g in groups:
                query.bindValue(':rounds', g['rounds'])
                query.bindValue(':g_id', g['id'])
                self.execute_query(query)
            self.db.commit()

        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
        finally:
            self.db.close()

    def update_match(self, match):
        print('MATCH HAS BEEN RECEIVED BY DB_APP:', match)
        self.db.open()
        try:
            query = QSqlQuery()
            query.prepare('UPDATE Matches SET team1_score = :t1_s, team2_score = :t2_s, status= :status '
                          'WHERE id == :m_id')
            query.bindValue(':t1_s', match['team1_score'])
            query.bindValue(':t2_s', match['team2_score'])
            query.bindValue(':status', match['status'])
            query.bindValue(':m_id', match['id'])
            self.execute_query(query)
            print(DBException(query).get_last_query())
            print('hmm')
        finally:
            self.db.close()

    def generate_matches(self, tournament_id, data):
        print('database got generate-request', tournament_id, data)
        self.db.open()
        self.db.transaction()
        try:
            query = QSqlQuery()
            if data['status'] == TournamentStageStatus.COMPLETE:
                if data['next_stage'] is None:
                    raise AssertionError('TOURNAMENT COMPLETE, THIS SHOULD NEVER HAPPEN ANYHOW')
                elif data['next_stage']['name'] == 'GROUP':
                    # TODO: DO CRAZY GROUP STUFF!!
                    # 1) get all group ids and rounds
                    query.prepare('SELECT id, rounds, name FROM Groups WHERE group_stage == :gs_id')
                    query.bindValue(':gs_id', data['next_stage']['id'])
                    self.execute_query(query)
                    groups = self.simple_get_multiple(query, ['id', 'rounds', 'name'])
                    # 2) for each group, generate matches
                    schedule = []
                    for group in groups:
                        # 2.1) get teams
                        query.prepare('SELECT team as id, name FROM Group_Teams JOIN Teams '
                                      'ON Group_Teams.team==Teams.id WHERE group_id == :g_id')
                        query.bindValue(':g_id', group['id'])
                        self.execute_query(query)
                        teams = self.simple_get_multiple(query, ['id', 'name'])
                        # 2.2) for each round generate matches
                        # 2.2.1) generate a single round of matches
                        sched = create_balanced_round_robin(teams)
                        for round in range(group['rounds']):
                            for game_day in sched:
                                for m in game_day:
                                    if m[0] != 'BYE' and m[1] != 'BYE':
                                        schedule.append({'team1_id': m[0]['id'],
                                                                        'team2_id': m[1]['id']})
                        #                print(m)
                        # print('------------------------------')
                    print(schedule)
                    query.prepare('INSERT INTO Matches(team1, team2, status, tournament_stage) '
                                  'VALUES (:t1, :t2, 0, :ts_id)')
                    query.bindValue(':t1', [QVariant(m['team1_id']) for m in schedule])
                    query.bindValue(':t2', [QVariant(m['team2_id']) for m in schedule])
                    query.bindValue(':ts_id', [QVariant(data['next_stage']['id']) for m in schedule])
                    self.execute_query(query, batch=True)
                else:
                    # TODO: DO CRAZY KO-STAGE STUFF
                    pass
            elif data['status'] == TournamentStageStatus.INITIALIZED:
                # TODO: REGENERATE, FOR THIS WE WILL NEED TO AMEND THE CURRENT_STAGE-INFORMATION
                pass
            else:
                raise AssertionError('STAGE ALREADY IN PROGRESS, THIS SHOULD NEVER HAPPEN ANYHOW')
            self.db.commit()
        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
        finally:
            self.db.close()

    def update_tournament_teams(self, tournament_id, teams):
        self.db.open()
        self.db.transaction()
        try:
            query = QSqlQuery()
            # add all new teams to database
            query.prepare('INSERT INTO Teams(name) VALUES (:name)')
            ids = []
            for team in teams:
                try:
                    ids.append(team['id'])
                except KeyError:
                    # team needs to be added
                    query.bindValue(':name', team['name'])
                    self.execute_query(query)
                    ids.append(self.get_current_id('Teams'))

            # delete all teams from Tournament_Teams table
            query.prepare('DELETE FROM Tournament_Teams WHERE tournament==:tournament_id')
            query.bindValue(':tournament_id', tournament_id)
            self.execute_query(query)

            # add all new teams
            query.prepare('INSERT INTO Tournament_Teams(tournament, team) VALUES (:tournament_id, :team_id)')
            query.bindValue(':tournament_id', [QVariant(tournament_id) for t in ids])
            query.bindValue(':team_id', [QVariant(t) for t in ids])
            self.execute_query(query, batch=True)
            self.db.commit()
        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
        finally:
            self.db.close()

    def get_team_id(self, team_name):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('SELECT id FROM Teams WHERE name=:team_name')
            query.bindValue(':team_name', team_name)
            self.execute_query(query)
            return self.simple_get(query, 'id')
        finally:
            self.db.close()

    def get_tournament_id(self, tournament_name):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('SELECT id FROM Tournaments WHERE name=:tournament_name')
            query.bindValue(':tournament_name', tournament_name)
            self.execute_query(query)
            return self.simple_get(query, 'id')
        finally:
            self.db.close()

    def get_tournament_status(self, tournament_id):
        self.db.open()
        try:
            query = QSqlQuery()
            query.prepare('SELECT'
                          ' (SELECT COUNT() FROM Group_Teams WHERE group_id IN '
                          '    (SELECT id FROM Groups WHERE group_stage IN '
                          '    (SELECT id FROM Tournament_Stages WHERE tournament == :id))) as teams_in_groups,'
                          '(SELECT num_teams FROM Tournaments WHERE id == :id) as expected_teams,'
                          '(SELECT COUNT() FROM Tournament_Teams WHERE tournament == :id) as tournament_teams')
            query.bindValue(':id', tournament_id)

            self.execute_query(query)
            assert query.next()
            expected_teams = query.value('expected_teams')
            tournament_teams = query.value('tournament_teams')
            teams_in_groups = query.value('teams_in_groups')

            if expected_teams > tournament_teams:
                return {'current_stage': 0,
                        'name': 'SETUP',
                        'status': TournamentStageStatus.INITIALIZED}
            elif tournament_teams > teams_in_groups:
                return {'current_stage': 0,
                        'name': 'SETUP',
                        'status': TournamentStageStatus.IN_PROGRESS}

            query.prepare('SELECT id, tournament, stage_index, name, expected_matches'
                          ', COALESCE(pr_count, 0) as matches_in_progress, COALESCE(count, 0) as complete_matches, '
                          ' COALESCE(scheduled_count, 0) as scheduled_matches, '
                          'CASE WHEN COALESCE(count, 0) > 0 THEN '
                          ' CASE WHEN COALESCE(pr_count, 0) > 0 THEN '
                          '    1 '
                          ' ELSE '
                          '    CASE WHEN COALESCE(count, 0) < expected_matches THEN '
                          '     1 '
                          '    ELSE '
                          '     2'            
                          '    END '
                          ' END '
                          ' ELSE '
                          ' 0 '
                          'END as stage_status'
                          ' FROM Tournament_Stages '
                          'JOIN (SELECT id as stage, REPLACE(SUBSTR(name, 3,1),"_","1")*best_of as expected_matches '
                          'FROM KO_Stages Join Tournament_Stages ON KO_Stages.tournament_stage == Tournament_Stages.id'
                          ' UNION '
                          'SELECT group_matches.group_stage as stage, SUM(exp_matches) as expected_matches FROM '
                          '(SELECT  group_id, group_stage, name, '
                          'COUNT(team), rounds*(COUNT(team)*(COUNT(team)-1))/2 as exp_matches '
                          'FROM Groups LEFT JOIN Group_Teams ON Groups.id == Group_Teams.group_id GROUP BY group_id) '
                          'as group_matches GROUP BY group_matches.group_stage) as exp '
                          'ON Tournament_Stages.id == exp.stage '
                          'LEFT JOIN '
                          '(SELECT COUNT() as count,  tournament_stage FROM Matches WHERE status== 2 '
                          'GROUP BY tournament_stage )  AS cnt ON Tournament_Stages.id == cnt.tournament_stage '
                          'LEFT JOIN '
                          '(SELECT COUNT() as pr_count,  tournament_stage FROM Matches WHERE status== 1 '
                          'GROUP BY tournament_stage )  AS pcnt ON Tournament_Stages.id == pcnt.tournament_stage '
                          'LEFT JOIN '
                          '(SELECT COUNT() as scheduled_count,  tournament_stage FROM Matches WHERE status== 0 '
                          'GROUP BY tournament_stage )  AS e_cnt ON Tournament_Stages.id == e_cnt.tournament_stage '
                          'WHERE tournament == :id'
                          )

            query.bindValue(':id', tournament_id)
            self.execute_query(query)
            keys = ['id', 'name', 'stage_status', 'expected_matches', 'matches_in_progress',
                    'complete_matches', 'scheduled_matches']
            stages = []
            while query.next():
                d = {}
                for key in keys:
                    d[key] = query.value(key)
                stages.append(d)

            def get_next_stage(curr_stage):
                try:
                    return {'id': stages[curr_stage]['id'],
                            'name': stages[curr_stage]['name']}
                except IndexError:
                    return None

            current_status = {
                'current_stage': 0,
                'name': 'SETUP',
                'status': TournamentStageStatus.COMPLETE,
                'next_stage': get_next_stage(0)
            }

            def prev_stage_complete(curr_stage, curr_status):
                if curr_status['current_stage'] == curr_stage or \
                    (curr_status['current_stage'] == curr_stage - 1 and
                     curr_status['status'] == TournamentStageStatus.COMPLETE):
                    return True
                return False

            stage_index = 0
            for stage in stages:
                stage_index += 1
                match_sum = stage['scheduled_matches'] + stage['matches_in_progress'] + stage['complete_matches']
                if stage['expected_matches'] > 0:
                    if stage['expected_matches'] == stage['complete_matches']:
                        current_status = {
                            'current_stage': stage_index,
                            'name': stage['name'],
                            'status': TournamentStageStatus.COMPLETE,
                            'next_stage': get_next_stage(stage_index)
                        }
                        # print('stage', stage_index, 'complete')
                    elif stage['expected_matches'] == match_sum and \
                            (stage['matches_in_progress'] > 0 or stage['complete_matches'] > 0):
                        current_status = {
                            'current_stage': stage_index,
                            'name': stage['name'],
                            'status': TournamentStageStatus.IN_PROGRESS
                        }
                        # print('stage', stage_index, 'in progress')
                    elif stage['scheduled_matches'] == stage['expected_matches'] and \
                            prev_stage_complete(stage_index, current_status):
                        current_status = {
                            'current_stage': stage_index,
                            'name': stage['name'],
                            'status': TournamentStageStatus.INITIALIZED
                        }
                        # print('stage', stage_index, 'initialized')
                    else:
                        pass
                        # print('stage', stage_index, 'pending')
            return current_status
        finally:
            self.db.close()

    def get_tournament_teams(self, tournament_id):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('SELECT * FROM Tournament_Teams JOIN Teams ON Tournament_Teams.team = Teams.id '
                          'WHERE Tournament_Teams.tournament == :t_id')
            query.bindValue(':t_id', tournament_id)
            self.execute_query(query)
            return self.simple_get_multiple(query, ['id', 'name'])
        finally:
            self.db.close()

    def get_teams(self):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('SELECT * FROM Teams')
            self.execute_query(query)
            return self.simple_get_multiple(query, ['id', 'name'])
        finally:
            self.db.close()

    def get_tournament_groups(self, tournament_id):
        self.db.open()
        query = QSqlQuery()
        group_table_query = QSqlQuery()
        group_matches_query = QSqlQuery()
        try:
            groups = []
            query.prepare('SELECT id FROM Tournament_Stages WHERE tournament == :id AND stage_index == 1')
            query.bindValue(':id', tournament_id)

            group_table_query.\
                prepare('SELECT id as team, Teams.name as team_name, COALESCE(Games, 0) as games, '
                        'COALESCE(Won, 0) as won, '
                        'COALESCE(Lost, 0) as lost, COALESCE(Bierferenz, 0) as diff, '
                        'COALESCE(Score, 0) as score, COALESCE(Against, 0) as conceded '
                        'FROM Teams LEFT JOIN (SELECT team, SUM(Win)+SUM(Loss) as Games, SUM(Win) As Won, '
                        'SUM(Loss) as Lost, Sum(score)-Sum(against) as Bierferenz, SUM(score) as Score , '
                        'SUM(against) as Against FROM ( SELECT team1 as team, '
                        'CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END as Win, team2_score as against, '
                        'CASE WHEN team1_score < team2_score THEN 1 ELSE 0 END as Loss, team1_score as score'
                        ' FROM Matches WHERE tournament_stage == :stage_id UNION ALL SELECT team2 as team, '
                        'CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END as Win, team1_score as against, '
                        'CASE WHEN team2_score < team1_score THEN 1 ELSE 0 END as Loss, team2_score as score '
                        'FROM Matches WHERE tournament_stage == :stage_id ) t '
                        'GROUP BY team) as g_table ON Teams.id==g_table.team WHERE Teams.id in '
                        '(SELECT team FROM Group_Teams WHERE group_id==:g_id) '
                        ' ORDER By won DESC, diff DESC, score DESC, conceded')

            group_matches_query.\
                prepare('select Matches.id,'
                        '   T1.id as team1_id, '
                        '   T2.id as team2_id, '
                        '   T1.name as team1, '
                        '   T2.name as team2, '
                        '   Matches.team1_score, '
                        '   Matches.team2_score, '
                        '   Matches.field,'
                        '   Matches.status '
                        ' from Matches'
                        ' join Teams as T1 on Matches.team1 = T1.id'
                        ' join Teams as T2 on Matches.team2 = T2.id '
                        'WHERE tournament_stage == :stage_id and T1.id in '
                        '(SELECT team FROM Group_Teams WHERE group_id == :g_id)')
            self.execute_query(query)
            stage_id = self.simple_get(query, 'id')

            group_table_query.bindValue(':stage_id', stage_id)
            group_matches_query.bindValue(':stage_id', stage_id)

            query.prepare('SELECT * FROM Groups WHERE group_stage IN '
                          '(SELECT tournament_stage from Group_Stages WHERE tournament_stage IN '
                          '(SELECT id FROM Tournament_Stages WHERE tournament == :id))')
            query.bindValue(':id', tournament_id)

            self.execute_query(query)
            # for each group
            while query.next():
                group_table_query.bindValue(':g_id', query.record().value('id'))
                teams = []
                self.execute_query(group_table_query)
                # for each team
                while group_table_query.next():
                    teams.append({
                        'id': group_table_query.value('team'),
                        'name': group_table_query.value('team_name'),
                        'games': group_table_query.value('games'),
                        'won': group_table_query.value('won'),
                        'lost': group_table_query.value('lost'),
                        'diff': group_table_query.value('diff'),
                        'score': group_table_query.value('score'),
                        'conceded': group_table_query.value('conceded')
                    })
                group_matches_query.bindValue(':g_id', query.record().value('id'))
                self.execute_query(group_matches_query)
                matches = self.simple_get_multiple(group_matches_query,
                                                   ['id', 'team1_id', 'team2_id', 'team1', 'team2',
                                                    'team1_score', 'team2_score',
                                                    'status', 'field'])
                group = {
                    'name': query.record().value('name'),
                    'id': query.record().value('id'),
                    'size': query.record().value('size'),
                    'teams': teams,
                    'matches': matches
                }
                groups.append(group)
            return groups
        finally:
            self.db.close()

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
            query.prepare('INSERT INTO Tournaments(name, stylesheet, num_teams) VALUES (:name, :stylesheet, :num_teams)')
            query.bindValue(':name', data['name'])
            query.bindValue(':stylesheet', data['stylesheet'])
            query.bindValue(':num_teams', len(data['teams'].keys()))
            self.execute_query(query)
            tournament_id = self.get_current_id('Tournaments')

            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) '
                          'VALUES (:t_id, 1, :name)')
            query.bindValue(':t_id', tournament_id)
            query.bindValue(':name', 'GROUP')
            self.execute_query(query)
            gs_id = self.get_current_id('Tournament_Stages')
            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', gs_id)
            self.execute_query(query)
            query.prepare('INSERT INTO Groups(group_stage, size, name, rounds) VALUES(:gs_id, :size, :name, :rounds)')
            query2.prepare('INSERT INTO Group_Teams(group_id, team) VALUES (:g_id, :team_id)')
            for g in sorted(data['groups'].keys()):
                query.bindValue(':gs_id', gs_id)
                query.bindValue(':size', data['group_size'])
                query.bindValue(':name', g)
                # todo: this may be working for now, but it's somewhat brittle.. maybe find better solution
                if len(data['groups'][g]) < 3:
                    query.bindValue(':rounds', 2)
                else:
                    query.bindValue(':rounds', 1)
                self.execute_query(query)
                g_id = self.get_current_id('Groups')
                for t in data['groups'][g]:
                    query2.bindValue(':g_id', int(g_id))
                    query2.bindValue(':team_id', int(data['teams'][t]))
                    self.execute_query(query2)

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
                self.execute_query(query)
                ts_id = self.get_current_id('Tournament_Stages')
                query.prepare('INSERT INTO KO_Stages(tournament_stage) VALUES (:ts_id)')
                query.bindValue(':ts_id', ts_id)
                self.execute_query(query)
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
                        self.execute_query(query)
                        team_id = self.get_current_id('Teams')
                    query.prepare('INSERT INTO Tournament_Teams(tournament, team) VALUES(:tour_id, :team_id)')
                    query.bindValue(':tour_id', tournament_id)
                    query.bindValue(':team_id', team_id)
                    self.execute_query(query)

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
                    self.execute_query(query)

            self.db.commit()
            print('added %s to db' % data['name'])
            return True
        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
            return False
        finally:
            self.db.close()

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
            query.prepare('INSERT INTO Tournaments(name, stylesheet, num_teams) VALUES (:name, :stylesheet, :num_teams)')
            query.bindValue(':name', data['name'])
            query.bindValue(':stylesheet', data['stylesheet'])
            query.bindValue(':num_teams', len(data['teams']))
            self.execute_query(query)
            tournament_id = self.get_current_id('Tournaments')
            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) VALUES (:t_id, 1, "GROUP")')
            query.bindValue(':t_id', tournament_id)
            self.execute_query(query)
            ts_id = self.get_current_id('Tournament_Stages')
            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', ts_id)
            self.execute_query(query)
            query.prepare('INSERT INTO Groups(group_stage, size, name) VALUES(:gs_id, :size, :name)')
            for g in range(0, int(math.ceil(len(data['teams'])/int(data['group_size'])))):
                query.bindValue(':gs_id', ts_id)
                query.bindValue(':size', data['group_size'])
                query.bindValue(':name', str(chr(g+65)))
                self.execute_query(query)

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

                self.execute_query(query)
                ts_id = self.get_current_id('Tournament_Stages')
                query.prepare('INSERT INTO KO_Stages(tournament_stage) VALUES (:ts_id)')
                query.bindValue(':ts_id', ts_id)
                self.execute_query(query)
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
                        self.execute_query(query)
                        team_id = self.get_current_id('Teams')
                    query.prepare('INSERT INTO Tournament_Teams(tournament, team) VALUES(:tour_id, :team_id)')
                    query.bindValue(':tour_id', tournament_id)
                    query.bindValue(':team_id', team_id)
                    self.execute_query(query)

            self.db.commit()
            print('added %s to db' % data['name'])
            return True
        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
            return False
        finally:
            self.db.close()

    # this is just for testing purposes, of course there won't be a full copy of the database as a python dict
    # in the finished version, but it is very convenient for now
    def read_data(self, table_names=None):
        self.db.open()
        query = QSqlQuery()
        data = {}
        try:
            tables = set(table_names).intersection(self.db.tables()) if table_names is not None else self.db.tables()
            for table in tables:

                data[table] = []
                keys = [self.db.record(table).field(x).name() for x in range(self.db.record(table).count())]
                query.exec_('SELECT * from %s' % table)
                while query.next():
                    entry = {}
                    for key in keys:
                        entry[key] = query.value(key)
                    data[table].append(entry)
            return data
        finally:
            self.db.close()


# IMPORTANT QUERYS:
#
# EWIGE TABELLE:
"""
SELECT team, name, Games, Won, Lost, Bierferenz, Score, Against FROM (SELECT team, SUM(Win)+SUM(Loss) as Games, SUM(Win) As Won, SUM(Loss) as Lost,
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
ORDER By Won DESC, Bierferenz DESC, Score DESC, Against) as ewig JOIN Teams ON ewig.team == Teams.id
"""

# get stage completion
"""
SELECT id, tournament, stage_index, name, expected_matches, count, expected_matches == count as stage_complete FROM Tournament_Stages JOIN (SELECT id as stage, REPLACE(SUBSTR(name, 3,1),"_","1")*best_of as expected_matches FROM KO_Stages Join Tournament_Stages ON KO_Stages.tournament_stage == Tournament_Stages.id
UNION
SELECT group_matches.group_stage as stage, SUM(exp_matches) as expected_matches FROM (SELECT  group_id, group_stage, name, COUNT(team), rounds*(COUNT(team)*(COUNT(team)-1))/2 as exp_matches 
FROM Groups JOIN Group_Teams ON Groups.id == Group_Teams.group_id GROUP BY group_id) as group_matches GROUP BY group_matches.group_stage) as exp ON Tournament_Stages.id == exp.stage
JOIN (SELECT COUNT() as count,  tournament_stage FROM Matches WHERE status== 2 GROUP BY tournament_stage )  AS cnt ON Tournament_Stages.id == cnt.tournament_stage
WHERE tournament == 3
"""