from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from openpyxl import Workbook
from io import BytesIO
import requests
from dotenv import load_dotenv
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://peppy-cat-9abb7e.netlify.app"}})
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')

def calculate_service_fee(count):
    if count < 10:
        return 30
    elif 10 <= count <= 20:
        return 20
    else:
        return 15

def send_to_telegram(file, filename, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    files = {'document': (filename, file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    data = {'chat_id': chat_id}
    response = requests.post(url, files=files, data=data)
    return response.json()

@app.route('/upload-photo', methods=['POST'])
def upload_photo():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'Файл не предоставлен'}), 400

        file = request.files['image']
        form_data = {'image': file}
        response = requests.post(f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}", files=form_data)

        data = response.json()
        if not data.get('success'):
            return jsonify({'error': 'Ошибка при загрузке фото'}), 500

        return jsonify({'url': data['data']['url']})
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # Получаем данные из FormData
        username = request.form.get('username', 'user')
        chat_id = request.form.get('chat_id')
        items = []
        i = 1
        while f'name_{i}' in request.form:
            item = {
                'name': request.form.get(f'name_{i}', ''),
                'link': request.form.get(f'link_{i}', ''),
                'photo': request.form.get(f'qr_{i}', ''),  # Синхронизируем qr_X с photo
                'contactPhoto': '',  # Поле удалено из формы, оставляем пустым
                'size': request.form.get(f'size_{i}', ''),
                'qty': request.form.get(f'quantity_{i}', '0'),
                'price': request.form.get(f'price_{i}', '0.00')
            }
            items.append(item)
            i += 1

        if not items:
            return jsonify({'error': 'Список товаров пуст'}), 400
        if not chat_id:
            return jsonify({'error': 'Не указан chat_id'}), 400

        wb = Workbook()
        ws = wb.active
        ws.title = "Заказ"

        headers = [
            "Наименование товара", "Ссылка/контакт", "Фото товара", "Фото контакта",
            "Размер", "Количество", "Цена за единицу", "Услуги внутри Китая", "Итоговая стоимость"
        ]
        ws.append(headers)

        service_fee = calculate_service_fee(len(items))

        for item in items:
            try:
                price = float(item.get('price', 0))
                qty = int(item.get('qty', 0))
                if price <= 0 or qty <= 0:
                    return jsonify({'error': 'Цена и количество должны быть больше 0'}), 400
                total = price * qty + service_fee
                ws.append([
                    item.get('name', ''),
                    item.get('link', ''),
                    item.get('photo', ''),
                    item.get('contactPhoto', ''),
                    item.get('size', ''),
                    qty,
                    price,
                    service_fee,
                    total
                ])
            except (ValueError, TypeError):
                return jsonify({'error': 'Некорректные данные о товаре'}), 400

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        filename = f"{username}.xlsx"

        telegram_response = send_to_telegram(buffer.getvalue(), filename, chat_id)
        if not telegram_response.get('ok'):
            return jsonify({'error': f"Ошибка отправки в Telegram: {telegram_response.get('description')}"}), 500

        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/')
def ping():
    return "Сервер работает", 200

if __name__ == '__main__':
    app.run(debug=True)