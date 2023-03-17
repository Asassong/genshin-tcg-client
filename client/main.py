import json
import sys
from typing import Optional
from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel, QFrame, QVBoxLayout, \
                            QHBoxLayout, QGridLayout, QWidget, QPushButton, QMenu, QMessageBox
from PyQt6.QtNetwork import QUdpSocket, QHostAddress
from PyQt6.QtGui import QPixmap, QFont, QFontDatabase, QMouseEvent, QAction, QActionGroup, QDrag, QDragMoveEvent, \
                        QDragEnterEvent, QDropEvent
from PyQt6.QtCore import Qt, QMimeData, QTimer

class Gcg(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Genius Invokation TCG")
        self.main_widget = QWidget(self)
        self.main_widget.setStyleSheet("border-image: url(./resources/background/background.png)")
        QFontDatabase.addApplicationFont("./resources/genshin.ttf")  # 'HYWenHei-85W'
        menu = self.menuBar()
        menu.setStyleSheet("font-family: 'HYWenHei-85W'; font-size: 10pt; color: black;")
        game_menu = menu.addMenu("游戏")
        start_game = QAction("开始游戏", self)
        game_menu.addAction(start_game)
        start_game.triggered.connect(self.start_game)
        # self.choose_mode = QMenu("选择模式", self)
        # game_menu.addMenu(self.choose_mode)
        # mode1 = QAction("Game1", self)
        # mode1.setCheckable(True)
        # self.choose_mode.addAction(mode1)
        self.choose_deck = QMenu("选择牌组", self)
        game_menu.addMenu(self.choose_deck)
        self.player_chose_deck = None
        self.all_deck = QActionGroup(self)
        self.all_deck.triggered.connect(self.on_deck_chosen)
        self.init_choose()
        exit_game = QAction("退出", self)
        game_menu.addAction(exit_game)
        edit_menu = menu.addMenu("编辑")
        edit_deck = QAction("编辑牌组", self)
        edit_menu.addAction(edit_deck)
        edit_card = QAction("编辑卡牌", self)
        edit_menu.addAction(edit_card)
        edit_background = QAction("编辑背景", self)
        edit_menu.addAction(edit_background)
        self.diceNum = QLabel(self)
        self.diceNum.setObjectName("diceNum")
        self.diceNum.setStyleSheet("#diceNum{border-image: url(resources/images/own-dice-icon.png);color: white}")
        self.diceNum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diceNum.hide()
        self.oppoDiceNum = QLabel(self)
        self.oppoDiceNum.setObjectName("oppose_dice_num")
        self.oppoDiceNum.setStyleSheet(
            "#oppose_dice_num{border-image: url(./resources/images/oppo-dice-icon.png);color: white}")
        self.oppoDiceNum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.oppoDiceNum.hide()
        self.oppoCardNum = QLabel(self)
        self.oppoCardNum.setObjectName("oppo_card_num")
        self.oppoCardNum.setStyleSheet(
            "#oppo_card_num{border-image: url(./resources/images/card-num-icon.png);color: white}")
        self.oppoCardNum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.oppoCardNum.hide()
        self.card_zone = CardZone(self)
        self.skill_zone = SkillZone(self)
        self.summonZone = SummonZone(self)
        self.supportZone = SupportZone(self)
        self.oppoSupportZone =SupportZone(self)
        self.oppoSummonZone = SummonZone(self)
        self.dice_zone = DiceZone(self)
        self.character_zone = CharacterZone(self, "player")
        self.oppose_character_zone = CharacterZone(self, "oppose")
        self.end_round_button = QPushButton(self)
        self.end_round_button.setObjectName("end_round_button")
        self.end_round_button.setStyleSheet("#end_round_button{"
                                            "border-image: url(./resources/images/time-clock-icon.png);}"
                                            "#end_round_button:disabled"
                                            "{border-image: url(./resources/images/time-clock-grey.png);}")
        self.end_round_button.clicked.connect(self.round_end)
        self.end_round_button.setEnabled(False)
        self.end_round_button.hide()
        self.change_char_button = ChangeButton(self)
        self.change_char_button.hide()
        self.commit_button = CommitButton(self)
        self.commit_button.clicked.connect(self.commit_operation)
        self.commit_button.hide()
        self._server_port = 4095
        self._localhost = QHostAddress()
        self._localhost.setAddress("127.0.0.1")
        self._socket = QUdpSocket(self)
        self._socket.bind(self._localhost, 0)
        self._socket.readyRead.connect(self.socket_recv)
        self.redraw = Redraw(self)
        self.redraw.hide()
        self.reroll = Reroll(self)
        self.reroll.hide()
        self.setAcceptDrops(True)
        self.action_phase_start = False
        self.action_state = ""
        self.selectedCard: Optional[HandCard] = None
        self.choose_target_index = -1
        self.choose_target_type = ""
        self.resize(1280, 720)
        self.resize_timer = QTimer(self)
        self.resize_timer.setInterval(100)
        self.resize_timer.timeout.connect(self.on_resize_finished)

    def socket_recv(self):
        while self._socket.hasPendingDatagrams():
            datagram, _, port = self._socket.readDatagram(self._socket.pendingDatagramSize())
            if port != self._server_port:
                data: str = datagram.decode()
                data: dict = eval(data)
                if data["message"] == "game start":
                    self._server_port = port
            self.handle_recv(datagram)

    def socket_send(self, info: str):
        print("send", info)
        self._socket.writeDatagram(info.encode(), self._localhost, self._server_port)

    def handle_recv(self, datagram: bytes):
        data: str = datagram.decode()
        data: dict = eval(data)
        message = data["message"]
        if message == "init_character":
            self.character_zone.add_widget(data["character_name"], data["hp"], data["energy"], data["position"])
        elif message == "init_oppo_character":
            self.oppose_character_zone.add_widget(data["character_name"], data["hp"], data["energy"], data["position"])
        elif message == "choose mode":
            self.socket_send(str({"message": "selected mode", "mode": "Game1"}))
        elif message == "send deck":
            config = self.read_json("config.json")
            if self.player_chose_deck is not None:
                deck = config[self.player_chose_deck]
                deck_message = {"message": "check deck", "character": deck["character"], "card": deck["card"]}
                self.socket_send(str(deck_message))
        elif message == "change_energy":
            position = data["position"]
            energy = data["energy"]
            character = self.character_zone.get_character(position)
            character.change_energy(energy)
        elif message == "change_oppose_energy":
            position = data["position"]
            energy = data["energy"]
            character = self.oppose_character_zone.get_character(position)
            character.change_energy(energy)
        elif message == "redraw":
            self.redraw.show()
            self.redraw.raise_()
            self.redraw.add_cards(data["card_name"], data["card_cost"])
        elif message == "select_character":
            self.action_state = "select_character"
            self.change_char_button.show()
        elif message == "choose_target":
            target_type = data["target_type"]
            self.choose_target_type = target_type
            if target_type == "character":
                self.character_zone.enable_choose_target = True
            elif target_type == "summon":
                self.summonZone.change_enable_choose_target(True)
            elif target_type == "support":
                self.supportZone.change_enable_choose_target(True)
            elif target_type == "oppose_character":
                self.oppose_character_zone.enable_choose_target = True
            elif target_type == "oppose_summon":
                self.oppoSummonZone.change_enable_choose_target(True)
            elif target_type == "oppose_support":
                self.oppoSupportZone.change_enable_choose_target(True)
            self.commit_button.update_text()
            self.commit_button.setEnabled(True)
        elif message == "player_change_active":
            self.character_zone.change_active(data["from_index"], data["to_index"])
        elif message == "oppose_change_active":
            self.oppose_character_zone.change_active(data["from_index"], data["to_index"])
        elif message == "add_card":
            self.card_zone.raise_()
            card_name = data["card_name"]
            card_cost = data["card_cost"]
            for index, card in enumerate(card_name):
                card = card.replace(" ", "")
                self.card_zone.add_card(card, card_cost[index])
        elif message == "remove_card":
            self.card_zone.remove_card(data["card_index"])
        elif message == "reroll":
            self.reroll.show()
            self.reroll.raise_()
            self.reroll.show_dice(data["now_dice"])
        elif message == "oppose_card_num":
            self.oppoCardNum.setText(str(data["num"]))
        elif message == "show_dice_num":
            self.diceNum.setText(str(data["num"]))
        elif message == "show_oppose_dice_num":
            self.oppoDiceNum.setText(str(data["num"]))
        elif message == "add_dice":
            for dice in data["dices"]:
                self.dice_zone.add_dice(dice)
        elif message == "clear_dice":
            self.dice_zone.clear()
        elif message == "action_phase_start":
            self.end_round_button.setEnabled(True)
            self.action_phase_start = True
        elif message == "act_end":
            self.end_round_button.setEnabled(False)
            self.action_phase_start = False
        elif message == "highlight_dice":
            self.dice_zone.auto_highlight(data["dice_indexes"])
            self.commit_button.show()
            self.commit_button.setEnabled(True)
        elif message == "enable_commit":
            self.commit_button.setEnabled(True)
        elif message == "remove_dice":
            self.dice_zone.remove_dice(data["dices"])
        elif message == "init_skill":
            for skill_name, skill_cost in zip(data["skill_name"], data["skill_cost"]):
                self.skill_zone.add_widget(skill_name, skill_cost)
        elif message == "clear_skill":
            self.skill_zone.clear()
        elif message == "change_application":
            character = self.character_zone.get_character(data["position"])
            character.change_application(data["application"])
        elif message == "oppose_change_application":
            character = self.oppose_character_zone.get_character(data["position"])
            character.change_application(data["application"])
        elif message == "change_hp":
            character = self.character_zone.get_character(data["position"])
            character.change_hp(data["hp"])
        elif message == "change_oppose_hp":
            character = self.oppose_character_zone.get_character(data["position"])
            character.change_hp(data["hp"])
        elif message == "change_equip":
            character = self.character_zone.get_character(data["position"])
            character.change_equip(data["equip"])
        elif message == "change_oppose_equip":
            character = self.oppose_character_zone.get_character(data["position"])
            character.change_equip(data["equip"])
        elif message == "add_support":
            self.supportZone.add_widget(data["support_name"], data["num"])
        elif message == "oppose_add_support":
            self.oppoSupportZone.add_widget(data["support_name"], data["num"])
        elif message == "change_support_count":
            self.supportZone.change_support_count(data["support_index"], data["count"])
        elif message == "change_oppose_support_count":
            self.oppoSupportZone.change_support_count(data["support_index"], data["count"])
        elif message == "change_skill_state":
            self.skill_zone.update_skill_state(data["skill_cost"], data["skill_state"])
        elif message == "hide_oppose":
            self.oppoCardNum.hide()
            self.oppoDiceNum.hide()
            self.oppoSupportZone.hide()
            self.oppose_character_zone.hide()
        elif message == "show_oppose":
            self.oppoCardNum.show()
            self.oppoDiceNum.show()
            self.oppoSupportZone.show()
            self.oppose_character_zone.show()
        elif message == "add_summon":
            self.summonZone.add_widget(data["summon_name"], data["usage"], data["effect"])
        elif message == "oppose_add_summon":
            self.oppoSummonZone.add_widget(data["summon_name"], data["usage"], data["effect"])
        elif message == "change_sumon_usage":
            self.summonZone.change_summon_count(data["index"], data["usage"])
        elif message == "change_oppose_sumon_usage":
            self.oppoSummonZone.change_summon_count(data["index"], data["usage"])
        elif message == "remove_summon":
            self.summonZone.remove_widget(data["index"])
        elif message == "remove_oppose_summon":
            self.oppoSummonZone.remove_widget(data["index"])
        elif message == "add_state":
            if data["type"] == "self":
                character = self.character_zone.get_character(data["store"])
                character.self_state.add_widget(data["state_name"], data["state_icon"], data["num"])
            elif data["type"] == "team":
                self.character_zone.add_team_state(data["state_name"], data["state_icon"], data["num"])
        elif message == "oppose_add_state":
            if data["type"] == "self":
                character = self.oppose_character_zone.get_character(data["store"])
                character.self_state.add_widget(data["state_name"], data["state_icon"], data["num"])
            elif data["type"] == "team":
                self.oppose_character_zone.add_team_state(data["state_name"], data["state_icon"], data["num"])
        elif message == "change_state_usage":
            if data["type"] == "self":
                character = self.character_zone.get_character(data["store"])
                character.self_state.update_state(data["state_name"], data["num"])
            elif data["type"] == "team":
                self.character_zone.update_team_state(data["state_name"], data["num"])
        elif message == "change_oppose_state_usage":
            if data["type"] == "self":
                character = self.oppose_character_zone.get_character(data["store"])
                character.self_state.update_state(data["state_name"], data["num"])
            elif data["type"] == "team":
                self.oppose_character_zone.update_team_state(data["state_name"], data["num"])
        elif message == "remove_state":
            if data["type"] == "self":
                character = self.character_zone.get_character(data["store"])
                character.self_state.remove_widget(data["state_name"])
            elif data["type"] == "team":
                self.character_zone.remove_team_state(data["state_name"])
        elif message == "remove_oppose_state":
            if data["type"] == "self":
                character = self.oppose_character_zone.get_character(data["store"])
                character.self_state.remove_widget(data["state_name"])
            elif data["type"] == "team":
                self.oppose_character_zone.remove_team_state(data["state_name"])
        elif message == "zero_cost":
            self.zero_cost()
        elif message == "block_action":
            if self.action_state == "play_card" or self.action_state == "element_tuning":
                self.card_zone.cancel_drag()
                self.action_state = ""
                self.commit_button.hide()
        # else:
        print("recv", data)

    @staticmethod
    def init_card_picture(obj: QLabel, picture_name):
        picture = QPixmap("./resources/cards/%s.png" % picture_name)
        obj.setPixmap(picture)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.action_phase_start and self.action_state:
            obj = self.childAt(event.pos())
            if obj == self.main_widget:
                if self.action_state == "cost":
                    self.action_state = ""
                    self.dice_zone.auto_clear_highlight()
                    self.commit_button.hide()
                    self.socket_send(str({"message": "cancel"}))
                elif self.action_state == "play_card" or self.action_state == "element_tuning":
                    self.card_zone.cancel_drag()
                    self.dice_zone.auto_clear_highlight()
                    self.commit_button.hide()
                    self.action_state = ""
                    self.socket_send(str({"message": "cancel"}))
                elif self.action_state == "change_character":
                    self.change_char_button.hide()
                    self.action_state = ""

    def choose_character(self):
        index = self.character_zone.get_choose_index()
        if index is not None:
            if self.action_state == "change_character":
                self.socket_send(str({"message": "change_character", "character": index}))
                self.action_state = "cost"
            elif self.action_state == "select_character":
                self.socket_send(str({"message": "selected_character", "character_index": index}))
                self.action_state = ""
            self.character_zone.cancel_highlight(index)
            self.change_char_button.hide()
            
    def zero_cost(self):
        if self.action_state == "use_skill":
            self.skill_zone.choose.set_state(False)
        elif self.action_state == "play_card" or self.action_state == "element_tuning":
            self.card_zone.confirm_drag()
            if self.selectedCard is not None:
                self.selectedCard.deleteLater()
                self.selectedCard = None
        self.commit_button.hide()
        self.action_state = ""

    def commit_operation(self):
        if self.choose_target_type:
            index = self.choose_target_index
            if index != -1 and index is not None:
                self.socket_send(str({"message": "chose_target", "index": index}))
                if self.choose_target_type == "character":
                    self.character_zone.enable_choose_target = False
                    self.character_zone.cancel_highlight(index)
                elif self.choose_target_type == "summon":
                    self.summonZone.change_enable_choose_target(False)
                elif self.choose_target_type == "support":
                    self.supportZone.change_enable_choose_target(False)
                elif self.choose_target_type == "oppose_character":
                    self.oppose_character_zone.enable_choose_target = False
                    self.oppose_character_zone.cancel_highlight(index)
                elif self.choose_target_type == "oppose_summon":
                    self.oppoSummonZone.change_enable_choose_target(False)
                elif self.choose_target_type == "oppose_support":
                    self.oppoSupportZone.change_enable_choose_target(False)
                self.choose_target_type = ""
                if self.action_state:
                    self.commit_button.setEnabled(False)
                    self.commit_button.update_text()
                else:
                    self.commit_button.hide()
                self.choose_target_index = -1
        else:
            if self.action_state == "cost":
                choose = self.dice_zone.get_choose()
                self.action_state = ""
                self.socket_send(str({"message": "commit_cost", "cost": choose}))
                self.commit_button.hide()
            elif self.action_state == "use_skill":
                choose = self.dice_zone.get_choose()
                self.action_state = ""
                self.socket_send(str({"message": "commit_cost", "cost": choose}))
                self.commit_button.hide()
                self.skill_zone.choose.set_state(False)
            elif self.action_state == "play_card" or self.action_state == "element_tuning":
                choose = self.dice_zone.get_choose()
                self.action_state = ""
                self.socket_send(str({"message": "commit_cost", "cost": choose}))
                self.commit_button.hide()
                self.card_zone.confirm_drag()
                if self.selectedCard is not None:
                    self.selectedCard.deleteLater()
                    self.selectedCard = None

    def round_end(self):
        self.socket_send(str({"message": "round_end"}))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.action_phase_start:
            card: HandCard = event.source()
            self.card_zone.record_being_dragged(card)
            card.setParent(self)
            event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        card = event.source()
        x = event.position().x() - card.width() / 2
        y = event.position().y() - card.height() / 2
        event.accept()
        card.move(int(x), int(y))
        card.show()

    def dropEvent(self, event: QDropEvent) -> None:
        card = event.source()
        x = event.position().x() - card.width() / 2
        y = event.position().y() - card.height() / 2
        event.accept()
        width = self.width()
        height = self.height()
        selected_card = self.card_zone.get_select()
        if x > width * 0.8:
            self.action_state = "element_tuning"
            if selected_card is not None:
                card.hide()
                self.socket_send(str({"message": "element_tuning", "card_index": selected_card}))
                self.commit_button.show()
                self.commit_button.setEnabled(False)
                self.selectedCard = card
        elif y > height * 0.8:
            self.card_zone.cancel_drag()
        else:
            self.action_state = "play_card"
            if selected_card is not None:
                card.hide()
                self.socket_send(str({"message": "play_card", "card_index": selected_card}))
                self.commit_button.show()
                self.commit_button.setEnabled(False)
                self.selectedCard = card

    @staticmethod
    def read_json(file: str) -> dict[str]:
        with open(file, "r", encoding="utf-8") as f:
            text = json.load(f)
        return text

    def init_choose(self):
        config = self.read_json("config.json")
        for key, value in config.items():
            deck = QAction(key, self)
            deck.setCheckable(True)
            deck.setActionGroup(self.all_deck)
            self.choose_deck.addAction(deck)

    def start_game(self):
        if self.player_chose_deck is None:
            QMessageBox.about(self, "提示", "未选择牌组")
        else:
            self.socket_send(str({"message": "connect request", "nickname": "test"}))
            self.end_round_button.show()
            self.oppoCardNum.show()
            self.diceNum.show()
            self.oppoDiceNum.show()

    def on_deck_chosen(self, action):
        if action.isChecked():
            self.player_chose_deck = action.text()
        else:
            self.player_chose_deck = None

    def resizeEvent(self, event) -> None:
        self.resize_timer.stop()
        self.resize_timer.start()

    def on_resize_finished(self):
        self.resize_timer.stop()
        width = self.width()
        height = self.height()
        self.main_widget.resize(width, height)
        self.diceNum.move(int(0.015 * width), int(0.58 * height))
        self.diceNum.resize(int(0.03 * width), int(0.03 * width))
        self.diceNum.setFont(QFont('HYWenHei-85W', int(0.01 * width)))
        self.oppoDiceNum.move(int(0.012 * width), int(0.35 * height))
        self.oppoDiceNum.resize(int(0.03 * width), int(0.03 * width))
        self.oppoDiceNum.setFont(QFont('HYWenHei-85W', int(0.01 * width)))
        self.oppoCardNum.move(int(0.012 * width), int(0.3 * height))
        self.oppoCardNum.resize(int(0.03 * width), int(0.03 * width))
        self.oppoCardNum.setFont(QFont('HYWenHei-85W', int(0.01 * width)))
        self.commit_button.resize(int(width * 0.1), int(height * 0.05))
        self.commit_button.move(int(width * 0.45), int(height * 0.81))
        self.commit_button.setFont(QFont('HYWenHei-85W', int(0.008 * width)))
        self.character_zone.auto_resize()
        self.oppose_character_zone.auto_resize()
        self.end_round_button.move(int(0.006 * width), int(0.45 * height))
        self.end_round_button.resize(int(0.1 * height), int(0.1 * height))
        self.summonZone.move(int(0.70 * width), int(0.52 * height))
        self.oppoSummonZone.move(int(0.70 * width), int(0.15 * height))
        self.supportZone.move(int(0.15 * width), int(0.52 * height))
        self.oppoSupportZone.move(int(0.15 * width), int(0.15 * height))
        self.dice_zone.move(int(0.96 * width), int(0.1 * height))
        self.change_char_button.move(int(0.95 * width), int(0.8 * height))
        self.change_char_button.auto_resize()
        self.summonZone.auto_resize()
        self.oppoSummonZone.auto_resize()
        self.oppoSupportZone.auto_resize()
        self.supportZone.auto_resize()
        self.dice_zone.auto_resize()
        self.card_zone.auto_resize()
        self.skill_zone.auto_resize()
        self.reroll.auto_resize()
        self.redraw.auto_resize()

class ChangeButton(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.game = parent
        self.change_button = QPushButton(self)
        self.change_button.setObjectName("change_character")
        self.change_button.setStyleSheet("#change_character{border-image: url(./resources/change_character.png);}")
        self.change_button.clicked.connect(self.game.choose_character)
        self.cost = Cost(self, "ANY", 1)
        self.auto_resize()

    def change_cost(self, value):
        self.cost.change_cost(value)

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        self.resize(int(0.05 * parent_width), int(0.07 * parent_width))
        self.change_button.resize(int(0.05 * parent_width), int(0.05 * parent_width))
        self.cost.move(int(0.015 * parent_width), int(0.05 * parent_width))
        self.cost.auto_resize(int(0.02 * parent_width))

    def showEvent(self, event) -> None:
        if self.game.action_state == "select_character":
            self.cost.hide()
        elif self.game.action_state == "change_character":
            self.cost.show()

class CommitButton(QPushButton):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.setObjectName("commit")
        self.setStyleSheet("#commit{border-image: url(./resources/confirm-icon.png);color: rgb(59, 66, 85)}")
        self.game = parent

    def update_text(self):
        if self.game.choose_target_type:
            self.setText("确定")
        else:
            if self.game.action_state == "play_card":
                self.setText("打出卡牌")
            elif self.game.action_state == "element_tuning":
                self.setText("元素调和")
            elif self.game.action_state == "use_skill":
                self.setText("使用技能")
            else:
                self.setText("确定")

    def showEvent(self, event) -> None:
        self.update_text()

class CharacterZone(QWidget):
    def __init__(self, parent: Gcg, zone_type):
        super().__init__(parent)
        self.characters: list[CharacterCard] = []
        self.zone_type = zone_type
        self.active: Optional[CharacterCard] = None
        self.game = parent
        self.choose: Optional[CharacterCard] = None
        self.enable_choose_target = False
        self.auto_resize()

    def add_widget(self, character_name: str, hp: int, energy: tuple[int, int], index=None):
        new_character = CharacterCard(self, character_name, hp, energy)
        if index is None:
            self.characters.append(new_character)
        else:
            self.characters.insert(index, new_character)
        self.auto_resize()
        new_character.show()

    def change_active(self, from_index, to_index):
        self_width = self.width()
        self_height = self.height()
        character_num = len(self.characters)
        width = character_num - 0.2
        if from_index is not None:
            change_from = self.characters[from_index]
        else:
            change_from = None
        change_to = self.characters[to_index]
        self.active = change_to
        if self.zone_type == "player":
            if change_from is not None:
                change_from.move(int(from_index/width*self_width), int(5 / 36 * self_height))
            change_to.move(int(to_index / width * self_width), 0)
        elif self.zone_type == "oppose":
            if change_from is not None:
                change_from.move(int(from_index/width*self_width), 0)
            change_to.move(int(to_index / width * self_width), int(5 / 36 * self_height))
        if change_from is not None:
            change_to.team_state.transfer_state(change_from.team_state.states)
            change_from.team_state.states.clear()

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        character_num = len(self.characters)
        if character_num == 0:
            character_num = 1
        width = character_num * 0.08 + (character_num-1) * 0.02
        position_x = 0.5 - width / 2
        if self.zone_type == "player":
            self.move(int(position_x * parent_width), int(0.52 * parent_height))
        elif self.zone_type == "oppose":
            self.move(int(position_x * parent_width), int(0.12 * parent_height))
        self_width = int(width * parent_width)
        self_height = int(parent_height*0.36)
        self.resize(self_width, self_height)
        character_num = len(self.characters)
        width = character_num - 0.2
        for index, character in enumerate(self.characters):
            character_x = index / width
            character.auto_resize(int(parent_width * 0.08), int(parent_height * 0.31))
            if self.zone_type == "player":
                if character is self.active:
                    character.move(int(character_x * self_width), 0)
                else:
                    character.move(int(character_x * self_width), int(5 / 36 * self_height))
            elif self.zone_type == "oppose":
                if character is self.active:
                    character.move(int(character_x * self_width), int(5 / 36 * self_height))
                else:
                    character.move(int(character_x * self_width), 0)

    def get_choose_index(self):
        if self.choose is not None:
            return self.characters.index(self.choose)

    def get_character(self, index):
        return self.characters[index]

    def cancel_highlight(self, index):
        self.characters[index].picture.set_state(False)
        self.choose = None

    def add_team_state(self, state_name, icon_name, count):
        if self.active is not None:
            self.active.team_state.add_widget(state_name, icon_name, count)

    def update_team_state(self, state_name, count):
        if self.active is not None:
            self.active.team_state.update_state(state_name, count)

    def remove_team_state(self, state_name):
        if self.active is not None:
            self.active.team_state.remove_widget(state_name)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        obj = self.childAt(event.pos())
        if isinstance(obj, ClickableLabel) and isinstance(obj.parent(), CharacterCard):
            if self.choose is not None:
                if self.choose is not obj.parent():
                    self.choose.picture.set_state(False)
            if obj.get_state():
                self.choose = obj.parent()
            else:
                self.choose = None
            if self.enable_choose_target:
                self.game.choose_target_index = self.get_choose_index()
            elif self.zone_type == "player" and self.game.action_phase_start:
                if (self.choose is not self.active) and (self.choose is not None):
                    self.game.action_state = "change_character"
                    self.game.change_char_button.show()
                else:
                    self.game.action_state = "" if self.game.action_state == "change_character" else self.game.action_state
                    self.game.change_char_button.hide()

class CharacterCard(QFrame):
    def __init__(self, parent: CharacterZone, character_name: str, hp: int, energy: tuple[int, int]):
        super().__init__(parent)
        self.name = character_name
        self.parent = parent
        self.picture = ClickableLabel(self)
        self.picture.setScaledContents(True)
        self.application = AutoResizeWidget(self, 30, "h", "element")
        self.hp_icon = QLabel(self)
        self.hp_icon.setScaledContents(True)
        hp_pic = QPixmap("./resources/hp.png")
        self.hp_icon.setPixmap(hp_pic)
        self.hp = QLabel(self)
        self.hp.setStyleSheet('color: white')
        self.hp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equip = AutoResizeWidget(self, 30, "v", "equip")
        self.energy = AutoResizeWidget(self, 30, "v", "energy")
        self.self_state = StateManager(self)
        self.team_state = StateManager(self)
        self.init(character_name, hp, energy)

    def init(self, character_name: str, hp: int, energy: tuple[int, int]):
        character_name = character_name.replace(" ", "")
        picture = QPixmap("./resources/characters/%s.png" % character_name)
        self.picture.setPixmap(picture)
        self.change_hp(hp)
        self.change_energy(energy)

    def change_energy(self, energy: tuple[int, int]):
        self.energy.clear()
        now_energy, full = energy
        for _ in range(now_energy):
            self.energy.add_widget("fill")
        for _ in range(full - now_energy):
            self.energy.add_widget("empty")

    def change_hp(self, hp: int):
        self.hp.setText(str(hp))

    def is_chose(self) -> bool:
        if self.picture.get_state():
            self.picture.set_state(False)
            return True
        else:
            return False

    def change_equip(self, equipment: list):
        self.equip.clear()
        for equip in equipment:
            self.equip.add_widget(equip)

    def change_application(self, application: list):
        self.application.clear()
        for apply in application:
            self.application.add_widget(apply)

    def auto_resize(self, width, height):
        self.resize(width, height)
        self.picture.resize(width, int(height * 0.25 / 0.31))
        self.picture.move(0, int(height * 0.03 / 0.31))
        self.application.auto_resize(int(height * 0.03 / 0.31))
        self.hp_icon.resize(int(width / 4), int(height * 0.04 / 0.31))
        self.hp_icon.move(0, int(height * 0.03 / 0.31))
        self.hp.resize(int(width / 4), int(height * 0.04 / 0.31))
        self.hp.move(0, int(height * 0.03 / 0.31))
        self.hp.setFont(QFont('HYWenHei-85W', int(height * 0.02 / 0.31)))
        self.equip.auto_resize(int(height * 0.04 / 0.31))
        self.equip.move(0, int(height * 0.07 / 0.31))
        self.energy.move(int(width * 0.79), int(height * 0.06 / 0.31))
        self.energy.auto_resize(int(height * 0.04 / 0.31))
        self.self_state.move(0, int(height * 0.25 / 0.31))
        self.self_state.auto_resize(int(height * 0.03 / 0.31))
        self.team_state.move(0, int(height * 0.28 / 0.31))
        self.team_state.auto_resize(int(height * 0.03 / 0.31))

class Redraw(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.game = parent
        self.background = QFrame(self)
        self.background.setObjectName("redraw")
        self.background.setStyleSheet("#redraw{background-color:rgba(0, 0, 0, 127)}")
        self.commit = QPushButton(self)
        self.commit.setObjectName("commit")
        self.commit.setStyleSheet("#commit{border-image: url(./resources/confirm-icon.png);color: rgb(59, 66, 85)}")
        self.commit.setText("确定")
        self.card_zone = QWidget(self)
        self.lo = QHBoxLayout()
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.commit.clicked.connect(self.hide_ui)
        self.cards: list[Card] = []
        self.auto_resize()

    def add_cards(self, cards_name, cards_cost):
        for card_name, card_cost in zip(cards_name, cards_cost):
            card_name = card_name.replace(" ", "")
            new_card = Card(self, card_name, card_cost)
            self.cards.append(new_card)
            self.lo.addWidget(new_card)
        self.card_zone.setLayout(self.lo)
        self.auto_resize()

    def auto_resize(self):
        card_num = len(self.cards)
        if card_num == 0:
            card_num = 1
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        self.resize(parent_width, parent_height)
        self.background.resize(parent_width, parent_height)
        width = 0.12 * card_num - 0.04
        self.card_zone.resize(int(width * parent_width), int(parent_height * 0.25))
        self.card_zone.move(int(parent_width * (0.5 - width / 2)), int(parent_height * 0.37))
        self.commit.resize(int(parent_width * 0.1), int(parent_height * 0.05))
        self.commit.setFont(QFont('HYWenHei-85W', int(0.008 * parent_width)))
        self.commit.move(int(parent_width * 0.45), int(parent_height * 0.81))
        self.lo.setSpacing(int(parent_width * 0.04))
        for card in self.cards:
            card.auto_resize(int(parent_width * 0.08), int(parent_height * 0.25))

    def hide_ui(self):
        select = []
        for index in range(self.lo.count()):
            widget = self.lo.itemAt(index).widget()
            if isinstance(widget, Card):
                if widget.get_state():
                    select.append(index)
            widget.deleteLater()
        self.hide()
        self.cards.clear()
        select_message = {"message": "selected_card", "index": select}
        self.game.socket_send(str(select_message))

class ClickableLabel(QLabel):

    def __init__(self, parent):
        super().__init__(parent)
        self._state = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._state = not self._state
        self.change_highlight()
        event.ignore()

    def get_state(self):
        return self._state

    def set_state(self, value: bool):
        self._state = value
        self.change_highlight()

    def change_highlight(self):
        if self._state:
            border = max(int(self.width() / 25), 1)
            self.setStyleSheet("ClickableLabel{border: %dpx solid rgb(254, 251, 200)}" % border)
        else:
            self.setStyleSheet("ClickableLabel{border: 0px}")

class Card(ClickableLabel):

    def __init__(self, parent, card_name, card_cost):
        super().__init__(parent)
        self.setScaledContents(True)
        self.cost_list: list[Cost] = []
        self.init_card_picture(card_name)
        self.init_card_cost(card_cost)

    def init_card_picture(self, picture_name):
        picture = QPixmap("./resources/cards/%s.png" % picture_name)
        self.setPixmap(picture)

    def init_card_cost(self, card_cost):
        for key, value in card_cost.items():
            cost = Cost(self, key, value)
            self.cost_list.append(cost)
        self.auto_resize(self.width(), self.height())

    def change_cost(self, cost):
        if self.cost_list:
            self.cost_list[0].change_cost(cost)

    def auto_resize(self, width, height):
        self.resize(width, height)
        for index, cost in enumerate(self.cost_list):
            cost_height = int(0.05 * height / 0.31)
            cost.move(0, int(cost_height * index))
            cost.auto_resize(cost_height)

class HandCard(QLabel):
    def __init__(self, parent, card_name, card_cost):
        super().__init__(parent)
        self.setScaledContents(True)
        self.cost_list: list[Cost] = []
        self.init_card_picture(card_name)
        self.init_card_cost(card_cost)
        self.dragEnabled = False
        self.usable = False

    def init_card_picture(self, picture_name):
        picture = QPixmap("./resources/cards/%s.png" % picture_name)
        self.setPixmap(picture)

    def init_card_cost(self, card_cost):
        for key, value in card_cost.items():
            cost = Cost(self, key, value)
            self.cost_list.append(cost)
        self.auto_resize(self.width(), self.height())

    def change_cost(self, cost):
        if self.cost_list:
            self.cost_list[0].change_cost(cost)

    def set_usable(self, value: bool):
        self.usable = value
        self.change_highlight()

    def change_highlight(self):
        if self.usable:
            border = max(int(self.width() / 25), 1)
            self.setStyleSheet("HandCard{border: %dpx solid rgb(254, 251, 200)}" % border)
        else:
            self.setStyleSheet("HandCard{border: 0px}")

    def auto_resize(self, width, height):
        self.resize(width, height)
        for index, cost in enumerate(self.cost_list):
            cost_height = int(0.05 * height / 0.31)
            cost.move(0, int(cost_height * index))
            cost.auto_resize(cost_height)

    def setDragEnabled(self, enabled: bool):
        self.dragEnabled = enabled

    def mouseMoveEvent(self, e):
        if self.dragEnabled:
            mimeData = QMimeData()
            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setHotSpot(self.rect().center())
            drag.exec(Qt.DropAction.MoveAction)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)

class Cost(QWidget):
    def __init__(self, parent, cost_type, cost):
        super().__init__(parent)
        self.background = QLabel(self)
        self.background.setScaledContents(True)
        self.cost = QLabel(self)
        self.cost.setStyleSheet('color: white')
        self.cost.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.init_cost(cost_type, cost)

    def init_card_picture(self, picture_name):
        picture = QPixmap("./resources/cost/%s.png" % picture_name)
        self.background.setPixmap(picture)

    def init_cost(self, cost_type, cost):
        self.init_card_picture(cost_type)
        self.change_cost(cost)

    def change_cost(self, cost):
        self.cost.setText(str(cost))

    def auto_resize(self, width):
        self.resize(width, width)
        self.background.resize(width, width)
        self.cost.resize(width, width)
        self.cost.setFont(QFont('HYWenHei-85W', int(width/2)))

class State(QWidget):
    def __init__(self, parent, image_name, number):
        super().__init__(parent)
        self.image_name = image_name
        self.image_label = QLabel(self)
        self.image_label.setScaledContents(True)
        self.init_card_picture(image_name)
        self.number_label = QLabel(self)
        self.change_count(number)

    def init_card_picture(self, picture_name):
        default = QPixmap("./resources/state/state.png")
        self.image_label.setPixmap(default)
        picture = QPixmap("./resources/state/%s.png" % picture_name)
        self.image_label.setPixmap(picture)

    def change_count(self, number):
        self.number_label.setText(str(number))

    def auto_resize(self, width):
        self.resize(width, width)
        self.image_label.resize(width, width)
        self.number_label.resize(int(width/2), int(width/2))
        self.number_label.move(int(width*0.6), int(width/2))
        self.number_label.setStyleSheet("font-family: 'HYWenHei-85W'; color: white; font-size: %dpx;" % (int(width/3)))

class StateManager(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.lo = QHBoxLayout()
        self.lo.setSpacing(0)
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.lo)
        self.states: dict[str, State] = {}

    def add_widget(self, state_name, icon_name, count):
        new_state = State(self, icon_name, count)
        self.states.update({state_name: new_state})
        self.lo.addWidget(new_state)
        self.setLayout(self.lo)
        self.auto_resize(self.height())

    def update_state(self, state_name, count):
        if state_name in self.states:
            self.states[state_name].change_count(count)

    def remove_widget(self, state_name):
        if state_name in self.states:
            self.lo.removeWidget(self.states[state_name])
        self.setLayout(self.lo)
        self.auto_resize(self.height())

    def transfer_state(self, states: dict):
        for state_name, state in states.items():
            state.setParent(self)
            self.states.update({state_name: state})
            self.lo.addWidget(state)
        self.setLayout(self.lo)
        self.auto_resize(self.height())

    def clear(self):
        for index in range(self.lo.count()):
            self.lo.itemAt(index).widget().deleteLater()
        self.setLayout(self.lo)
        self.states.clear()

    def auto_resize(self, width):
        state_num = len(self.states)
        if state_num == 0:
            state_num = 1
        self.resize(width * state_num, width)
        for state_name, state in self.states.items():
            state.auto_resize(width)

class CardZone(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.all_card: list[HandCard] = []
        # self.select_card = None
        self.game = parent
        self.be_dragged: Optional[HandCard] = None
        self.be_dragged_index = -1
        self.auto_resize()

    def add_card(self, card_name, card_cost):
        new_card = HandCard(self, card_name, card_cost)
        new_card.show()
        self.all_card.append(new_card)
        self.auto_resize()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.game.action_phase_start:
            if event.button() == Qt.MouseButton.LeftButton:
                self.auto_expand()

    def record_being_dragged(self, card: HandCard):
        if card in self.all_card:
            self.be_dragged_index = self.all_card.index(card)
            self.be_dragged = card
            self.all_card.pop(self.be_dragged_index)
            self.auto_resize()


    def cancel_drag(self):
        self.be_dragged.setParent(self)
        self.all_card.insert(self.be_dragged_index, self.be_dragged)
        self.be_dragged.show() # 大概QDrag有默认的hide吧
        self.auto_resize()
        self.be_dragged_index = -1
        self.be_dragged = None

    def confirm_drag(self):
        self.be_dragged_index = -1
        self.be_dragged = None

    def get_select(self):
        if self.be_dragged is not None:
            return self.be_dragged_index
        else:
            return None

    def remove_card(self, index):
        # if self.be_dragged == self.all_card[index]:
        #     self.be_dragged = None  # 防止变量已删除再设state
        self.all_card[index].deleteLater()
        self.all_card.pop(index)
        self.auto_resize()

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        card_num = len(self.all_card)
        width = card_num * 0.05 + 0.03
        self.move(int((0.5 - width/2) * parent_width), int(parent_height * 0.9))
        self.resize(int(width * parent_width), int(parent_height * 0.25))
        for index, card in enumerate(self.all_card):
            card.auto_resize(int(0.08 * parent_width), int(0.25 * parent_height))
            card.move(int(0.05 * index * parent_width), 0)
            card.setDragEnabled(False)

    def auto_expand(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        card_num = len(self.all_card)
        width = card_num * 0.057 + 0.3 / card_num
        self.move(int((0.5 - width / 2) * parent_width), int(parent_height * 0.8))
        self.resize(int(width * parent_width), int(parent_height * 0.25))
        each_card_space = int((width-0.02) / card_num * parent_width)
        for index, card in enumerate(self.all_card):
            card.move(int(each_card_space * index), 0)
            card.setDragEnabled(True)

class Reroll(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.game = parent
        self.dice_zone = AutoResizeWidget(self, 60, "h", "element", True)
        self.commit = QPushButton(self)
        self.commit.setObjectName("commit")
        self.commit.setStyleSheet("#commit{border-image: url(./resources/confirm-icon.png);color: rgb(59, 66, 85);}")
        self.commit.clicked.connect(self.commit_reroll)
        self.commit.setText("确定")
        self.scroll_start_state = False
        self.auto_resize()

    @staticmethod
    def init_dice_picture(obj: ClickableLabel, picture_name):
        picture = QPixmap("./resources/elements/%s.png" % picture_name)
        obj.setPixmap(picture)

    def show_dice(self, dices):
        self.dice_zone.clear()
        for element in dices:
            self.dice_zone.add_widget(element)
        self.auto_resize()

    def commit_reroll(self):
        choose = []
        for index, dice in enumerate(self.dice_zone.contain_widget):
            if dice.get_state():
                choose.append(index)
        reroll_message = {"message": "need_reroll", "dice_index": choose}
        self.game.socket_send(str(reroll_message))
        self.hide()

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        self.resize(parent_width, parent_height)
        self.dice_zone.auto_resize(int(parent_height * 0.06))
        widget_width = self.dice_zone.width()
        widget_height = self.dice_zone.height()
        self.dice_zone.move(int(parent_width/2 - widget_width/2), int(parent_height/2 - widget_height/2))
        self.commit.resize(int(parent_width * 0.1), int(parent_height * 0.05))
        self.commit.move(int(parent_width * 0.45), int(parent_height * 0.81))
        self.commit.setFont(QFont('HYWenHei-85W', int(0.008 * parent_width)))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        obj = self.childAt(event.pos())
        if isinstance(obj, ClickableLabel):
            self.scroll_start_state = obj.get_state() # 点击时骰子已经改变了状态

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        obj = self.childAt(event.pos())
        if isinstance(obj, ClickableLabel):
            obj.set_state(self.scroll_start_state)

class DiceZone(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        # self.frame = QFrame(self)
        # self.frame.resize(40, 640)
        self.lo = QVBoxLayout()
        self.lo.setSpacing(0)
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.contain_dice: list[ClickableLabel] = []
        self.game = parent
        self.auto_resize()

    @staticmethod
    def init_dice_picture(obj: ClickableLabel, picture_name):
        picture = QPixmap("./resources/elements/%s.png" % picture_name)
        obj.setPixmap(picture)

    def add_dice(self, dice_name):
        dice_name = dice_name.lower()
        new_dice = ClickableLabel(self)
        new_dice.setScaledContents(True)
        self.init_dice_picture(new_dice, dice_name)
        self.lo.addWidget(new_dice)
        self.contain_dice.append(new_dice)
        self.auto_resize()
        self.setLayout(self.lo)

    def get_choose(self):
        choose = []
        for index, dice in enumerate(self.contain_dice):
            if dice.get_state():
                choose.append(index)
        return choose

    def remove_dice(self, indexes):
        indexes = sorted(indexes, reverse=True)
        for index in indexes:
            self.lo.itemAt(index).widget().deleteLater()
            self.contain_dice.pop(index)
        self.auto_resize()
        self.setLayout(self.lo)

    def clear(self):
        for index in range(self.lo.count()):
            self.lo.itemAt(index).widget().deleteLater()
        self.setLayout(self.lo)
        self.contain_dice.clear()

    def auto_highlight(self, indexes: list):
        for index in indexes:
            self.contain_dice[index].set_state(True)

    def auto_clear_highlight(self):
        indexes = self.get_choose()
        for index in indexes:
            self.contain_dice[index].set_state(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.game.action_state in ["cost", "play_card", "element_tuning", "use_skill"]:
            self.game.commit_button.setEnabled(False)
            choose_index = self.game.dice_zone.get_choose()
            cost_message = {"message": "check_cost", "cost": choose_index}
            self.game.socket_send(str(cost_message))

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        dice_num = len(self.contain_dice)
        self.move(int(parent_width * 0.96), int(parent_height * 0.16))
        self.resize(int(parent_width * 0.02), int(parent_height * 0.04) * dice_num)
        for dice in self.contain_dice:
            dice.resize(int(parent_width * 0.02), int(parent_height * 0.04))

class AutoResizeWidget(QWidget):
    def __init__(self, parent, child_widget_size, layout, widget_type, clickable=False):
        super().__init__(parent)
        self.resize(child_widget_size, child_widget_size)
        # self.frame = QFrame(self)
        # self.frame.resize(child_widget_size, child_widget_size)
        self.layout_type = layout
        self.child_widget_size = child_widget_size
        if layout == "v":
            self.lo = QVBoxLayout()
        else:
            self.lo = QHBoxLayout()
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.lo.setSpacing(0)
        self.widget_type = widget_type
        self.contain_widget = []
        self.clickable = clickable

    def init_picture(self, obj, picture_name):
        category = ""
        if self.widget_type == "energy":
            category = "energy"
        elif self.widget_type == "equip":
            category = "equip"
        elif self.widget_type == "element":
            category = "elements"
        picture = QPixmap("./resources/%s/%s.png" % (category, picture_name))
        obj.setPixmap(picture)

    def add_widget(self, widget_name):
        if self.clickable:
            new_widget = ClickableLabel(self)
        else:
            new_widget = QLabel(self)
        new_widget.setScaledContents(True)
        self.init_picture(new_widget, widget_name)
        self.lo.addWidget(new_widget)
        self.contain_widget.append(new_widget)
        if self.layout_type == "v":
            self.resize(self.child_widget_size, self.child_widget_size * len(self.contain_widget))
        else:
            self.resize(self.child_widget_size  * len(self.contain_widget), self.child_widget_size)
        self.setLayout(self.lo)

    def clear(self):
        for index in range(self.lo.count()):
            self.lo.itemAt(index).widget().deleteLater()
        self.setLayout(self.lo)
        self.contain_widget.clear()

    def remove_widget(self, index):
        self.lo.itemAt(index).widget().deleteLater()
        self.contain_widget.pop(index)
        if self.layout_type == "v":
            self.resize(self.child_widget_size, self.child_widget_size * len(self.contain_widget))
        else:
            self.resize(self.child_widget_size  * len(self.contain_widget), self.child_widget_size)
        self.setLayout(self.lo)

    def auto_resize(self, new_size):
        self.child_widget_size = new_size
        for widget in self.contain_widget:
            widget.resize(self.child_widget_size, self.child_widget_size)
        if self.layout_type == "v":
            self.resize(self.child_widget_size, self.child_widget_size * len(self.contain_widget))
        else:
            self.resize(self.child_widget_size  * len(self.contain_widget), self.child_widget_size)
        self.setLayout(self.lo)

class Skill(QWidget):
    def __init__(self, parent, skill_name, skill_cost):
        super().__init__(parent)
        self.skill_background = ClickableLabel(self)
        self.skill_background.setScaledContents(True)
        self.init_card_picture(self.skill_background, "skill-bg")
        self.skill_image = QLabel(self)
        self.skill_image.setScaledContents(True)
        self.skill_image.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.skill_image.setObjectName("skill_image")
        self.init_card_picture(self.skill_image, skill_name)
        self.skill_cost = QWidget(self)
        self.lo = QHBoxLayout(self.skill_cost)
        self.lo.setSpacing(0)
        self.skill_cost.setLayout(self.lo)
        self.auto_layout(skill_cost)

    @staticmethod
    def init_card_picture(obj, picture_name):
        picture_name = picture_name.replace(" ", "")
        picture = QPixmap("./resources/skills/%s.png" % picture_name)
        obj.setPixmap(picture)

    def auto_layout(self, skill_cost):
        if len(skill_cost) == 1:
            for key, value in skill_cost.items():
                cost = Cost(self, key, value)
                self.lo.addWidget(cost)
        elif len(skill_cost) == 2:
            for key, value in skill_cost.items():
                cost = Cost(self, key, value)
                self.lo.addWidget(cost)
        self.skill_cost.setLayout(self.lo)

    def update_cost(self, skill_cost):
        for index in range(self.lo.count()):
            self.lo.itemAt(index).widget().deleteLater()
        self.auto_layout(skill_cost)
        self.auto_resize(self.width(), self.height())

    def set_state(self, value):
        self.skill_background.set_state(value)

    def auto_resize(self, width, height):
        self.resize(width, height)
        self.skill_background.resize(width, width)
        self.skill_image.move(int(width/4), int(width/4))
        self.skill_image.resize(int(width/2), int(width/2))
        self.skill_cost.resize(int(width * 0.6), int(height/4))
        self.skill_cost.move(int(width/5), int(height*3/4))
        cost_num = 0
        for index in range(self.lo.count()):
            widget = self.lo.itemAt(index).widget()
            if isinstance(widget, Cost):
                cost_num += 1
                widget.auto_resize(int(height/4))
        if cost_num == 1:
            self.lo.setContentsMargins(int(width * 0.15), 0, 0, 0)
        else:
            self.lo.setContentsMargins(0, 0, 0, 0)
        self.skill_cost.setLayout(self.lo)

class SkillZone(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.choose: Optional[Skill] = None
        self.game = parent
        self.contain_widget = []
        self.skill_state = []
        self.lo = QHBoxLayout()
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.lo.setSpacing(0)
        self.auto_resize()

    def add_widget(self, skill_name, skill_cost):
        new_skill = Skill(self, skill_name, skill_cost)
        self.contain_widget.append(new_skill)
        self.lo.addWidget(new_skill)
        self.resize(80 * len(self.contain_widget), 110)
        self.setLayout(self.lo)
        self.auto_resize()

    def clear(self):
        for index in range(self.lo.count()):
            self.lo.itemAt(index).widget().deleteLater()
        self.setLayout(self.lo)
        self.contain_widget.clear()

    def get_choose(self):
        if self.choose is not None:
            return self.contain_widget.index(self.choose)
        return None

    def update_skill_state(self, skill_cost, skill_state):
        self.skill_state = skill_state
        for index, cost in enumerate(skill_cost):
            skill = self.contain_widget[index]
            skill.update_cost(cost)

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        skill_num = len(self.contain_widget)
        if skill_num == 0:
            skill_num = 1
        self_width = 0.06 * skill_num - 0.01
        self.move(int((0.97 - self_width) * parent_width), int(0.85 * parent_height))
        self.resize(int(self_width * parent_width), int(0.12 * parent_height))
        for skill in self.contain_widget:
            skill.auto_resize(int(parent_width * 0.05), int(0.12 * parent_height))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.game.action_phase_start and self.game.action_state != "cost":
            obj = self.childAt(event.pos())
            if isinstance(obj, ClickableLabel) and isinstance(obj.parent(), Skill):
                if obj.get_state():
                    if self.choose is not None:
                        try:
                            self.choose.set_state(False)
                            self.game.socket_send(str({"message": "cancel"}))
                        except RuntimeError:  # 对象已删除
                            pass
                    self.choose = obj.parent()
                    skill_index = self.get_choose()
                    if skill_index is not None:
                        if self.skill_state[self.get_choose()]:
                            self.game.commit_button.show()
                            self.game.action_state = "use_skill"
                            self.game.socket_send(str({"message": "use_skill", "skill_index": skill_index}))
                else:
                    self.choose = None
                    self.game.commit_button.hide()
                    self.game.dice_zone.auto_clear_highlight()
                    if self.game.action_state == "use_skill":
                        self.game.socket_send(str({"message": "cancel"}))
                        self.game.action_state = ""

class SupportCard(QFrame):
    def __init__(self, parent, support_name, count):
        super().__init__(parent)
        self.pic = QLabel(self)
        self.pic.setScaledContents(True)  # 原神是把图片按宽度缩放，高度保留底边。如果用scaledToWidth模糊的根本没法看，有空再说。
        self.init_card_picture(support_name)
        self.counter = QLabel(self)
        self.counter.setStyleSheet('color: white')
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter.setText(count)
        self.tick = QLabel(self)
        self.tick.setScaledContents(True)
        self.tick.setPixmap(QPixmap("./resources/tick.png"))
        self.tick.hide()
        self.be_chose = False
        self.can_be_chose = False

    def init_card_picture(self, picture_name):
        picture_name = picture_name.replace(" ", "")
        picture = QPixmap("./resources/cards/%s.png" % picture_name)
        self.pic.setPixmap(picture)

    def change_count(self, value):
        self.counter.setText(value)

    def change_state(self):
        self.set_state(not self.be_chose)

    def set_state(self, value: bool):
        self.be_chose = value
        if self.be_chose:
            self.tick.show()
        else:
            self.tick.hide()

    def auto_resize(self, width, height):
        self.resize(width, height)
        self.pic.resize(width, height)
        self.counter.resize(int(width/5), int(height/5))
        self.counter.setFont(QFont('HYWenHei-85W', int(width/6)))
        self.tick.resize(width, height)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.can_be_chose:
            self.change_state()
        event.ignore()

class SupportZone(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.game = parent
        self.lo = QGridLayout()
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.lo.setRowStretch(0, 1)
        self.lo.setRowStretch(1, 1)
        self.lo.setColumnStretch(0, 1)
        self.lo.setColumnStretch(1, 1)
        self.contain_widget: list[SupportCard] = []
        self.enable_choose_target = False
        self.auto_resize()

    def add_widget(self, support_name, count):
        new_support = SupportCard(self, support_name, count)
        self.contain_widget.append(new_support)
        num = len(self.contain_widget)
        self.lo.addWidget(new_support, (num-1)//2, (num-1)%2)
        self.setLayout(self.lo)
        self.auto_resize()

    def remove_widget(self, index):
        self.contain_widget.pop(index)
        self.lo.itemAt(index).widget().deleteLater()
        for index in range(self.lo.count()):
            widget = self.lo.itemAt(index).widget()
            if widget is not None:
                self.lo.addWidget(widget, index // 2, index % 2)
        self.setLayout(self.lo)

    def change_support_count(self, index, value):
        self.contain_widget[index].change_count(value)

    def change_enable_choose_target(self, value):
        self.enable_choose_target = value
        if self.enable_choose_target:
            for support in self.contain_widget:
                support.can_be_chose = True
        else:
            for support in self.contain_widget:
                support.can_be_chose = False
                support.set_state(False)

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        self.resize(int(parent_width * 0.15), int(parent_height * 0.31))
        self.lo.setSpacing(int(parent_height * 0.01))
        for support in self.contain_widget:
            support.auto_resize(int(parent_width * 0.07), int(parent_height * 0.15))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        obj = self.childAt(event.pos())
        if isinstance(obj, SupportCard):
            if self.enable_choose_target:
                if obj in self.contain_widget:
                    if obj.be_chose:
                        self.game.choose_target_index = self.contain_widget.index(obj)
                    else:
                        self.game.choose_target_index = -1

class SummonCard(QWidget):
    def __init__(self, parent, support_name, count, effect):
        super().__init__(parent)
        self.pic = QLabel(self)
        self.pic.setScaledContents(True)
        self.init_card_picture(support_name)
        self.counter = QLabel(self)
        self.counter.setStyleSheet('color: white')
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.change_usage(count)
        self.effect_type = QLabel(self)
        self.effect_type.setScaledContents(True)
        self.effect_value = QLabel(self)
        self.effect_value.setStyleSheet('color: white')
        self.effect_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.init_effect(effect)
        self.tick = QLabel(self)
        self.tick.setScaledContents(True)
        self.tick.setPixmap(QPixmap("./resources/tick.png"))
        self.tick.hide()
        self.be_chose = False
        self.can_be_chose = False

    def init_card_picture(self, picture_name):
        picture_name = picture_name.replace(" ", "")
        picture = QPixmap("./resources/summon/%s.png" % picture_name)
        self.pic.setPixmap(picture)

    def init_effect(self, effect):
        if effect:
            effect_type, effect_value = effect["effect_type"].lower(), effect["effect_value"]
            if effect_type == "heal":
                picture = QPixmap("./resources/images/heal-icon.png")
                self.effect_type.setPixmap(picture)
                self.effect_value.setText(str(effect_value))
            else:
                picture = QPixmap("./resources/elements/%s.png" % effect_type)
                self.effect_type.setPixmap(picture)
                self.effect_value.setText(str(effect_value))

    def change_state(self):
        self.set_state(not self.be_chose)

    def set_state(self, value: bool):
        self.be_chose = value
        if self.be_chose:
            self.tick.show()
        else:
            self.tick.hide()

    def change_usage(self, num):
        self.counter.setText(str(num))

    def auto_resize(self, width, height):
        self.resize(width, height)
        self.pic.resize(width, height)
        self.counter.resize(int(width/5), int(height/5))
        self.counter.setFont(QFont('HYWenHei-85W', int(width/6)))
        self.counter.move(int(width * 4 / 5), 0)
        self.effect_type.resize(int(width * 0.4), int(width * 0.4))
        self.effect_type.move(0, int(width * 0.72))
        self.effect_value.resize(int(width * 0.4), int(width * 0.4))
        self.effect_value.move(0, int(width * 0.75))
        self.effect_value.setFont(QFont('HYWenHei-85W', int(width/5)))
        self.tick.resize(width, height)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.can_be_chose:
            self.change_state()
        event.ignore()

class SummonZone(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.game = parent
        self.lo = QGridLayout()
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.lo.setRowStretch(0, 1)
        self.lo.setRowStretch(1, 1)
        self.lo.setColumnStretch(0, 1)
        self.lo.setColumnStretch(1, 1)
        self.contain_widget: list[SummonCard] = []
        self.enable_choose_target = False
        
    def add_widget(self, summon_name, count, effect):
        new_summon = SummonCard(self, summon_name, count, effect)
        self.contain_widget.append(new_summon)
        num = len(self.contain_widget)
        self.lo.addWidget(new_summon, (num-1)//2, (num-1)%2)
        self.setLayout(self.lo)
        self.auto_resize()

    def get_not_none_widget(self) -> list[SummonCard]: # 延迟删除真的有病
        not_none_widget = []
        for index in range(self.lo.count()):
            widget = self.lo.itemAt(index).widget()
            if isinstance(widget, SummonCard) and widget is not None:
                not_none_widget.append(widget)
        return not_none_widget

    def remove_widget(self, index):
        self.contain_widget.pop(index)
        self.lo.itemAt(index).widget().deleteLater()
        not_none_widget = self.get_not_none_widget()
        for index, widget in enumerate(not_none_widget):
            self.lo.addWidget(widget, index//2, index%2)
        self.setLayout(self.lo)

    def change_summon_count(self, index, value):
        self.contain_widget[index].change_usage(value)

    def change_enable_choose_target(self, value):
        self.enable_choose_target = value
        if self.enable_choose_target:
            for summon in self.contain_widget:
                summon.can_be_chose = True
        else:
            for summon in self.contain_widget:
                summon.can_be_chose = False
                summon.set_state(False)

    def auto_resize(self):
        parent_height = self.parent().height()
        parent_width = self.parent().width()
        self.resize(int(parent_width * 0.15), int(parent_height * 0.31))
        self.lo.setSpacing(int(parent_height * 0.01))
        for summon in self.contain_widget:
            summon.auto_resize(int(parent_width * 0.07), int(parent_height * 0.15))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        obj = self.childAt(event.pos())
        if isinstance(obj, SummonCard):
            if self.enable_choose_target:
                if obj in self.contain_widget:
                    if obj.be_chose:
                        self.game.choose_target_index = self.contain_widget.index(obj)
                    else:
                        self.game.choose_target_index = -1

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = Gcg()
    game.show()
    sys.exit(app.exec())

