import math
from PyQt5.QtCore import QSortFilterProxyModel, Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPainter, QPixmap, QColor, QImage
from PyQt5.QtWidgets import QWizard, QWizardPage, QComboBox, QLabel, QLineEdit, QSpinBox, QFormLayout, \
    QStyle, QListWidgetItem, QListWidget, \
    QCompleter, QSizePolicy, QGridLayout

from widgets import FilteringComboBox


class TournamentWizard(QWizard):

    tournament_created = pyqtSignal(dict)

    def __init__(self, teams):
        super().__init__()
        self.setWindowTitle('Create Tournament')
        self.setWindowIcon(QIcon('icons/application_add'))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; '
                           'color: rgb(255,255,255)')
        self.resize(700, 700)
        self.namePage = NamePage([t['name'] for t in teams], parent=self)
        self.tournamentSettingsPage = TournamentSettingsPage(self)
        self.addPage(self.namePage)
        self.addPage(self.tournamentSettingsPage)
        self.accepted.connect(self.create_tournament)

        self.namePage.team_num_changed_signal.connect(self.tournamentSettingsPage.num_teams_changed)
        self.tournamentSettingsPage.num_teams_changed(self.namePage.spinBox.value())

    def create_tournament(self):
        data = {
                'name': self.namePage.lineEdit.text(),
                # todo: create style-selector
                'stylesheet':  'background-color: rgb(161,58,139); color: rgb(255,255,255)',
                'teams': [self.namePage.teamTable.itemWidget(self.namePage.teamTable.item(i)).currentText()
                          for i in range(0, self.namePage.teamTable.count())],
                'group_size': int(self.tournamentSettingsPage.groupComboBox.currentData()),
                'teams_in_ko': int(self.tournamentSettingsPage.finalComboBox.currentData())
                }
        self.tournament_created.emit(data)


class NamePage(QWizardPage):
    team_num_changed_signal = pyqtSignal(int)

    def __init__(self, teams, parent=None):
        super(NamePage, self).__init__(parent)
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setText('FlunkyRock 2018')
        self.spinBox = QSpinBox(self)
        self.spinBox.setMinimum(4)
        self.spinBox.setValue(16)
        self.spinBox.valueChanged.connect(self.num_teams_changed)

        self.teamTable = QListWidget(self)

        self.teams = teams

        layout = QGridLayout()
        layout.addWidget(QLabel('Tournament Name:'), 0, 0)
        layout.addWidget(self.lineEdit, 0, 1)
        layout.addWidget(QLabel('Number of Teams:'), 1, 0)
        layout.addWidget(self.spinBox, 1, 1)
        self.teamLabel = QLabel('Teams:\n\n(team names can\nalso be manually\nadded later on)')
        self.teamLabel.setAlignment(Qt.AlignTop)
        layout.addWidget(self.teamLabel, 2, 0)
        layout.addWidget(self.teamTable, 2, 1)

        self.setLayout(layout)
        self.num_teams_changed()

    def num_teams_changed(self):
        while self.spinBox.value() > self.teamTable.count():
            item = QListWidgetItem(self.teamTable)
            team_item = FilteringComboBox(self)
            team_item.currentTextChanged.connect(self.team_selected)
            px = QPixmap(16, 16)
            px.fill(QColor(0, 0, 0, 0))
            painter = QPainter()
            painter.begin(px)
            painter.drawText(0, 0, 16, 16, Qt.AlignRight | Qt.AlignVCenter, str(self.teamTable.count()))
            painter.end()
            item.setIcon(QIcon(px))
            self.teamTable.addItem(item)
            self.teamTable.setItemWidget(item, team_item)
            item.setSizeHint(team_item.sizeHint())
        while self.spinBox.value() < self.teamTable.count():
            self.teamTable.takeItem(self.teamTable.count()-1)
        self.team_selected()
        self.team_num_changed_signal.emit(self.spinBox.value())

    def team_selected(self):
        selections = {}
        for i in range(0, self.teamTable.count()):
            item = self.teamTable.itemWidget(self.teamTable.item(i))

            item.blockSignals(True)
            if item.currentText() in selections.values() and item.currentText() != '':
                selections[item] = item.currentText()+' (2)'
            else:
                selections[item] = item.currentText()
            item.clear()
            item.blockSignals(False)
        for i in range(0, self.teamTable.count()):
            item = self.teamTable.itemWidget(self.teamTable.item(i))
            item.blockSignals(True)
            item.addItem('')
            for t in self.teams:
                if t not in selections.values() or selections[item] == t:
                    item.addItem(t)
            item.setCurrentText(selections[item])
            item.blockSignals(False)


class TournamentSettingsPage(QWizardPage):
    final_names = {
        2: 'Final',
        4: 'Semi-Final',
        8: 'Quarter-Final',
        16: 'Round of 16',
        32: 'Round of 32',
        64: 'Round of 64'
    }

    def __init__(self, parent=None):
        super(TournamentSettingsPage, self).__init__(parent)
        self.num_teams = 0
        self.setLayout(QFormLayout())
        self.groupComboBox = QComboBox()
        self.finalComboBox = QComboBox()
        self.maxGamesLabel = QLabel()
        self.layout().addRow(QLabel('Group size:'), self.groupComboBox)
        self.layout().addRow(QLabel('Teams in KO Round:'), self.finalComboBox)
        self.layout().addRow(QLabel('Max # of Games:'), self.maxGamesLabel)
        self.groupComboBox.currentTextChanged.connect(self.estimate_games)
        self.finalComboBox.currentTextChanged.connect(self.estimate_games)

    def num_teams_changed(self, num_teams):
        self.num_teams = num_teams

        self.finalComboBox.clear()
        for i in range(2, self.num_teams+1):
            if (i & (i - 1)) == 0:
                self.finalComboBox.addItem('%r (%s)' % (i, self.final_names[i]), i)

        self.groupComboBox.clear()
        choices = self.compute_group_size_scores()
        for choice in choices:
            self.groupComboBox.addItem('%r (%r Groups, %r open Slots)' %
                                       (choice[1]['size'], choice[1]['groups'], choice[1]['open_slots']),
                                       choice[1]['size'])
            if choice[0] == 0:
                self.groupComboBox.setItemData(self.groupComboBox.count()-1, QColor.green, Qt.BackgroundRole)

    def compute_group_size_scores(self):
        choices = []
        for group_size in range(3, self.num_teams+1).__reversed__():

            rest = self.num_teams % group_size
            num_groups = float(self.num_teams) / float(group_size)
            prev_g = float(self.num_teams) / float(group_size - 1)
            groups = math.ceil(num_groups)
            open_slots = (groups * group_size) - self.num_teams

            score = - open_slots
            if groups > 1:
                score -= (groups % 2) * 2

            if group_size < 4:
                score -= 4 - group_size
            elif group_size > 5:
                score -= group_size - 5

            if num_groups < 1 or \
                    (0 < rest < (group_size / 2.0)) or groups == math.ceil(prev_g):
                pass
            else:
                choices.append((score, {'size': group_size, 'groups': groups, 'open_slots': open_slots}))
                # print('    %s   |  %s   | %s   |  %s' % (groups, group_size,
                #                                         open_slots, score))
        choices = sorted(choices, key=lambda x: x[0])
        choices.reverse()
        return choices

    def estimate_games(self):
        if self.finalComboBox.currentData() is not None and self.groupComboBox.currentData() is not None:
            est_games = int(math.log2(int(self.finalComboBox.currentData())))+int(self.groupComboBox.currentData())-1
            self.maxGamesLabel.setText(str(est_games))


