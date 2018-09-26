import math
from collections import OrderedDict

from tools import DataBaseManager, InsertNotUniqueException
import csv


flunky_rocks = {'2015': '*{background-color: rgb(30,143,158); color: rgb(0,0,80)}'
                        '*[bg_img]{background-image: url(bg_imgs/2015.png)}'
                        'QLabel, QLineEdit, QRadioButton{background-color: rgba(255, 255, 255, 0)} '
                        '*[transp_bg="true"]{background-color: rgba(255, 255, 255, 0)}',
                '2016': '*{background-color: rgb(70,190,130); color: rgb(0,80,0)}'
                        '*[bg_img]{background-image: url(bg_imgs/2016.png)}'
                        'QLabel, QLineEdit, QRadioButton{background-color: rgba(255, 255, 255, 0)} '
                        '*[transp_bg="true"]{background-color: rgba(255, 255, 255, 0)}',
                '2017': '*{background-color: rgb(174,56,52); color: rgb(255,255,255)} '
                        '*[highlighted]{color: rgb(40,154,183)}'
                        '*[bg_img]{background-image: url(bg_imgs/2017.png)}'
                        'QLabel, QLineEdit, QRadioButton{background-color: rgba(255, 255, 255, 0)} '
                        '*[transp_bg="true"]{background-color: rgba(255, 255, 255, 0)}'}

database = DataBaseManager()

for year in sorted(flunky_rocks.keys()):
    groups = OrderedDict()
    matches = OrderedDict()
    teams = OrderedDict()
    ko_stages = OrderedDict()
    finals = OrderedDict()

    with open('%s.csv' % year, 'r', encoding='utf-8') as csv_file:
        reader = csv.reader(csv_file, delimiter=';', quotechar='"')
        for row in reader:
            team1 = row[0]
            team2 = row[1]
            score1 = row[2]
            score2 = row[3]
            # year = row[4]
            stage = row[5]
            if team1 not in teams.keys():
                teams[team1] = None
            if team2 not in teams.keys():
                teams[team2] = None
            if stage.startswith('KO'):
                if stage.startswith('KO_FINAL'):  # THERE CAN NEVER BE TWO IDENTICAL FINALS
                    finals[stage] = -1  # empty-stage-id
                    matches[stage] = []
                elif stage not in ko_stages:
                    ko_stages[stage] = -1  # empty-stage-id
                    matches[stage] = []
            else:
                if stage not in groups:
                    groups[stage] = []
                    matches[stage] = []
                if team1 not in groups[stage]:
                    groups[stage].append(team1)
                if team2 not in groups[stage]:
                    groups[stage].append(team2)
            matches[stage].append({'team1': team1, 'team2': team2,
                                   'score1': score1, 'score2': score2,
                                   })

    for team in teams:
        try:
            team_id = database.add_team(team)
        except InsertNotUniqueException as inu:
            team_id = database.get_team_id(team)

        # print(team, team_id)
        teams[team] = team_id

    group_size = int(math.ceil(float(len(teams)) / float(len(groups))))

    data = {'group_size': group_size,
            'name': 'FlunkyRock %s' % year,
            'stylesheet': flunky_rocks[year],
            'teams': teams,
            'groups': groups,
            'ko_stages': ko_stages,
            'finals': finals,
            'matches': matches}
    database.import_two_stage_tournament(data)
