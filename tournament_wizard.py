from PyQt5.QtWidgets import QWizard, QWizardPage, QComboBox, QVBoxLayout, QLabel, QLineEdit, QSpinBox, QFormLayout, \
    QStyle


class TournamentWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Create Tournament')
        self.setWindowIcon(self.style().standardIcon(getattr(QStyle, 'SP_FileDialogNewFolder')))
        self.setStyleSheet('background-color: rgb(51,124,99); font-family: Helvetica; font-weight: bold; '
                           'color: rgb(255,255,255)')
        self.addPage(NamePage(self))
        self.addPage(TeamPage(self))
        # self.button(QWizard.NextButton).clicked.connect(self.print_current)
        # self.button(QWizard.FinishButton).clicked.connect(self.print_current)

    # def print_current(self):
        # print(self.currentPage())


class NamePage(QWizardPage):
    def __init__(self, parent=None):
        super(NamePage, self).__init__(parent)
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setText('Flunkyrock 2018')
        self.spinBox = QSpinBox(self)
        self.spinBox.setMinimum(2)

        self.comboBox = QComboBox(self)
        self.comboBox.addItem("ipsum", 101)
        self.comboBox.addItem("dolor", 221)
        self.comboBox.addItem("sit", 31)
        layout = QFormLayout()
        layout.addRow(QLabel('Tournament Name:'), self.lineEdit)
        layout.addRow(QLabel('Number of Teams:'), self.spinBox)
        layout.addRow('Lorem', self.comboBox)
        self.setLayout(layout)

    def print_selection(self):
        print(self.comboBox.currentData())


class TeamPage(QWizardPage):
    def __init__(self, parent=None):
        super(TeamPage, self).__init__(parent)
        self.label1 = QLabel()
        self.label2 = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self.label1)
        layout.addWidget(self.label2)
        self.setLayout(layout)

    def initializePage(self):
        self.label1.setText("amet, consectetur adipisici ")
        self.label2.setText("elit, sed eiusmod tempor incidunt")
