import math
import pickle
from collections import OrderedDict
from enum import Enum
from random import shuffle
from urllib.error import URLError
from urllib.request import urlopen

from PyQt5.QtCore import QVariant, pyqtSignal, QObject
from PyQt5.QtSql import QSqlQuery, QSqlDatabase
try:
    from remote_connection import RemoteConnectionManager
except ImportError:
    pass


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


class RemoteQueue(QObject):
    sync_status = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.queue = []
        self.file_name = 'remote_queue'
        remote_sync = False
        try:
            RemoteConnectionManager()
            self.ONLINE_MODE = remote_sync
        except NameError:
            self.ONLINE_MODE = False

        try:
            self.load()
        except FileNotFoundError:
            pass

    def save(self):
        with open(self.file_name, 'wb') as output:
            pickle.dump(self.queue, output)

    def load(self):
        with open(self.file_name, 'rb') as input:
            self.queue = pickle.load(input)

    def queue_size(self):
        return len(self.queue)

    def extend(self, local_queue):
        self.queue.extend(local_queue)
        self.save()

    @staticmethod
    def internet_on():
        try:
            urlopen('http://flunkyrock.de', timeout=2)
            return True
        except URLError as err:
            return False

    def execute_updates(self):
        success = True
        queue_size = len(self.queue)

        if self.ONLINE_MODE and self.internet_on():
            self.sync_status.emit({'internet': True, 'queue_size': self.queue_size()})

            while queue_size > 0 and success:
                update = self.queue[0]
                print('remote', update['action'], ' ==> ', update)
                if self.ONLINE_MODE:
                    success = RemoteConnectionManager.send_request(update)
                else:
                    success = True
                if success:
                    self.queue.pop(0)
                    self.save()
                    self.sync_status.emit({'internet': True, 'queue_size': self.queue_size()})
                else:
                    self.sync_status.emit({'internet': self.internet_on(), 'queue_size': self.queue_size()})

        else:
            self.sync_status.emit({'internet': False, 'queue_size': queue_size})


