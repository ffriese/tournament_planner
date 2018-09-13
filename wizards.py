from PyQt5.QtCore import QSortFilterProxyModel, Qt
from PyQt5.QtWidgets import QWizard, QWizardPage, QComboBox, QLabel, QLineEdit, QSpinBox, QFormLayout, \
    QStyle, QListWidgetItem, QListWidget, \
    QCompleter, QSizePolicy, QGridLayout


class TournamentWizard(QWizard):
    def __init__(self, teams):
        super().__init__()
        self.setWindowTitle('Create Tournament')
        self.setWindowIcon(self.style().standardIcon(getattr(QStyle, 'SP_FileDialogNewFolder')))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; '
                           'color: rgb(255,255,255)')
        self.namePage = NamePage([t['name'] for t in teams], parent=self)
        self.tournamentSettingsPage = TournamentSettingsPage(self)
        self.addPage(self.namePage)
        self.addPage(self.tournamentSettingsPage)
        self.accepted.connect(self.print_current)

    def print_current(self):
        print([self.namePage.teamTable.itemWidget(self.namePage.teamTable.item(i)).currentText()
               for i in range(0, self.namePage.teamTable.count())])


class NamePage(QWizardPage):
    def __init__(self, teams, parent=None):
        super(NamePage, self).__init__(parent)
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setText('FlunkyRock 2018')
        self.spinBox = QSpinBox(self)
        self.spinBox.setMinimum(4)
        self.spinBox.setValue(12)
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
            self.teamTable.addItem(item)
            self.teamTable.setItemWidget(item, team_item)
            item.setSizeHint(team_item.sizeHint())
        while self.spinBox.value() < self.teamTable.count():
            self.teamTable.takeItem(self.teamTable.count()-1)
        self.team_selected()

    def team_selected(self):
        selections = {}
        for i in range(0, self.teamTable.count()):
            item = self.teamTable.itemWidget(self.teamTable.item(i))

            item.blockSignals(True)
            if item.currentText() in selections.values() and item.currentText() != '':
                selections[item] = str(item.currentText())+' (2)'
            else:
                selections[item] = str(item.currentText())
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
    def __init__(self, parent=None):
        super(TournamentSettingsPage, self).__init__(parent)
        self.setLayout(QFormLayout())
        self.groupSpinBox = QSpinBox()
        self.finalComboBox = QComboBox()
        self.estimatedGamesLabel = QLabel()
        self.layout().addRow(QLabel('Number of Groups:'), self.groupSpinBox)
        self.layout().addRow(QLabel('First KO-Round:'), self.finalComboBox)
        self.layout().addRow(QLabel('Estimated # of Games:'), self.estimatedGamesLabel)


#  ----------------------------------------------------------------------------
#
#  FilteringComboBox class taken from http://www.gulon.co.uk/2013/05/07/a-filtering-qcombobox/
#
#  "THE BEER-WARE LICENSE" (Revision 42):
#  Rob Kent from http://www.gulon.co.uk wrote this class.  As long as you retain this notice you
#  can do whatever you want with this stuff. If we meet some day, and you think
#  this stuff is worth it, you can buy me a beer in return.
#  ----------------------------------------------------------------------------


class FilteringComboBox(QComboBox):
    def __init__(self, parent=None, *args):
        QComboBox.__init__(self, parent, *args)
        self.setEditable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setSourceModel(self.model())

        self._completer = QCompleter(self._proxy, self)
        self._completer.activated.connect(self.on_completer_activated)
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        p = self._completer
        stylesheet = self.styleSheet()
        while p.parent() is not None:
            stylesheet = p.parent().styleSheet()
            p = p.parent()

        self._completer.popup().setStyleSheet(stylesheet)
        self.setCompleter(self._completer)

        self.lineEdit().textEdited.connect(self._proxy.setFilterFixedString)

    def on_completer_activated(self, text):
        if not text: return
        self.setCurrentIndex(self.findText(text))
        self.activated[str].emit(self.currentText())

