import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import sqlite3
import io
from config import TOKEN


# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния разговора
CHOOSING, PROJECT_NAME, DESCRIPTION, URL, STATUS, PHOTO = range(6)

# Функция для подключения к базе данных
def get_db_connection():
    conn = sqlite3.connect('projects.db')
    conn.row_factory = sqlite3.Row
    return conn

# Функция для создания таблицы
def create_table():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS projects
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    project_name TEXT,
                    description TEXT,
                    url TEXT,
                    status TEXT,
                    photo BLOB)''')
    conn.commit()
    conn.close()
    logger.info("Таблица 'projects' создана или уже существует.")

# Функция для начала разговора
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [KeyboardButton("Добавить проект")],
        [KeyboardButton("Мои проекты")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        'Привет! Что бы вы хотели сделать?',
        reply_markup=reply_markup
    )
    return CHOOSING

# Функция для добавления проекта
async def add_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Введите название проекта:')
    return PROJECT_NAME

async def project_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['project_name'] = update.message.text
    await update.message.reply_text('Введите описание проекта:')
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['description'] = update.message.text
    await update.message.reply_text('Введите URL проекта:')
    return URL

async def url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['url'] = update.message.text
    await update.message.reply_text('Введите статус проекта:')
    return STATUS

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['status'] = update.message.text
    await update.message.reply_text('Отправьте фото проекта:')
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
    else:
        photo_bytes = None
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO projects (user_id, project_name, description, url, status, photo) VALUES (?, ?, ?, ?, ?, ?)',
                     (user.id, context.user_data['project_name'], context.user_data['description'],
                      context.user_data['url'], context.user_data['status'], photo_bytes))
        conn.commit()
        await update.message.reply_text('Проект успешно добавлен!')
        logger.info(f"Проект '{context.user_data['project_name']}' добавлен для пользователя {user.id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении проекта: {e}")
        await update.message.reply_text('Произошла ошибка при добавлении проекта. Попробуйте еще раз.')
    finally:
        conn.close()
    
    return ConversationHandler.END

# Функция для показа проектов пользователя
async def show_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    conn = get_db_connection()
    try:
        projects = conn.execute('SELECT * FROM projects WHERE user_id = ?', (user.id,)).fetchall()
        if not projects:
            await update.message.reply_text('У вас пока нет проектов.')
        else:
            for project in projects:
                message = f"Название: {project['project_name']}\n"
                message += f"Описание: {project['description']}\n"
                message += f"URL: {project['url']}\n"
                message += f"Статус: {project['status']}"
                await update.message.reply_text(message)
                if project['photo']:
                    photo_bytes = io.BytesIO(project['photo'])
                    await update.message.reply_photo(photo_bytes)
        logger.info(f"Показаны проекты для пользователя {user.id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении проектов: {e}")
        await update.message.reply_text('Произошла ошибка при получении проектов. Попробуйте еще раз.')
    finally:
        conn.close()
    
    return ConversationHandler.END

def main() -> None:
    # Создаем таблицу при запуске бота
    create_table()
    
    # Создаем Application и передаем ему токен вашего бота
    application = Application.builder().token("7488139606:AAGewFlwlWSUy4LO4ganWHluS40d59zd-rc").build()

    # Добавляем обработчик разговора с состояниями CHOOSING, PROJECT_NAME, DESCRIPTION, URL, STATUS и PHOTO
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [MessageHandler(filters.Regex('^(Добавить проект)$'), add_project),
                       MessageHandler(filters.Regex('^(Мои проекты)$'), show_projects)],
            PROJECT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, project_name)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description)],
            URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, url)],
            STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, status)],
            PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, photo)]
        },
        fallbacks=[CommandHandler('start', start)]
    )

    application.add_handler(conv_handler)

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()