class DataBaseManager(QObject):

    def __init__(self):
        super().__init__()
        self.db = QSqlDatabase.addDatabase('QSQLITE')
        self.db.setDatabaseName('flunkyrock.db')
        self.remote_queue = RemoteQueue()
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

    @staticmethod
    def create_remote_update(action, table, keys, values, where=None):
        update = {}
        if where is not None:
            w_keys = list(where.keys())
            update['where_keys'] = w_keys
            for key in w_keys:
                if len(where[key]) > 1:
                    values.append(where[key])
                elif len(values) == 0:
                    values.append([where[key][0]])
                else:
                    values.append([where[key][0] for i in range(len(values[0]))])
        update['action'] = action
        update['table'] = table
        update['keys'] = keys
        update['values'] = [values[i][j] for j in range(len(values[0])) for i in range(len(values))]

        return update



    # used for import-script
    def add_team(self, team_name):
        self.db.open()
        query = QSqlQuery()
        try:
            query.prepare('INSERT INTO Teams(name) VALUES (:team_name)')
            query.bindValue(':team_name', team_name)
            self.execute_query(query)
            team_id = self.get_current_id('Teams')
            return team_id
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

        local_update_queue = []
        try:
            query = QSqlQuery()

            # get all entries to be deleted in Group_Teams
            query.prepare('SELECT Groups.id FROM Groups JOIN '
                          'Tournament_Stages ON Tournament_Stages.id==Groups.group_stage '
                          'WHERE Tournament_Stages.tournament==:tournament_id')
            query.bindValue(':tournament_id', tournament_id)
            self.execute_query(query)
            del_ids = [d['id'] for d in self.simple_get_multiple(query, ['id'])]

            # delete all entries in Group_Teams
            query.prepare('DELETE FROM Group_Teams WHERE group_id = (:id)')
            query.bindValue(':id', [QVariant(_id) for _id in del_ids])
            self.execute_query(query, batch=True)

            for _id in del_ids:
                local_update_queue.append(
                    self.create_remote_update('delete', 'Group_Teams', [], [], where={'group_id': [_id]}))

            # add new Group_Teams
            query.prepare('INSERT INTO Group_Teams(group_id, team) VALUES (:group_id, :team_id)')
            query.bindValue(':group_id', [QVariant(g) for g in g_ids])
            query.bindValue(':team_id', [QVariant(t) for t in t_ids])
            self.execute_query(query, batch=True)

            local_update_queue.append(
                self.create_remote_update('insert', 'Group_Teams', ['group_id', 'team'],
                                          [g_ids, t_ids]
                                          ))

            # update Groups (rounds etc)
            query.prepare('UPDATE Groups SET rounds = :rounds WHERE id==:g_id')
            for g in groups:
                query.bindValue(':rounds', g['rounds'])
                query.bindValue(':g_id', g['id'])
                self.execute_query(query)

                local_update_queue.append(
                    self.create_remote_update('update', 'Groups', ['rounds'],
                                              [[g['rounds']]], where={'id': [g['id']]}
                                              ))

            self.db.commit()
            self.remote_queue.extend(local_update_queue)

        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
        finally:
            self.db.close()

    def update_match(self, match):
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
            self.remote_queue.append(
                self.create_remote_update('update', 'Matches', ['team1_score', 'team2_score', 'status'],
                                          [
                                              [match['team1_score']],
                                              [match['team2_score']],
                                              [match['status']]
                                          ], where={'id': [match['id']]}
                                          ))
        finally:
            self.db.close()

    def generate_matches(self, tournament_id, data):
        print('database got generate-request', tournament_id, data)

        def delete_stage_matches(stage_id):
            q = QSqlQuery()
            q.prepare('DELETE FROM Matches WHERE tournament_stage = (:id)')
            q.bindValue(':id', stage_id)
            self.execute_query(q)

            local_update_queue.append(
                self.create_remote_update('delete', 'Matches', [], [], where={'tournament_stage': [stage_id]}
                                          ))
        self.db.open()
        local_update_queue = []
        try:
            query = QSqlQuery()

            print('db-open:', self.db.isOpen())
            if data['status'] == TournamentStageStatus.COMPLETE:
                if data['next_stage'] is None:
                    raise AssertionError('TOURNAMENT COMPLETE, THIS SHOULD NEVER HAPPEN ANYHOW')
                elif data['next_stage']['name'] == 'GROUP':

                    # delete all entries in Matches for next stage
                    delete_stage_matches(data['next_stage']['id'])

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
                                        teams = (m[0], m[1]) if round % 2 else (m[1], m[0])
                                        schedule.append({'team1_id': teams[0]['id'],
                                                         'team2_id': teams[1]['id']})
                    print(schedule)

                    self.db.transaction()
                    query.prepare('INSERT INTO Matches(team1, team2, status, tournament_stage) '
                                  'VALUES (:t1, :t2, 0, :ts_id)')
                    query.bindValue(':t1', [QVariant(m['team1_id']) for m in schedule])
                    query.bindValue(':t2', [QVariant(m['team2_id']) for m in schedule])
                    query.bindValue(':ts_id', [QVariant(data['next_stage']['id']) for m in schedule])
                    self.execute_query(query, batch=True)

                    query.prepare('SELECT * FROM Matches WHERE tournament_stage = :t_id')
                    query.bindValue(':t_id', data['next_stage']['id'])
                    self.execute_query(query)
                    keys = ['id', 'team1', 'team2', 'status', 'tournament_stage']
                    value_dict = self.simple_get_multiple(query, keys)
                    local_update_queue.append(
                        self.create_remote_update('insert', 'Matches', keys,
                                                  [[t[key] for t in value_dict] for key in keys]
                                                  ))

                    self.db.commit()
                    self.remote_queue.extend(local_update_queue)
                elif data['next_stage']['name'].startswith('KO_FINAL'):
                    print('TODO: DO CRAZY FINAL STUFF')

                elif data['next_stage']['name'].startswith('KO'):
                    match_count = int(data['next_stage']['name'][2:3])
                    team_count = match_count * 2
                    groups = self.get_tournament_groups(tournament_id)
                    self.db.open()
                    direct_qualification = math.floor(team_count/len(groups))
                    qualified = []
                    pots = [[] for i in range(direct_qualification)]

                    for group in groups:
                        for q in range(direct_qualification):
                            direct = group['teams'].pop(0)
                            qualified.append(direct)
                            pots[q].append(direct['name'])
                    if len(qualified) < team_count:
                        # fill the rest of the spots with the next best teams...
                        left_over_teams = []
                        for group in groups:
                            for t in group['teams']:
                                left_over_teams.append(t['id'])
                        team_replacement = '(%s)' % ', '.join(['%r' % t for t in left_over_teams])
                        query.prepare(
                            'SELECT id as id, Teams.name as name, COALESCE(Games, 0) as games, '
                            'COALESCE(Won, 0) as won, '
                            'COALESCE(Lost, 0) as lost, COALESCE(Bierferenz, 0) as diff, '
                            'COALESCE(Score, 0) as score, COALESCE(Against, 0) as conceded '
                            'FROM Teams LEFT JOIN (SELECT team, SUM(Win)+SUM(Loss) as Games, SUM(Win) As Won, '
                            'SUM(Loss) as Lost, Sum(score)-Sum(against) as Bierferenz, SUM(score) as Score , '
                            'SUM(against) as Against FROM ( SELECT team1 as team, '
                            'CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END as Win, team2_score as against, '
                            'CASE WHEN team1_score < team2_score THEN 1 ELSE 0 END as Loss, team1_score as score'
                            ' FROM Matches WHERE tournament_stage = :stage_id '
                            'UNION ALL SELECT team2 as team, '
                            'CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END as Win, team1_score as against, '
                            'CASE WHEN team2_score < team1_score THEN 1 ELSE 0 END as Loss, team2_score as score '
                            'FROM Matches WHERE tournament_stage = :stage_id '
                            ') t '
                            'GROUP BY team) as g_table ON Teams.id=g_table.team WHERE Teams.id in '
                            '%s'
                            ' ORDER By won DESC, diff DESC, score DESC, conceded' % team_replacement)
                        query.bindValue(':stage_id', data['current_stage_id'])

                        self.execute_query(query)
                        table = self.simple_get_multiple(query, ['id', 'name', 'won', 'diff'])
                        for i in range(team_count-len(qualified)):
                            qualified.append(table.pop(0))

                    print('qualified:', [t['name'] for t in qualified])
                    # todo: use pots maybe?
                    shuffle(qualified)
                    schedule = []
                    while len(qualified) > 0:
                        teams = [qualified.pop(0), qualified.pop(0)]
                        print('KO-Match: %s - %s' % (teams[0]['name'], teams[1]['name']))
                        schedule.append({'team1_id': teams[0]['id'],
                                         'team2_id': teams[1]['id']})

                    self.db.transaction()
                    query.prepare('INSERT INTO Matches(team1, team2, status, tournament_stage) '
                                  'VALUES (:t1, :t2, 0, :ts_id)')
                    query.bindValue(':t1', [QVariant(m['team1_id']) for m in schedule])
                    query.bindValue(':t2', [QVariant(m['team2_id']) for m in schedule])
                    query.bindValue(':ts_id', [QVariant(data['next_stage']['id']) for m in schedule])
                    self.execute_query(query, batch=True)

                    query.prepare('SELECT * FROM Matches WHERE tournament_stage = :t_id')
                    query.bindValue(':t_id', data['next_stage']['id'])
                    self.execute_query(query)
                    keys = ['id', 'team1', 'team2', 'status', 'tournament_stage']
                    value_dict = self.simple_get_multiple(query, keys)
                    local_update_queue.append(
                        self.create_remote_update('insert', 'Matches', keys,
                                                  [[t[key] for t in value_dict] for key in keys]
                                                  ))

                    self.db.commit()
                    self.remote_queue.extend(local_update_queue)

            elif data['status'] == TournamentStageStatus.INITIALIZED:
                # TODO: REGENERATE, FOR THIS WE WILL NEED TO AMEND THE CURRENT_STAGE-INFORMATION
                print('REGENERATION OF MATCHES IS NOT YET POSSIBLE')
            else:
                raise AssertionError('STAGE ALREADY IN PROGRESS, THIS SHOULD NEVER HAPPEN ANYHOW')

        except DBException as ex:
            print('db_error:', ex, ex.get_last_query())
            self.db.rollback()
        finally:
            self.db.close()

    def update_tournament_stages(self, tournament_id, num_teams, group_size, teams_in_ko):
        print('create new stages. teams:', num_teams, 'group_size:', group_size)
        self.db.open()
        self.db.transaction()
        local_update_queue = []
        query = QSqlQuery()
        try:

            # delete all current stages

            # get stage_ids
            query.prepare('SELECT * FROM Tournament_Stages WHERE tournament = :tournament_id')
            query.bindValue(':tournament_id', tournament_id)
            self.execute_query(query)
            stages = self.simple_get_multiple(query, ['id', 'name'])
            for stage in stages:
                if stage['name'] == 'GROUP':
                    # delete groups
                    query.prepare('DELETE FROM Groups WHERE group_stage = :stage_id')
                    query.bindValue(':stage_id', stage['id'])
                    self.execute_query(query)

                    local_update_queue.append(self.create_remote_update('delete', 'Groups', [], [],
                                                                        where={'group_stage': [stage['id']]}))
                    # delete group-stage-entry
                    query.prepare('DELETE FROM Group_Stages WHERE tournament_stage = :stage_id')
                    query.bindValue(':stage_id', stage['id'])
                    self.execute_query(query)

                    local_update_queue.append(self.create_remote_update('delete', 'Group_Stages', [], [],
                                                                        where={'tournament_stage': [stage['id']]}))
                else:
                    # delete ko-stage-entry
                    query.prepare('DELETE FROM KO_Stages WHERE tournament_stage = :stage_id')
                    query.bindValue(':stage_id', stage['id'])
                    self.execute_query(query)

                    local_update_queue.append(self.create_remote_update('delete', 'KO_Stages', [], [],
                                                                        where={'tournament_stage': [stage['id']]}))
            # delete tournament-stage-entry
            query.prepare('DELETE FROM Tournament_Stages WHERE tournament = :tournament_id')
            query.bindValue(':tournament_id', tournament_id)
            self.execute_query(query)

            local_update_queue.append(self.create_remote_update('delete', 'Tournament_Stages', [], [],
                                                                where={'tournament': [tournament_id]}))

            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) VALUES (:t_id, 1, "GROUP")')
            query.bindValue(':t_id', tournament_id)
            self.execute_query(query)
            ts_id = self.get_current_id('Tournament_Stages')

            local_update_queue.append(self.create_remote_update('insert', 'Tournament_Stages',
                                                                ['id', 'tournament', 'stage_index', 'name'],
                                                                [[ts_id], [tournament_id], [1], ['GROUP']]
                                                                ))

            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', ts_id)
            self.execute_query(query)

            local_update_queue.append(self.create_remote_update('insert', 'Group_Stages',
                                                                ['tournament_stage'],
                                                                [[ts_id]]
                                                                ))

            query.prepare('INSERT INTO Groups(group_stage, size, name) VALUES(:gs_id, :size, :name)')
            for g in range(0, int(math.ceil(num_teams / group_size))):
                query.bindValue(':gs_id', ts_id)
                query.bindValue(':size', group_size)
                query.bindValue(':name', str(chr(g + 65)))
                self.execute_query(query)
                g_id = self.get_current_id('Groups')

                local_update_queue.append(self.create_remote_update('insert', 'Groups',
                                                                    ['id', 'group_stage', 'size', 'name'],
                                                                    [[g_id], [ts_id], [group_size],
                                                                     [str(chr(g + 65))]]
                                                                    ))

            # create ko-stages including 3rd place final
            index = 2
            while teams_in_ko >= 1:
                query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) VALUES (:t_id, :idx, :name)')
                query.bindValue(':t_id', tournament_id)
                query.bindValue(':idx', index)
                if teams_in_ko > 2:
                    query.bindValue(':name', 'KO%r' % int(teams_in_ko / 2))
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

                local_update_queue.append(self.create_remote_update('insert', 'Tournament_Stages',
                                                                    ['id', 'tournament', 'stage_index', 'name'],
                                                                    [[ts_id], [tournament_id], [index],
                                                                     [query.boundValue(':name')]]
                                                                    ))

                query.prepare('INSERT INTO KO_Stages(tournament_stage) VALUES (:ts_id)')
                query.bindValue(':ts_id', ts_id)
                self.execute_query(query)

                local_update_queue.append(self.create_remote_update('insert', 'KO_Stages',
                                                                    ['tournament_stage'],
                                                                    [[ts_id]]
                                                                    ))
                index += 1
                teams_in_ko /= 2

            self.db.commit()
            self.remote_queue.extend(local_update_queue)
        except DBException as ex:
            print('db_error:', ex)
            self.db.rollback()
        finally:
            self.db.close()

    def update_tournament_teams(self, tournament_id, teams, num_teams):
        self.db.open()
        local_update_queue = []
        self.db.transaction()
        try:
            query = QSqlQuery()
            # set number of teams in database
            query.prepare('UPDATE Tournaments SET num_teams = :num_teams WHERE id = :id')
            query.bindValue(':num_teams', num_teams)
            query.bindValue(':id', tournament_id)
            self.execute_query(query)

            local_update_queue.append(self.create_remote_update('update', 'Tournaments',
                                                                ['num_teams'],
                                                                [[num_teams]],
                                                                where={'id': [tournament_id]}
                                                                ))

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
                    team_id = self.get_current_id('Teams')
                    ids.append(team_id)

                    local_update_queue.append(self.create_remote_update('insert', 'Teams',
                                                                        ['id', 'name'],
                                                                        [[team_id], [team['name']]]
                                                                        ))

            # delete all teams from Tournament_Teams table
            query.prepare('DELETE FROM Tournament_Teams WHERE tournament==:tournament_id')
            query.bindValue(':tournament_id', tournament_id)
            self.execute_query(query)

            local_update_queue.append(self.create_remote_update('delete', 'Tournament_Teams', [], [],
                                                                where={'tournament': [tournament_id]}))

            # add all new teams
            query.prepare('INSERT INTO Tournament_Teams(tournament, team) VALUES (:tournament_id, :team_id)')
            query.bindValue(':tournament_id', [QVariant(tournament_id) for t in ids])
            query.bindValue(':team_id', [QVariant(t) for t in ids])
            self.execute_query(query, batch=True)

            local_update_queue.append(self.create_remote_update('insert', 'Tournament_Teams',
                                                                ['tournament', 'team'],
                                                                [[tournament_id for t in ids], ids]
                                                                ))
            self.db.commit()
            self.remote_queue.extend(local_update_queue)
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
                            'current_stage_id': stage['id'],
                            'current_stage': stage_index,
                            'name': stage['name'],
                            'status': TournamentStageStatus.COMPLETE,
                            'next_stage': get_next_stage(stage_index)
                        }
                        # print('stage', stage_index, 'complete')
                    elif stage['expected_matches'] == match_sum and \
                            (stage['matches_in_progress'] > 0 or stage['complete_matches'] > 0):
                        current_status = {
                            'current_stage_id': stage['id'],
                            'current_stage': stage_index,
                            'name': stage['name'],
                            'status': TournamentStageStatus.IN_PROGRESS
                        }
                        # print('stage', stage_index, 'in progress')
                    elif stage['scheduled_matches'] == stage['expected_matches'] and \
                            prev_stage_complete(stage_index, current_status):
                        current_status = {
                            'current_stage_id': stage['id'],
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
                          'WHERE Tournament_Teams.tournament = :t_id')
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

    def get_tournament_ko_stages(self, tournament_id):
        self.db.open()
        ko_matches_query = QSqlQuery()
        try:
            ko_matches_query.prepare('SELECT Matches.id as id, tournament_stage, T1.id as team1_id, T2.id as team2_id, '
                                     'Tournament_Stages.name as stage_name, field, status, '
                                     'tournament, T1.name as team1, T2.name as team2, team1_score, team2_score, status '
                                     'FROM Matches '
                                     'JOIN Tournament_Stages ON Tournament_Stages.id = Matches.tournament_stage '
                                     'join Teams as T1 on Matches.team1 = T1.id '
                                     'join Teams as T2 on Matches.team2 = T2.id '
                                     'WHERE tournament = :t_id and Tournament_Stages.name != "GROUP"')
            ko_matches_query.bindValue(':t_id', tournament_id)
            self.execute_query(ko_matches_query)
            ko_matches = self.simple_get_multiple(ko_matches_query,
                                                  ['id', 'tournament_stage', 'stage_name',
                                                   'team1_id', 'team2_id', 'team1', 'team2',
                                                   'team1_score', 'team2_score',
                                                   'status', 'field'])
            stages = OrderedDict()
            for m in ko_matches:
                if m['tournament_stage'] not in stages:
                    stages[m['tournament_stage']] = {}
                    stages[m['tournament_stage']]['name'] = m['stage_name']
                    stages[m['tournament_stage']]['id'] = m['id']
                    stages[m['tournament_stage']]['matches'] = []
                stages[m['tournament_stage']]['matches'].append(m)

            return stages
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
                prepare('SELECT id as team, Teams.name as name, COALESCE(Games, 0) as games, '
                        'COALESCE(Won, 0) as won, '
                        'COALESCE(Lost, 0) as lost, COALESCE(Bierferenz, 0) as diff, '
                        'COALESCE(Score, 0) as score, COALESCE(Against, 0) as conceded '
                        'FROM Teams LEFT JOIN (SELECT team, SUM(Win)+SUM(Loss) as Games, SUM(Win) As Won, '
                        'SUM(Loss) as Lost, Sum(score)-Sum(against) as Bierferenz, SUM(score) as Score , '
                        'SUM(against) as Against FROM ( SELECT team1 as team, '
                        'CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END as Win, team2_score as against, '
                        'CASE WHEN team1_score < team2_score THEN 1 ELSE 0 END as Loss, team1_score as score'
                        ' FROM Matches WHERE tournament_stage = :stage_id UNION ALL SELECT team2 as team, '
                        'CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END as Win, team1_score as against, '
                        'CASE WHEN team2_score < team1_score THEN 1 ELSE 0 END as Loss, team2_score as score '
                        'FROM Matches WHERE tournament_stage = :stage_id ) t '
                        'GROUP BY team) as g_table ON Teams.id=g_table.team WHERE Teams.id in '
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
                        'WHERE tournament_stage = :stage_id and T1.id in '
                        '(SELECT team FROM Group_Teams WHERE group_id = :g_id)')
            self.execute_query(query)
            stage_id = self.simple_get(query, 'id')

            group_table_query.bindValue(':stage_id', stage_id)
            group_matches_query.bindValue(':stage_id', stage_id)

            query.prepare('SELECT * FROM Groups WHERE group_stage IN '
                          '(SELECT tournament_stage from Group_Stages WHERE tournament_stage IN '
                          '(SELECT id FROM Tournament_Stages WHERE tournament = :id))')
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
                        'name': group_table_query.value('name'),
                        'games': group_table_query.value('games'),
                        'won': group_table_query.value('won'),
                        'lost': group_table_query.value('lost'),
                        'diff': group_table_query.value('diff'),
                        'score': group_table_query.value('score'),
                        'conceded': group_table_query.value('conceded')
                    })

                # solve position-clashes by direct comparison
                last_data = ''
                last_team = -1
                conflicts = {}
                for team in teams:
                    current_data = '%r-%r-%r' % (team['won'], team['diff'], team['score'])
                    if current_data == last_data and current_data != '0-0-0':
                        if last_data not in conflicts:
                            conflicts[last_data] = [team['id'], last_team]
                        else:
                            conflicts[last_data].append(team['id'])
                    last_data = current_data
                    last_team = team['id']

                direct_comp_query = QSqlQuery()
                for conflict in conflicts:
                    print('conflict in group %s: %r, %r' % (query.record().value('name'),
                                                            conflict, conflicts[conflict]))
                    team_replacement = '(%s)' % ','.join([':t%r' % t for t in conflicts[conflict]])
                    direct_comp_query.prepare(
                        'SELECT id as id, Teams.name as name, COALESCE(Games, 0) as games, '
                        'COALESCE(Won, 0) as won, '
                        'COALESCE(Lost, 0) as lost, COALESCE(Bierferenz, 0) as diff, '
                        'COALESCE(Score, 0) as score, COALESCE(Against, 0) as conceded '
                        'FROM Teams LEFT JOIN (SELECT team, SUM(Win)+SUM(Loss) as Games, SUM(Win) As Won, '
                        'SUM(Loss) as Lost, Sum(score)-Sum(against) as Bierferenz, SUM(score) as Score , '
                        'SUM(against) as Against FROM ( SELECT team1 as team, '
                        'CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END as Win, team2_score as against, '
                        'CASE WHEN team1_score < team2_score THEN 1 ELSE 0 END as Loss, team1_score as score'
                        ' FROM Matches WHERE tournament_stage = :stage_id '
                        'AND team1 IN %s AND team2 IN %s'
                        'UNION ALL SELECT team2 as team, '
                        'CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END as Win, team1_score as against, '
                        'CASE WHEN team2_score < team1_score THEN 1 ELSE 0 END as Loss, team2_score as score '
                        'FROM Matches WHERE tournament_stage = :stage_id '
                        'AND team2 IN %s AND team1 IN %s'
                        ') t '
                        'GROUP BY team) as g_table ON Teams.id=g_table.team WHERE Teams.id in '
                        '%s '
                        ' ORDER By won DESC, diff DESC, score DESC, conceded' % (team_replacement,
                                                                                 team_replacement,
                                                                                 team_replacement,
                                                                                 team_replacement,
                                                                                 team_replacement))

                    direct_comp_query.bindValue(':stage_id', stage_id)
                    for t in conflicts[conflict]:
                        direct_comp_query.bindValue(':t%r' % t, QVariant(t))
                    self.execute_query(direct_comp_query)
                    resolution = self.simple_get_multiple(direct_comp_query, ['id'])
                    old_conf_teams = {}
                    for i in range(0, len(teams)):
                        if teams[i]['id'] in conflicts[conflict]:
                            old_conf_teams[teams[i]['id']] = teams[i]
                    for i in range(0, len(teams)):
                        if teams[i]['id'] in conflicts[conflict]:
                            teams[i] = old_conf_teams[resolution.pop(0)['id']]
                    assert len(resolution) == 0

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

    def get_all_time_table(self):
        self.db.open()
        try:
            query = QSqlQuery()
            query.prepare('SELECT team, name, games, won, lost, diff, score, conceded FROM '
                          '(SELECT team, SUM(Win)+SUM(Loss) as games, SUM(Win) As won, SUM(Loss) as lost, '
                          'Sum(score)-Sum(against) as diff, SUM(score) as score , SUM(against) as conceded '
                          'FROM ( SELECT team1 as team, '
                          'CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END as Win, team2_score as against, '
                          'CASE WHEN team1_score <  team2_score THEN 1 ELSE 0 END as Loss, team1_score as score '
                          'FROM Matches UNION ALL SELECT team2 as team, '
                          'CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END as Win, team1_score as against, '
                          'CASE WHEN team2_score < team1_score THEN 1 ELSE 0 END as Loss, team2_score as score '
                          'FROM Matches WHERE status = 2) t GROUP BY team '
                          'ORDER By won DESC, diff DESC, score DESC) '
                          'as ewig JOIN Teams ON  ewig.team = Teams.id')
            self.execute_query(query)
            teams = []
            # for each team
            while query.next():
                teams.append({
                    'id': query.value('team'),
                    'name': query.value('name'),
                    'games': query.value('games'),
                    'won': query.value('won'),
                    'lost': query.value('lost'),
                    'diff': query.value('diff'),
                    'score': query.value('score'),
                    'conceded': query.value('conceded')
                })
            group = {
                'name': 'ALL TIME TABLE',
                'id': None,
                'size': len(teams),
                'teams': teams,
                'matches': None
            }
            return [group]
        finally:
            self.db.close()

    #  data.keys = ['group_size': int, 'name': str, 'teams_in_ko': int, 'teams': dict{name:id}}
    def import_two_stage_tournament(self, data):
        self.db.open()
        query = QSqlQuery()
        query2 = QSqlQuery()
        self.db.transaction()
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
        print(data)
        self.db.open()
        local_update_queue = []
        query = QSqlQuery()
        self.db.transaction()
        try:
            query.prepare('INSERT INTO Tournaments(name, stylesheet, num_teams) VALUES (:name, :stylesheet, :num_teams)')
            query.bindValue(':name', data['name'])
            query.bindValue(':stylesheet', data['stylesheet'])
            query.bindValue(':num_teams', data['num_teams'])
            self.execute_query(query)
            tournament_id = self.get_current_id('Tournaments')

            local_update_queue.append(self.create_remote_update('insert', 'Tournaments',
                                                                ['id', 'name', 'stylesheet', 'num_teams'],
                                                                [[tournament_id], [data['name']],
                                                                 [data['stylesheet']], [len(data['teams'])]]
                                                                ))
            # create group_stage
            query.prepare('INSERT INTO Tournament_Stages(tournament, stage_index, name) VALUES (:t_id, 1, "GROUP")')
            query.bindValue(':t_id', tournament_id)
            self.execute_query(query)
            ts_id = self.get_current_id('Tournament_Stages')

            local_update_queue.append(self.create_remote_update('insert', 'Tournament_Stages',
                                                                ['id', 'tournament', 'stage_index', 'name'],
                                                                [[ts_id], [tournament_id], [1], ['GROUP']]
                                                                ))

            query.prepare('INSERT INTO Group_Stages(tournament_stage) VALUES (:ts_id)')
            query.bindValue(':ts_id', ts_id)
            self.execute_query(query)

            local_update_queue.append(self.create_remote_update('insert', 'Group_Stages',
                                                                ['tournament_stage'],
                                                                [[ts_id]]
                                                                ))

            query.prepare('INSERT INTO Groups(group_stage, size, name) VALUES(:gs_id, :size, :name)')
            for g in range(0, int(math.ceil(len(data['teams'])/int(data['group_size'])))):
                query.bindValue(':gs_id', ts_id)
                query.bindValue(':size', data['group_size'])
                query.bindValue(':name', str(chr(g+65)))
                self.execute_query(query)
                g_id = self.get_current_id('Groups')

                local_update_queue.append(self.create_remote_update('insert', 'Groups',
                                                                    ['id', 'group_stage', 'size', 'name'],
                                                                    [[g_id], [ts_id], [data['group_size']], [str(chr(g+65))]]
                                                                    ))

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

                local_update_queue.append(self.create_remote_update('insert', 'Tournament_Stages',
                                                                    ['id', 'tournament', 'stage_index', 'name'],
                                                                    [[ts_id], [tournament_id], [index],
                                                                     [query.boundValue(':name')]]
                                                                    ))

                query.prepare('INSERT INTO KO_Stages(tournament_stage) VALUES (:ts_id)')
                query.bindValue(':ts_id', ts_id)
                self.execute_query(query)

                local_update_queue.append(self.create_remote_update('insert', 'KO_Stages',
                                                                    ['tournament_stage'],
                                                                    [[ts_id]]
                                                                    ))
                index += 1
                teams_in_ko /= 2

            # add teams
            # maybe we can skip the query with the id information
            query.exec_('SELECT * FROM Teams')
            db_teams = {}
            while query.next():
                db_teams[query.value('name')] = query.value('id')
            for team in data['teams']:
                if team['name'] in db_teams:
                    team_id = db_teams[team['name']]
                else:
                    query.prepare('INSERT INTO Teams(name) VALUES(:team)')
                    query.bindValue(':team', team['name'])
                    self.execute_query(query)
                    team_id = self.get_current_id('Teams')

                    local_update_queue.append(self.create_remote_update('insert', 'Teams',
                                                                        ['id', 'name'],
                                                                        [[team_id], [team['name']]]
                                                                        ))

                query.prepare('INSERT INTO Tournament_Teams(tournament, team) VALUES(:tour_id, :team_id)')
                query.bindValue(':tour_id', tournament_id)
                query.bindValue(':team_id', team_id)
                self.execute_query(query)

                local_update_queue.append(self.create_remote_update('insert', 'Tournament_Teams',
                                                                    ['tournament', 'team'],
                                                                    [[tournament_id], [team_id]]
                                                                    ))

            self.db.commit()
            print('added %s to db' % data['name'])
            self.remote_queue.extend(local_update_queue)
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