
import csv
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio

API_TOKEN = '7242273434:AAFiwplTnqrE9No0cXgwDxBUVu-9yhgdjko'
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Путь к файлу с вопросами
QUESTIONS_FILE = 'questions.csv'

# Список категорий
categories = [
    "Наука", "Технологии", "Музыка"
]

# Хранилище для вопросов и ответов
questions_by_category = {category: [] for category in categories}
user_answers = {}
message_ids = {}  # Хранилище для идентификаторов сообщений

# Глобальная переменная для выбранной категории
selected_category = None

def load_questions():
    global questions_by_category
    for category in categories:
        questions_by_category[category] = []  # Сбрасываем вопросы перед загрузкой
        with open(QUESTIONS_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['category'] == category:
                    question = {
                        'question': row['question'],
                        'options': [row['option1'], row['option2'], row['option3'], row['option4']],
                        'correct': row['correct_option']
                    }
                    questions_by_category[category].append(question)

@dp.message(Command(commands=['start']))
async def send_welcome(message: types.Message):
    # Создание клавиатуры с кнопками для выбора категории
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=category, callback_data=f'category_{category}')] for category in categories
    ])

    await message.answer("Привет! Добро пожаловать в викторину. Выберите категорию вопросов:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith('category_'))
async def choose_category(callback_query: types.CallbackQuery):
    global selected_category
    selected_category = callback_query.data.split('_')[1]
    load_questions()  # Загружаем все вопросы
    user_id = callback_query.from_user.id

    # Оставляем 5 случайных вопросов из выбранной категории
    user_answers[user_id] = {
        'answers': [],
        'current_question_index': 0,
        'questions': random.sample(questions_by_category[selected_category], min(5, len(questions_by_category[selected_category])))
    }

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, f"Вы выбрали категорию: {selected_category}. Викторина начинается!")

    if user_answers[user_id]['questions']:
        await send_question(callback_query.message, user_id)
    else:
        await callback_query.message.answer("Не удалось загрузить вопросы.")

async def send_question(message: types.Message, user_id):
    current_question_index = user_answers[user_id]['current_question_index']
    question = user_answers[user_id]['questions'][current_question_index]

    # Создание клавиатуры с вариантами ответов
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=option, callback_data=f"option_{i}")] for i, option in enumerate(question['options'])
    ])

    # Сохраняем идентификатор сообщения
    message_id = await message.answer(question['question'], reply_markup=keyboard)
    if user_id not in message_ids:
        message_ids[user_id] = []
    message_ids[user_id].append(message_id.message_id)

@dp.callback_query(lambda c: c.data.startswith('option_'))
async def process_answer(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    selected_answer_index = int(callback_query.data.split('_')[1])
    current_question_index = user_answers[user_id]['current_question_index']
    question = user_answers[user_id]['questions'][current_question_index]

    # Получаем выбранный ответ по индексу
    selected_answer = question['options'][selected_answer_index]

    # Сохранение ответа пользователя
    user_answers[user_id]['answers'].append({
        'question': question['question'],
        'answer': selected_answer,
        'correct': question['correct']
    })

    # Удаление кнопок после ответа
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.message.answer(f"Ваш ответ: {selected_answer}")

    # Переход к следующему вопросу или завершение викторины
    user_answers[user_id]['current_question_index'] += 1
    if user_answers[user_id]['current_question_index'] < len(user_answers[user_id]['questions']):
        await send_question(callback_query.message, user_id)
    else:
        await show_results(callback_query.message, user_id)

async def show_results(message: types.Message, user_id: int):
    results = user_answers[user_id]['answers']

    if not results:
        await message.answer("Итоги не найдены. Похоже, что вы не ответили ни на один вопрос.")
        return

    # Форматирование итогов викторины
    result_text = "📊 *Итоги викторины:*\n\n"
    for result in results:
        if result['answer'] == result['correct']:
            result_text += f"✅ *Вопрос:* {result['question']}\n"
            result_text += f"Ваш ответ: {result['answer']}\n\n"
        else:
            result_text += f"❌ *Вопрос:* {result['question']}\n"
            result_text += f"Ваш ответ: {result['answer']}\n"
            result_text += f"Правильный ответ: {result['correct']}\n\n"

    # Кнопка "Сыграть еще раз"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сыграть еще раз", callback_data='play_again')]
    ])

    # Отправляем итоги и сохраняем идентификатор сообщения
    result_message = await message.answer(result_text, parse_mode="Markdown", reply_markup=keyboard)
    if user_id not in message_ids:
        message_ids[user_id] = []
    message_ids[user_id].append(result_message.message_id)

@dp.callback_query(lambda c: c.data == 'play_again')
async def play_again(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    # Удаляем все сообщения викторины, кроме сообщения с итогами
    if user_id in message_ids:
        for message_id in message_ids[user_id]:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                print(f"Failed to delete message {message_id}: {e}")
        message_ids[user_id] = []

    # Отправляем сообщение с предложением выбрать категорию
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=category, callback_data=f'category_{category}')] for category in categories
    ])

    await bot.send_message(callback_query.from_user.id, "Выберите категорию вопросов:", reply_markup=keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
