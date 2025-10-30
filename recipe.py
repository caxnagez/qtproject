import sys
import os
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QListWidgetItem, QMessageBox, QDialog, QFileDialog)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from PyQt6 import uic
import pyttsx3
from database import (init_db, get_all_ingredients, get_recipes_by_ingredients, add_recipe,
                      update_recipe, delete_recipe, get_recipe_by_id, ensure_ingredient_exists)


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class AddRecipeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(resource_path("ui/newrecipe.ui"), self)
        self.image_path = ""
        self.setWindowTitle("Добавить рецепт")
        self.btn_browse.clicked.connect(self.browse_image)
        self.btn_save.clicked.connect(self.save_recipe)
        self.btn_cancel.clicked.connect(self.reject)

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите фото блюда", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.image_path = path
            pixmap = QPixmap(path)
            scaled_pixmap = pixmap.scaled(
                self.label_preview.width(),
                self.label_preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.label_preview.setPixmap(scaled_pixmap)
            self.label_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def save_recipe(self):
        name = self.lineEdit_name.text().strip()
        instructions = self.textEdit_instructions.toPlainText().strip()
        if not name or not instructions:
            QMessageBox.warning(self, "Ошибка", "Заполните название и инструкцию.")
            return

        ing_str = self.lineEdit_ingredients.text()
        ing_names = [x.strip() for x in ing_str.split(",") if x.strip()]
        ing_ids = [ensure_ingredient_exists(name) for name in ing_names]

        img_path = self.image_path if self.image_path else resource_path("resources/def.png")
        add_recipe(name, instructions, img_path, ing_ids)
        self.accept()


class EditRecipeDialog(QDialog):
    def __init__(self, recipe_data, parent=None):
        super().__init__(parent)
        uic.loadUi(resource_path("ui/editrecipe.ui"), self)
        self.recipe_data = recipe_data
        self.image_path = recipe_data['image_path']
        self.setWindowTitle(f"Редактировать: {recipe_data['name']}")
        self.load_recipe_data()
        self.btn_browse.clicked.connect(self.browse_image)
        self.btn_save.clicked.connect(self.save_recipe)
        self.btn_cancel.clicked.connect(self.reject)

    def load_recipe_data(self):
        self.lineEdit_name.setText(self.recipe_data['name'])
        self.lineEdit_ingredients.setText(", ".join(self.recipe_data['ingredients']))
        self.textEdit_instructions.setPlainText(self.recipe_data['instructions'])

        if os.path.exists(self.image_path):
            pixmap = QPixmap(self.image_path)
            scaled_pixmap = pixmap.scaled(
                self.label_preview.width(),
                self.label_preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.label_preview.setPixmap(scaled_pixmap)
            self.label_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.label_preview.setText("Фото не найдено")

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите фото блюда", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.image_path = path
            pixmap = QPixmap(path)
            scaled_pixmap = pixmap.scaled(
                self.label_preview.width(),
                self.label_preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.label_preview.setPixmap(scaled_pixmap)
            self.label_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def save_recipe(self):
        name = self.lineEdit_name.text().strip()
        instructions = self.textEdit_instructions.toPlainText().strip()
        if not name or not instructions:
            QMessageBox.warning(self, "Ошибка", "Заполните название и инструкцию.")
            return

        ing_str = self.lineEdit_ingredients.text()
        ing_names = [x.strip() for x in ing_str.split(",") if x.strip()]
        ing_ids = [ensure_ingredient_exists(name) for name in ing_names]

        update_recipe(self.recipe_data['id'], name, instructions, self.image_path, ing_ids)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("ui/main.ui"), self)
        self.setWindowTitle("Рецепты *Ам-Ням*")

        init_db()
        self.setup_connections()
        self.load_all_recipes()

        self.tts_running = False

    def setup_connections(self):
        self.btn_search.clicked.connect(self.search_recipes)
        self.btn_add.clicked.connect(self.open_add_dialog)
        self.btn_speak.clicked.connect(self.speak_instructions)
        self.btn_delete.clicked.connect(self.delete_selected_recipe)
        self.listWidget_recipes.itemClicked.connect(self.load_recipe)
        self.listWidget_recipes.itemDoubleClicked.connect(self.open_edit_dialog)
        self.listWidget_recipes.itemDoubleClicked.connect(self.play_recipe_tts)

    def load_all_recipes(self):
        recipes = get_recipes_by_ingredients([])
        self.display_recipes(recipes)

    def search_recipes(self):
        text = self.lineEdit_search.text().strip()
        if not text:
            self.load_all_recipes()
            return

        ing_names = [x.strip().lower() for x in text.split(",") if x.strip()]
        all_ings = {name.lower(): id for id, name in get_all_ingredients()}
        ids = [all_ings[name] for name in ing_names if name in all_ings]
        recipes = get_recipes_by_ingredients(ids)
        self.display_recipes(recipes)

    def display_recipes(self, recipes):
        self.listWidget_recipes.clear()
        for rec in recipes:
            item = QListWidgetItem(rec[1])
            item.setData(Qt.ItemDataRole.UserRole, rec)
            self.listWidget_recipes.addItem(item)

    def load_recipe(self, item):
        rec = item.data(Qt.ItemDataRole.UserRole)
        self.textEdit_instructions.setPlainText(rec[2] or "")
        img_path = rec[3] or resource_path("resources/def.png")
        if not os.path.exists(img_path):
            img_path = resource_path("resources/def.png")
        pixmap = QPixmap(img_path)
        scaled_pixmap = pixmap.scaled(
            self.label_image.width(),
            self.label_image.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.label_image.setPixmap(scaled_pixmap)
        self.label_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.listWidget_ingredients.clear()
        recipe_id = rec[0]
        recipe_data = get_recipe_by_id(recipe_id)
        if recipe_data:
            ingredients = recipe_data['ingredients']
            for ingredient in ingredients:
                self.listWidget_ingredients.addItem(ingredient)

    def open_add_dialog(self):
        dialog = AddRecipeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_all_recipes()

    def open_edit_dialog(self, item):
        rec = item.data(Qt.ItemDataRole.UserRole)
        recipe_id = rec[0]
        recipe_data = get_recipe_by_id(recipe_id)
        if recipe_data:
            self.listWidget_recipes.itemDoubleClicked.disconnect(self.play_recipe_tts)

            dialog = EditRecipeDialog(recipe_data, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.load_all_recipes()
                self.textEdit_instructions.clear()
                self.listWidget_ingredients.clear()
                self.label_image.clear()
                self.label_image.setText("Фото блюда")
            self.listWidget_recipes.itemDoubleClicked.connect(self.play_recipe_tts)
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить данные рецепта для редактирования.")

    def delete_selected_recipe(self):
        item = self.listWidget_recipes.currentItem()
        if not item:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите рецепт для удаления.")
            return

        rec = item.data(Qt.ItemDataRole.UserRole)
        recipe_id = rec[0]
        recipe_name = rec[1]

        reply = QMessageBox.question(
            self, "Подтверждение", f"Вы уверены, что хотите удалить рецепт '{recipe_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_recipe(recipe_id)
            self.load_all_recipes()
            self.textEdit_instructions.clear()
            self.listWidget_ingredients.clear()
            self.label_image.clear()
            self.label_image.setText("Фото блюда")

    def _speak_with_new_engine(self, text):
        engine = pyttsx3.init()
        engine.setProperty('rate', 220)
        engine.setProperty('volume', 0.9)

        voices = engine.getProperty('voices')
        for voice in voices:
            if 'david' in voice.name.lower() or 'male' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                print(f"[DEBUG] В потоке установлен голос: {voice.name}")
                break
        else:
            if voices:
                engine.setProperty('voice', voices[0].id)
                print(f"[!] В потоке установлен первый доступный голос: {voices[0].name}")

        engine.say(text)
        engine.runAndWait()

    def play_recipe_tts(self, item):
        if self.tts_running:
            print("[!] Озвучка уже запущена, пропускаем новый запуск.")
            return

        rec = item.data(Qt.ItemDataRole.UserRole)
        instructions = (rec[2] or "").strip()
        if not instructions:
            return

        self.tts_running = True
        print("[!] Запускаю _speak_with_new_engine в отдельном потоке...")
        def _run():
            self._speak_with_new_engine(instructions)
            self.tts_running = False
            print("[!] _speak_with_new_engine завершён, флаг сброшен.")
        threading.Thread(target=_run, daemon=True).start()

    def speak_instructions(self):
        if self.tts_running:
            print("[!] Озвучка уже запущена, пропускаем новый запуск.")
            return

        text = self.textEdit_instructions.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Нет текста для озвучки.")
            return

        self.tts_running = True
        print("[!] Запускаю _speak_with_new_engine для кнопки в отдельном потоке...")
        def _run():
            self._speak_with_new_engine(text)
            self.tts_running = False
            print("[!] _speak_with_new_engine завершён, флаг сброшен.")
        threading.Thread(target=_run, daemon=True).start()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.lineEdit_search.hasFocus():
                self.search_recipes()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())