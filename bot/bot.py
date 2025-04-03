import logging
import asyncio
import json
import os
import requests
from typing import List, Dict
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
from openai import OpenAI
from PyPDF2 import PdfReader

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000"
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

(
    CHOOSING, REGISTER_NAME, REGISTER_PASS, LOGIN_NAME, LOGIN_PASS, 
    AUTHORIZED, UPLOAD_PDF, FROM_REG_TO_LOG, EDIT_TOPIC, EDIT_TOPIC_NAME, EDIT_CONCLUSIONS,
    REWRITE_CONCLUSIONS, REGENERATE_CONCLUSIONS, ADD_COMMENT, DELETE_CONFIRM, VIEW_TOPICS, 
    INSTRUCTOR_ACTIONS, VIEW_TOPICS_INLINE, TOPIC_DETAILS, VIEW_LEARNER_TOPICS_INLINE, LEARNER_TOPIC_DETAILS,
    TAKING_TEST, TEST_RESULTS, WAITING_FOR_NEXT, GENERATE_ASSESSMENT, REVIEW_ASSESSMENT, SAVE_ASSESSMENT
) = range(27)

main_keyboard = ReplyKeyboardMarkup([["Register", "Login"]], one_time_keyboard=True)
auth_keyboard = ReplyKeyboardMarkup(
    [["Instructor", "Learner"], ["Logout"]],
    one_time_keyboard=True
)
instructor_keyboard = ReplyKeyboardMarkup(
    [["New topic", "Edit my topics"], ["Back"]],
    one_time_keyboard=True
)
from_reg_to_log_keyboard = ReplyKeyboardMarkup([["Login", "Register"]], one_time_keyboard=True)
edit_options_keyboard = ReplyKeyboardMarkup(
    [["Change topic name", "Edit learning outcomes"], 
     ["Delete document", "Save learning outcomes"]],
    one_time_keyboard=True
)
edit_conclusions_keyboard = ReplyKeyboardMarkup(
    [["Rewrite learning outcomes", "Regenerate with comment"], ["Back"]],
    one_time_keyboard=True
)
delete_confirm_keyboard = ReplyKeyboardMarkup(
    [["Yes, delete", "No, cancel"]],
    one_time_keyboard=True
)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

TOPICS_DIR = "topics"
os.makedirs(TOPICS_DIR, exist_ok=True)

PDF_FILENAME = "doc.pdf"
OUTCOMES_FILENAME = "outcomes.txt"
ASSESSMENT_FILENAME = "assessment.txt"

async def start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Choose an action:", reply_markup=main_keyboard)
    return CHOOSING

async def start_with_command(update: Update, context: CallbackContext) -> int:
    command = update.message.text
    if command == "Register":
        await update.message.reply_text("Enter a name to register:", reply_markup=ReplyKeyboardRemove())
        return REGISTER_NAME
    elif command == "Login":
        await update.message.reply_text("Enter your name:", reply_markup=ReplyKeyboardRemove())
        return LOGIN_NAME
    else:
        await update.message.reply_text("Choose an action:", reply_markup=main_keyboard)
        return CHOOSING

async def choose_action(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Register":
        await update.message.reply_text("Enter a name to register:", reply_markup=ReplyKeyboardRemove())
        return REGISTER_NAME
    elif text == "Login":
        await update.message.reply_text("Enter your name:", reply_markup=ReplyKeyboardRemove())
        return LOGIN_NAME
    await update.message.reply_text("Use the buttons!", reply_markup=main_keyboard)
    return CHOOSING

async def register_name(update: Update, context: CallbackContext) -> int:
    name = update.message.text
    context.user_data["reg_name"] = name
    await update.message.reply_text("Create a password:")
    return REGISTER_PASS

async def register_pass(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    context.user_data["reg_password"] = password
    name = context.user_data["reg_name"]

    try:
        response = requests.post(
            f"{API_BASE_URL}/user",
            json={"username": name, "hashed_password": password}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            try:
                response_t = requests.post(
                    f"{API_BASE_URL}/auth",
                    data={"username": name, "password": password}
                )
                
                if response_t.status_code == 200:
                    token_data = response_t.json()
                    context.user_data["access_token"] = token_data["access_token"]
                    await show_auth_menu(update, f"Welcome, {name}!")
                    return AUTHORIZED
                else:
                    error_msg = response_t.json().get("detail", "Invalid login or password")
                    await update.message.reply_text(f"Invalid login or password")
                    return CHOOSING
                    
            except Exception as e:
                logger.error(f"API error: {e}")
                await update.message.reply_text("Error getting client token. Please try again later.", reply_markup=main_keyboard)
                return CHOOSING
            
            return AUTHORIZED

        elif response.status_code == 409:
            await update.message.reply_text(f"User with login {name} already exists, do you want to login?", 
                                          reply_markup=from_reg_to_log_keyboard)
            return FROM_REG_TO_LOG
        else:
            error_msg = response.json().get("detail", "Registration error")
            await update.message.reply_text(f"Error: {error_msg}")
            return CHOOSING
    except Exception as e:
        logger.error(f"API error: {e}")
        await update.message.reply_text("Server connection error. Please try again later.", reply_markup=main_keyboard)
        return CHOOSING

async def login_name(update: Update, context: CallbackContext) -> int:
    name = update.message.text
    context.user_data["login_name"] = name
    await update.message.reply_text("Enter password:")
    return LOGIN_PASS

async def login_pass(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    context.user_data["login_password"] = password
    name = context.user_data["login_name"]

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth",
            data={"username": name, "password": password}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            context.user_data["access_token"] = token_data["access_token"]
            await show_auth_menu(update, f"Welcome, {name}!")
            return AUTHORIZED
        else:
            error_msg = response.json().get("detail", "Invalid login or password")
            await update.message.reply_text(f"Invalid login or password")
            return CHOOSING
    except Exception as e:
        logger.error(f"API error: {e}")
        await update.message.reply_text("Server connection error. Please try again later.", reply_markup=main_keyboard)
        return CHOOSING

async def from_reg_to_log(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Login":
        name = context.user_data["reg_name"]
        password = context.user_data["reg_password"]
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth",
                data={"username": name, "password": password}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                context.user_data["access_token"] = token_data["access_token"]
                await show_auth_menu(update, f"Welcome, {name}!")
                return AUTHORIZED
            else:
                error_msg = response.json().get("detail", "Invalid login or password")
                await update.message.reply_text(f"Invalid login or password", reply_markup=main_keyboard)
                return CHOOSING
        except Exception as e:
            logger.error(f"API error: {e}")
            await update.message.reply_text("Server connection error. Please try again later.", reply_markup=main_keyboard)
            return CHOOSING
    if text == "Register":
        await update.message.reply_text("Enter a name to register:", reply_markup=ReplyKeyboardRemove())
        return REGISTER_NAME
    else:
        await update.message.reply_text("Choose an action:", reply_markup=main_keyboard)
        return CHOOSING

async def show_auth_menu(update: Update, message: str) -> None:
    await update.message.reply_text(message, reply_markup=auth_keyboard)

async def instructor_actions(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "New topic":
        await update.message.reply_text(
            "Upload PDF document:",
            reply_markup=ReplyKeyboardRemove()
        )
        return UPLOAD_PDF
    elif text == "Edit my topics":
        return await view_topics_inline(update, context)
    elif text == "Back":
        await update.message.reply_text(
            "Choose your role:",
            reply_markup=auth_keyboard
        )
        return AUTHORIZED

async def auth_actions(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Instructor":
        await update.message.reply_text(
            "Choose topic actions:",
            reply_markup=instructor_keyboard
        )
        return INSTRUCTOR_ACTIONS
    elif text == "Learner":
        return await view_learner_topics_inline(update, context)
    elif text == "Logout":
        context.user_data.clear()
        await update.message.reply_text("You have logged out!", reply_markup=main_keyboard)
        return CHOOSING
    else:
        await update.message.reply_text("Use the buttons!", reply_markup=auth_keyboard)
        return AUTHORIZED

async def view_topics_inline(update: Update, context: CallbackContext) -> int:
    try:
        message = update.message or update.callback_query.message
        
        all_topics = [name for name in os.listdir(TOPICS_DIR) 
                    if os.path.isdir(os.path.join(TOPICS_DIR, name))]
        
        if not all_topics:
            await message.reply_text("You don't have any saved topics yet.")
            return INSTRUCTOR_ACTIONS
        
        context.user_data.setdefault('topics_pagination', {'page': 0, 'topics': all_topics})
        page = context.user_data['topics_pagination']['page']
        topics = context.user_data['topics_pagination']['topics']
        
        PAGE_SIZE = 8
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_topics = topics[start:end]
        
        keyboard = []
        for topic in page_topics:
            topic_body = topic.replace(' ', '_').replace('/', '').replace('\\', '')[:40]
            safe_callback = f"topic_{topic_body}"
            keyboard.append([InlineKeyboardButton(topic, callback_data=safe_callback)])
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀ Back", callback_data="prev_page"))
        if end < len(topics):
            nav_buttons.append(InlineKeyboardButton("Next ▶", callback_data="next_page"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("Exit", callback_data="exit")])
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "Select a topic to edit:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await message.reply_text(
                "Select a topic to edit:",
                reply_markup=InlineKeyboardMarkup(keyboard))
        
        return VIEW_TOPICS_INLINE
        
    except Exception as e:
        logger.error(f"Error listing topics: {e}")
        await message.reply_text("Error getting topics list.")
        return INSTRUCTOR_ACTIONS

async def handle_pagination(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    action = query.data
    pagination = context.user_data.get('topics_pagination', {'page': 0})
    
    if action == "prev_page":
        pagination['page'] -= 1
    elif action == "next_page":
        pagination['page'] += 1
    elif action == "exit":
        context.user_data.clear()
        await query.edit_message_text("You exited edit mode.")
        
        await query.message.reply_text(
            "Choose topic actions:",
            reply_markup=instructor_keyboard
        )
        
        return INSTRUCTOR_ACTIONS
    
    context.user_data['topics_pagination'] = pagination
    return await view_topics_inline(update, context)

async def topic_selected(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    try:
        raw_topic = query.data.replace("topic_", "", 1)
        topic_name = raw_topic.replace('_', ' ')
        context.user_data["selected_topic"] = topic_name
        topic_dir = os.path.join(TOPICS_DIR, topic_name)
        
        if not os.path.exists(topic_dir):
            await query.edit_message_text("Topic not found!")
            return await view_topics_inline(update, context)
        
        outcomes_path = os.path.join(topic_dir, OUTCOMES_FILENAME)
        conclusions = "No learning outcomes"
        if os.path.exists(outcomes_path):
            with open(outcomes_path, "r", encoding="utf-8") as f:
                content = f.read().split('\n', 1)
                if len(content) > 1:
                    conclusions = content[1]
        
        await query.edit_message_text(
            f"Topic: {topic_name}\n\nLearning outcomes:\n{conclusions[:3000]}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Download document", callback_data="download_doc"),
                    InlineKeyboardButton("Edit topic", callback_data="edit_topic")
                ],
                [InlineKeyboardButton("Back", callback_data="back_to_topics")]
            ])
        )
        return TOPIC_DETAILS
    except Exception as e:
        logger.error(f"Error in topic_selected: {e}")
        await query.edit_message_text("Error loading topic")
        return await view_topics_inline(update, context)

async def handle_topic_actions(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    action = query.data
    topic_name = context.user_data["selected_topic"]
    topic_dir = os.path.join(TOPICS_DIR, topic_name)
    
    if action == "download_doc":
        try:
            doc_path = os.path.join(topic_dir, PDF_FILENAME)
            
            await query.message.reply_document(
                document=open(doc_path, "rb"),
                filename=f"{topic_name}.pdf",
                reply_to_message_id=query.message.message_id
            )
            
            return TOPIC_DETAILS
            
        except Exception as e:
            logger.error(f"Error sending document: {e}")
            await query.message.reply_text("Error sending document")
            return await topic_selected(update, context)
    
    elif action == "edit_topic":
        context.user_data["current_topic"] = topic_name
        context.user_data["topic_dir"] = topic_dir
        outcomes_path = os.path.join(topic_dir, OUTCOMES_FILENAME)
        
        try:
            with open(outcomes_path, "r", encoding="utf-8") as f:
                context.user_data["gpt_response"] = f.read()
            
            await show_topic_info(update, context)
            return EDIT_TOPIC
            
        except Exception as e:
            logger.error(f"Error loading topic: {e}")
            await query.message.reply_text("Error loading topic")
            return await topic_selected(update, context)
    
    elif action == "back_to_topics":
        return await view_topics_inline(update, context)
    
    return TOPIC_DETAILS

async def view_learner_topics_inline(update: Update, context: CallbackContext) -> int:
    try:
        message = update.message or update.callback_query.message
        
        all_topics = [name for name in os.listdir(TOPICS_DIR) 
                    if os.path.isdir(os.path.join(TOPICS_DIR, name))]
        
        if not all_topics:
            await message.reply_text("No topics available for learning yet.")
            return AUTHORIZED
        
        context.user_data['learner_topics_pagination'] = {
            'page': 0,
            'topics': all_topics
        }
        return await show_learner_topics_page(update, context)
        
    except Exception as e:
        logger.error(f"Error listing topics: {e}")
        message = update.message or update.callback_query.message
        await message.reply_text("Error getting topics list.")
        return AUTHORIZED

async def show_learner_topics_page(update: Update, context: CallbackContext) -> int:
    pagination = context.user_data.get('learner_topics_pagination', {'page': 0, 'topics': []})
    page = pagination['page']
    topics = pagination['topics']
    
    PAGE_SIZE = 8
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_topics = topics[start:end]
    
    keyboard = []
    for topic in page_topics:
        topic_body = topic.replace(' ', '_').replace('/', '').replace('\\', '')[:40]
        keyboard.append([InlineKeyboardButton(topic, callback_data=f"learner_topic_{topic_body}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀ Back", callback_data="learner_prev_page"))
    if end < len(topics):
        nav_buttons.append(InlineKeyboardButton("Next ▶", callback_data="learner_next_page"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("Exit", callback_data="learner_exit")])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Select a topic to learn:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await (update.message or update.callback_query.message).reply_text(
            "Select a topic to learn:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    
    return VIEW_LEARNER_TOPICS_INLINE

async def handle_learner_pagination(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    action = query.data
    pagination = context.user_data.get('learner_topics_pagination', {'page': 0, 'topics': []})
    
    if action == "learner_prev_page":
        pagination['page'] -= 1
    elif action == "learner_next_page":
        pagination['page'] += 1
    elif action == "learner_exit":
        await query.edit_message_text("You exited topic viewing mode.")
        await query.message.reply_text(
            "Choose your role:",
            reply_markup=auth_keyboard
        )
        return AUTHORIZED
    
    context.user_data['learner_topics_pagination'] = pagination
    return await show_learner_topics_page(update, context)

async def learner_topic_selected(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    try:
        raw_topic = query.data.replace("learner_topic_", "", 1)
        topic_name = raw_topic.replace('_', ' ')
        context.user_data["current_learner_topic"] = topic_name
        topic_dir = os.path.join(TOPICS_DIR, topic_name)
        
        if not os.path.exists(topic_dir):
            await query.edit_message_text("Topic not found!")
            return await show_learner_topics_page(update, context)
        
        outcomes_path = os.path.join(topic_dir, OUTCOMES_FILENAME)
        conclusions = "No learning outcomes"
        if os.path.exists(outcomes_path):
            with open(outcomes_path, "r", encoding="utf-8") as f:
                content = f.read().split('\n', 1)
                if len(content) > 1:
                    conclusions = content[1]
        
        has_assessment = os.path.exists(os.path.join(topic_dir, ASSESSMENT_FILENAME))
        if(has_assessment):
            keyboard = [
                [InlineKeyboardButton("Take test", callback_data="start_test")],
                [InlineKeyboardButton("Download document", callback_data="learner_download")],
                [InlineKeyboardButton("Back to topics list", callback_data="learner_back")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("Download document", callback_data="learner_download")],
                [InlineKeyboardButton("Back to topics list", callback_data="learner_back")]
            ]
        
        await query.edit_message_text(
            f"Topic: {topic_name}\n\nLearning outcomes:\n{conclusions[:3000]}",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return LEARNER_TOPIC_DETAILS
    except Exception as e:
        logger.error(f"Error in learner_topic_selected: {e}")
        await query.edit_message_text("Error loading topic")
        return await show_learner_topics_page(update, context)

async def handle_learner_actions(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "learner_download":
        try:
            topic_name = context.user_data["current_learner_topic"]
            topic_dir = os.path.join(TOPICS_DIR, topic_name)
            doc_path = os.path.join(topic_dir, PDF_FILENAME)
            
            await query.message.reply_document(
                document=open(doc_path, "rb"),
                filename=f"{topic_name}.pdf",
                reply_to_message_id=query.message.message_id
            )
            
            return LEARNER_TOPIC_DETAILS
            
        except Exception as e:
            logger.error(f"Error sending document: {e}")
            await query.message.reply_text("Error sending document")
            return await learner_topic_selected(update, context)
    
    elif action == "learner_back":
        return await show_learner_topics_page(update, context)
    
    return LEARNER_TOPIC_DETAILS

async def view_topics(update: Update, context: CallbackContext) -> int:
    try:
        topics = [name for name in os.listdir(TOPICS_DIR) 
                 if os.path.isdir(os.path.join(TOPICS_DIR, name))]
        
        if not topics:
            await update.message.reply_text(
                "You don't have any saved topics yet.",
                reply_markup=auth_keyboard
            )
            return AUTHORIZED
        
        message = "Your saved topics:\n\n" + "\n".join(
            f"{i+1}. {topic}" for i, topic in enumerate(topics)
        )
        
        await update.message.reply_text(
            message,
            reply_markup=auth_keyboard
        )
        
        return AUTHORIZED
    except Exception as e:
        logger.error(f"Error listing topics: {e}")
        await update.message.reply_text(
            "Error getting topics list.",
            reply_markup=auth_keyboard
        )
        return AUTHORIZED

def extract_text_from_pdf(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text

async def ask_gpt(pdf_text: str, additional_prompt: str = "") -> str:
    try:
        prompt = f'{additional_prompt} Document is next:\n\n"{pdf_text}"\n\n'
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an assistant in identifying learning outcomes that a student can read after reading the document."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Error processing OpenAI request."

async def start_test(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    topic_name = context.user_data["current_learner_topic"]
    
    test = await load_assessment(topic_name)
    if not test:
        await query.message.reply_text("❌ Test not found for this topic")
        return LEARNER_TOPIC_DETAILS
    
    context.user_data["current_test"] = {
        **test,
        "current_question": 0,
        "score": 0,
        "answers": []
    }
    
    await show_question(
        update, 
        context,
        test["questions"][0],
        0,
        len(test["questions"])
    )
    return TAKING_TEST

async def show_question(update: Update, context: CallbackContext, question: Dict, q_num: int, total: int):
    context.user_data['current_test']['current_question'] = q_num
    
    keyboard = [
        [InlineKeyboardButton(option, callback_data=f"test_answer_{q_num}_{i}")]
        for i, option in enumerate(question["options"])
    ]
    
    text = (
        f"📚 Topic: {context.user_data['current_test']['topic']}\n\n"
        f"❓ Question {q_num+1}/{total}:\n"
        f"{question['question']}"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard))
    
async def back_to_topics(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    return await view_learner_topics_inline(update, context)

async def handle_test_answer(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    try:
        _, _, q_num, answer_idx = query.data.split('_')
        q_num = int(q_num)
        answer_idx = int(answer_idx)
        
        test_data = context.user_data['current_test']
        question = test_data['questions'][q_num]
        
        test_data.setdefault('answers', []).append({
            'question': question['question'],
            'user_answer': answer_idx,
            'correct_answer': question['correct'],
            'explanation': question.get('explanation', '')
        })

        if answer_idx == question['correct']:
            test_data['score'] += 1
            feedback = "✅ Correct!"
        else:
            correct_option = question['options'][question['correct']]
            feedback = f"❌ Wrong! Correct answer: {correct_option}"

        if 'explanation' in question:
            feedback += f"\n\n💡 Explanation: {question['explanation']}"

        keyboard = []
        next_q = q_num + 1
        
        if next_q < len(test_data['questions']):
            keyboard.append([InlineKeyboardButton("Next question →", callback_data=f"next_question_{next_q}")])
        else:
            keyboard.append([InlineKeyboardButton("View results", callback_data="show_results")])

        await query.edit_message_text(
            f"{feedback}\n\n"
            f"Question {q_num+1}/{len(test_data['questions'])}\n"
            f"{question['question']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return WAITING_FOR_NEXT

    except Exception as e:
        logger.error(f"Error in handle_test_answer: {e}")
        await query.message.reply_text("Error processing answer")
        return TAKING_TEST

async def next_question_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "show_results":
            await show_test_results(update, context)
            return TEST_RESULTS
        else:
            _, _, next_q = query.data.split('_')
            next_q = int(next_q)
            
            test_data = context.user_data['current_test']
            test_data['current_question'] = next_q
            
            await show_question(
                update, 
                context,
                test_data['questions'][next_q],
                next_q,
                len(test_data['questions'])
            )
            return TAKING_TEST
            
    except Exception as e:
        logger.error(f"Error in next_question_handler: {e}")
        await query.message.reply_text("Error moving to next question")
        return TAKING_TEST

async def show_test_results(update: Update, context: CallbackContext):
    test_data = context.user_data["current_test"]
    score = test_data["score"]
    total = len(test_data["questions"])
    percentage = score/total*100
    
    result_message = (
        f"📊 Test results for '{test_data['topic']}':\n"
        f"🔹 Correct answers: {score}/{total}\n"
        f"🔹 Success rate: {percentage:.0f}%\n\n"
    )
    
    if percentage < 70:
        result_message += "📝 Recommended to review material:\n"
        for answer in test_data["answers"]:
            if answer["user_answer"] != answer["correct_answer"]:
                result_message += f"\n• {answer['question']}\n"
                if answer["explanation"]:
                    result_message += f"  💡 {answer['explanation']}\n"
    
    keyboard = [
        [InlineKeyboardButton("Retake test", callback_data="restart_test")],
        [InlineKeyboardButton("Back to topics", callback_data="back_to_topics")]
    ]
    
    await update.callback_query.message.reply_text(
        result_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def restart_test(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    context.user_data["current_test"]["current_question"] = 0
    context.user_data["current_test"]["score"] = 0
    context.user_data["current_test"]["answers"] = []
    
    await show_question(
        update, 
        context,
        context.user_data["current_test"]["questions"][0],
        0,
        len(context.user_data["current_test"]["questions"]))
    return TAKING_TEST

async def generate_test_from_content(topic_name: str) -> Dict:
    topic_dir = os.path.join(TOPICS_DIR, topic_name)
    pdf_path = os.path.join(topic_dir, PDF_FILENAME)
    outcomes_path = os.path.join(topic_dir, OUTCOMES_FILENAME)
    
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        
        with open(outcomes_path, "r", encoding="utf-8") as f:
            outcomes_text = f.read()
        
        prompt = """
        You are given a document and the desired learning outcomes that learners should learn by reading this document. Your task is to generate a multiple choice test with one question for each outcome. Your answer is processed automatically and YOU DO NOT HAVE TO WRITE ANYTHING BUT THE TEST ITSELF IN THE CORRECT JSON FORMAT. Format:
        {
          "topic": "Topic Title",
          "questions": [
            {
              "question": "Question text",
              "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
              "correct": 0 (correct answer index),
              "explanation": "Brief explanation of the correct answer"
            }
          ]
        }
        Questions should:
        - Test understanding of key concepts from the document
        - Be aligned with the learning outcomes
        - Have one clear correct answer
        - Be in the same language as the source document
        """
        
        response = await ask_gpt_for_assesments(
            pdf_text=pdf_text,
            outcomes_text=outcomes_text,
            additional_prompt=prompt
        )
        
        cleaned_response = response.strip().replace("```json", "").replace("```", "")
        
        return json.loads(cleaned_response)
    
    except Exception as e:
        logger.error(f"Test generation error: {e}")
        return None

async def load_assessment(topic_name: str) -> Dict:
    topic_dir = os.path.join(TOPICS_DIR, topic_name)
    assessment_path = os.path.join(topic_dir, ASSESSMENT_FILENAME)
    
    if not os.path.exists(assessment_path):
        return None
        
    with open(assessment_path, "r", encoding="utf-8") as f:
        return json.load(f)

async def ask_gpt_for_assesments(pdf_text: str, outcomes_text: str, additional_prompt: str = "") -> str:
    try:
        prompt = f'{additional_prompt}\n Document is next:\n\n"{pdf_text}"\n\nOutcomes are next:\n\n"{outcomes_text}"\n\n'
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an assistant in creating simple multiple choice tests using source document of the course and learning outcomes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Error processing OpenAI request."

def sanitize_topic_name(topic: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        topic = topic.replace(char, '_')
    return topic[:40].strip()

async def show_topic_info(update: Update, context: CallbackContext) -> None:
    topic_name = context.user_data.get("current_topic", "Untitled")
    gpt_response = context.user_data.get("gpt_response", "")
    
    conclusions = gpt_response.split('\n', 1)[1] if '\n' in gpt_response else "No learning outcomes"
    
    topic_dir = context.user_data["topic_dir"]
    has_assessment = os.path.exists(os.path.join(topic_dir, ASSESSMENT_FILENAME))
    
    keyboard = [
        ["Change topic name", "Edit learning outcomes"],
        ["Create test" if not has_assessment else "View test", "Delete document"],
        ["Save learning outcomes"]
    ]
    
    message = f"Current topic: {topic_name}\n\nLearning outcomes:\n{conclusions[:4000]}"
    
    if update.message:
        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    
    if len(conclusions) > 4000:
        if update.message:
            await update.message.reply_text(
                "Full learning outcomes text saved to file.",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                "Full learning outcomes text saved to file.",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))

def get_unique_topic_dir(base_dir: str, topic_name: str) -> tuple[str, bool]:
    original_name = topic_name
    counter = 1
    was_renamed = False
    
    while True:
        topic_dir = os.path.join(base_dir, topic_name)
        if not os.path.exists(topic_dir):
            return topic_dir, was_renamed
        
        topic_name = f"{original_name} ({counter})"
        counter += 1
        was_renamed = True

async def upload_pdf(update: Update, context: CallbackContext) -> int:
    if document := update.message.document:
        if document.mime_type == "application/pdf":
            temp_pdf_path = os.path.join(TOPICS_DIR, f"temp_{document.file_name}")
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(temp_pdf_path)
            
            try:
                pdf_text = extract_text_from_pdf(temp_pdf_path)
                
                additional_prompt = (
                    "Analyze this document and write in first line document title "
                    "(what you would call the general topic of the document, if the document already has a general title, use it) "
                    "and after, separated by newline (starting from second line), a numbered list of learning outcomes that a person "
                    "who reads this document can get. Also, DO NOT WRITE ANYTHING BUT THE TITLE AND A NUMBERED LIST, because you are "
                    "not working with a person, but with a script that will break if your answer contains anything other than title "
                    "in first line and a numbered list. Answer in language on which the document is written."
                )
                
                await update.message.reply_text("Processing document with GPT...")
                gpt_response = await ask_gpt(pdf_text, additional_prompt)
                
                first_line_end = gpt_response.find('\n')
                if first_line_end == -1:
                    topic_name = "Untitled"
                else:
                    topic_name = gpt_response[:first_line_end].strip()
                
                topic_name = sanitize_topic_name(topic_name)
                
                topic_dir, was_renamed = get_unique_topic_dir(TOPICS_DIR, topic_name)
                
                if was_renamed:
                    new_topic_name = os.path.basename(topic_dir)
                    await update.message.reply_text(
                        f"Topic with name '{topic_name}' already exists. "
                        f"Will use name '{new_topic_name}'"
                    )
                    topic_name = new_topic_name
                
                os.makedirs(topic_dir, exist_ok=True)
                
                final_pdf_path = os.path.join(topic_dir, PDF_FILENAME)
                os.rename(temp_pdf_path, final_pdf_path)
                
                response_filename = os.path.join(topic_dir, OUTCOMES_FILENAME)
                with open(response_filename, "w", encoding="utf-8") as f:
                    f.write(gpt_response)
                
                context.user_data["current_topic"] = topic_name
                context.user_data["topic_dir"] = topic_dir
                context.user_data["gpt_response"] = gpt_response
                
                await show_topic_info(update, context)
                return EDIT_TOPIC
            except Exception as e:
                logger.error(f"PDF processing error: {e}")
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                await update.message.reply_text(
                    "Error processing PDF file.",
                    reply_markup=auth_keyboard
                )
                return AUTHORIZED
    
    await update.message.reply_text("Send PDF file:", reply_markup=auth_keyboard)
    return UPLOAD_PDF

async def edit_topic(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Change topic name":
        await update.message.reply_text("Enter new topic name:")
        return EDIT_TOPIC_NAME
    elif text == "Edit learning outcomes":
        await update.message.reply_text("Choose action:", reply_markup=edit_conclusions_keyboard)
        return EDIT_CONCLUSIONS
    elif text == "Delete document":
        await update.message.reply_text(
            "Are you sure you want to delete this document and all related data?",
            reply_markup=delete_confirm_keyboard
        )
        return DELETE_CONFIRM
    elif text == "Create test":
        return await generate_and_review_assessment(update, context)
    elif text == "View test":
        return await view_existing_assessment(update, context)
    elif text == "Save learning outcomes":
        await update.message.reply_text(
            "Topic saved",
            reply_markup=instructor_keyboard
        )
        return INSTRUCTOR_ACTIONS
    else:
        await show_topic_info(update, context)
        return EDIT_TOPIC

async def view_existing_assessment(update: Update, context: CallbackContext) -> int:
    topic_name = context.user_data["current_topic"]
    topic_dir = context.user_data["topic_dir"]
    
    try:
        test = await load_assessment(topic_name)
        if not test:
            await update.message.reply_text("❌ Test not found for this topic")
            return EDIT_TOPIC
        
        context.user_data["current_assessment"] = test
        
        formatted_test = format_test_for_display(test)
        
        keyboard = [
            [InlineKeyboardButton("Regenerate test", callback_data="regenerate_assessment")],
            [InlineKeyboardButton("Delete test", callback_data="delete_assessment")],
            [InlineKeyboardButton("Back to editing", callback_data="back_to_edit")]
        ]
        
        await update.message.reply_text(
            f"📝 Test for topic '{topic_name}':\n\n{formatted_test}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return REVIEW_ASSESSMENT
        
    except Exception as e:
        logger.error(f"Test loading error: {e}")
        await update.message.reply_text(
            "❌ Error loading test",
            reply_markup=edit_options_keyboard
        )
        return EDIT_TOPIC

async def generate_and_review_assessment(update: Update, context: CallbackContext) -> int:
    topic_name = context.user_data["current_topic"]
    topic_dir = context.user_data["topic_dir"]
    
    message = await update.message.reply_text("🔄 Generating test...")
    
    try:
        test = await generate_test_from_content(topic_name)
        
        if not test:
            await message.edit_text("❌ Failed to generate test")
            return EDIT_TOPIC
        
        context.user_data["current_assessment"] = test
        
        formatted_test = format_test_for_display(test)
        
        keyboard = [
            [InlineKeyboardButton("Regenerate with comment", callback_data="regenerate_assessment")],
            [InlineKeyboardButton("Save test", callback_data="save_assessment")],
            [InlineKeyboardButton("Cancel", callback_data="cancel_assessment")]
        ]
        
        await message.edit_text(
            f"📝 Generated test for topic '{topic_name}':\n\n{formatted_test}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return REVIEW_ASSESSMENT
        
    except Exception as e:
        logger.error(f"Test generation error: {e}")
        await message.edit_text("❌ Error generating test")
        return EDIT_TOPIC

def format_test_for_display(test: Dict) -> str:
    formatted = f"📚 Topic: {test['topic']}\n\n"
    for i, question in enumerate(test["questions"], 1):
        formatted += f"{i}. {question['question']}\n"
        for j, option in enumerate(question["options"]):
            prefix = "✓" if j == question["correct"] else "○"
            formatted += f"   {prefix} {option}\n"
        if "explanation" in question:
            formatted += f"   💡 {question['explanation']}\n"
        formatted += "\n"
    return formatted

async def back_to_edit(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    await query.delete_message()
    
    await show_topic_info(update, context)
    return EDIT_TOPIC

async def handle_assessment_actions(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    action = query.data
    topic_dir = context.user_data["topic_dir"]
    assessment_path = os.path.join(topic_dir, ASSESSMENT_FILENAME)
    
    if action == "regenerate_assessment":
        with open(assessment_path, "w", encoding="utf-8") as f:
            json.dump(context.user_data["current_assessment"], f, ensure_ascii=False, indent=2)
        
        await query.message.reply_text(
            "Enter your comment to improve the test:",
            reply_markup=ReplyKeyboardRemove()
        )
        return GENERATE_ASSESSMENT
        
    elif action == "save_assessment":
        with open(assessment_path, "w", encoding="utf-8") as f:
            json.dump(context.user_data["current_assessment"], f, ensure_ascii=False, indent=2)
        
        await show_topic_info(update, context)
        return EDIT_TOPIC
        
    elif action == "cancel_assessment":
        try:
            if os.path.exists(assessment_path):
                os.remove(assessment_path)
                await query.message.reply_text("❌ Test creation canceled, test file deleted.")
            else:
                await query.message.reply_text("❌ Test creation canceled.")
        except Exception as e:
            logger.error(f"Error canceling test: {e}")
            await query.message.reply_text("❌ Error canceling test.")
        
        await show_topic_info(update, context)
        return EDIT_TOPIC
    
    elif action == "delete_assessment":
        try:
            if os.path.exists(assessment_path):
                os.remove(assessment_path)
                await query.edit_message_text("✅ Test successfully deleted!")
            else:
                await query.edit_message_text("⚠️ Test not found, possibly already deleted")
            
            await show_topic_info(update, context)
            return EDIT_TOPIC
        except Exception as e:
            logger.error(f"Error deleting test: {e}")
            await query.edit_message_text("❌ Error deleting test")
            return REVIEW_ASSESSMENT
    
    elif action == "back_to_edit":
        await show_topic_info(update, context)
        return EDIT_TOPIC
    
    return REVIEW_ASSESSMENT

async def regenerate_assessment_with_comment(update: Update, context: CallbackContext) -> int:
    user_comment = update.message.text
    topic_name = context.user_data["current_topic"]
    topic_dir = context.user_data["topic_dir"]
    
    pdf_path = os.path.join(topic_dir, PDF_FILENAME)
    outcomes_path = os.path.join(topic_dir, OUTCOMES_FILENAME)
    assesment_path = os.path.join(topic_dir, ASSESSMENT_FILENAME)
    
    try:
        with open(assesment_path, "r", encoding="utf-8") as f:
            assesment_text = f.read()
        pdf_text = extract_text_from_pdf(pdf_path)
        with open(outcomes_path, "r", encoding="utf-8") as f:
            outcomes_text = f.read()
        
        prompt = f"""
        Please review the test taking into account the following IMPORTANT user comment:
        {user_comment}
        YOU DO NOT HAVE TO WRITE ANYTHING BUT THE TEST ITSELF IN THE CORRECT JSON FORMAT. Format:""" + """
        {
          "topic": "Topic Title",
          "questions": [
            {
              "question": "Question text",
              "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
              "correct": 0 (correct answer index),
              "explanation": "Brief explanation of the correct answer"
            }
          ]
        }
        Questions should:
        - Test understanding of key concepts from the document
        - Be aligned with the learning outcomes
        - Have one clear correct answer
        - Be in the same language as the source document

        Old test version:"{assesment_text}"
        """
        
        response = await ask_gpt_for_assesments(
            pdf_text=pdf_text,
            outcomes_text=outcomes_text,
            additional_prompt=prompt
        )
        
        cleaned_response = response.strip().replace("```json", "").replace("```", "")
        test = json.loads(cleaned_response)
        context.user_data["current_assessment"] = test
        
        formatted_test = format_test_for_display(test)
        keyboard = [
            [InlineKeyboardButton("Regenerate with comment", callback_data="regenerate_assessment")],
            [InlineKeyboardButton("Save test", callback_data="save_assessment")],
            [InlineKeyboardButton("Cancel", callback_data="cancel_assessment")]
        ]
        
        await update.message.reply_text(
            f"📝 Revised test for topic '{topic_name}':\n\n{formatted_test}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return REVIEW_ASSESSMENT
        
    except Exception as e:
        logger.error(f"Test regeneration error: {e}")
        await update.message.reply_text(
            "❌ Error regenerating test",
            reply_markup=edit_options_keyboard
        )
        return EDIT_TOPIC

async def delete_confirm(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Yes, delete":
        topic_dir = context.user_data.get("topic_dir")
        try:
            if topic_dir and os.path.exists(topic_dir):
                import shutil
                shutil.rmtree(topic_dir)
            
            await update.message.reply_text(
                "Document and all related data successfully deleted!",
                reply_markup=auth_keyboard
            )
            
            context.user_data.pop("current_topic", None)
            context.user_data.pop("topic_dir", None)
            context.user_data.pop("gpt_response", None)
            
            return AUTHORIZED
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            await update.message.reply_text(
                "Error deleting document. Please try again.",
                reply_markup=edit_options_keyboard
            )
            await show_topic_info(update, context)
            return EDIT_TOPIC
    else:
        await update.message.reply_text(
            "Deletion canceled.",
            reply_markup=edit_options_keyboard
        )
        await show_topic_info(update, context)
        return EDIT_TOPIC
    
async def edit_topic_name(update: Update, context: CallbackContext) -> int:
    new_topic_name = sanitize_topic_name(update.message.text)
    old_topic_dir = context.user_data["topic_dir"]
    
    topic_dir, was_renamed = get_unique_topic_dir(TOPICS_DIR, new_topic_name)
    if was_renamed:
        new_new_topic_name = os.path.basename(topic_dir)
        await update.message.reply_text(
            f"Topic with name '{new_topic_name}' already exists. "
            f"Will use name '{new_new_topic_name}'"
        )
        new_topic_name = new_new_topic_name
    
    new_topic_dir = topic_dir
    
    try:
        os.rename(old_topic_dir, new_topic_dir)
        
        context.user_data["current_topic"] = new_topic_name
        context.user_data["topic_dir"] = new_topic_dir
        
        await show_topic_info(update, context)
        return EDIT_TOPIC
    except Exception as e:
        logger.error(f"Error renaming topic: {e}")
        await update.message.reply_text(
            "Error changing topic name. Please try again.",
            reply_markup=edit_options_keyboard
        )
        return EDIT_TOPIC

async def edit_conclusions(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Rewrite learning outcomes":
        await update.message.reply_text(
            "Enter new learning outcomes (preferably a numbered list):",
            reply_markup=ReplyKeyboardRemove()
        )
        return REWRITE_CONCLUSIONS
    elif text == "Regenerate with comment":
        await update.message.reply_text(
            "Enter your comment to improve learning outcomes:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_COMMENT
    elif text == "Back":
        await show_topic_info(update, context)
        await update.message.reply_text(
            "Choose action:",
            reply_markup=edit_options_keyboard
        )
        return EDIT_TOPIC
    else:
        await update.message.reply_text(
            "Please use buttons to choose action",
            reply_markup=edit_conclusions_keyboard
        )
        return EDIT_CONCLUSIONS

async def rewrite_conclusions(update: Update, context: CallbackContext) -> int:
    if not update.message.text:
        await update.message.reply_text(
            "Please enter learning outcomes text",
            reply_markup=edit_conclusions_keyboard
        )
        return REWRITE_CONCLUSIONS

    new_conclusions = update.message.text
    topic_dir = context.user_data["topic_dir"]
    response_path = os.path.join(topic_dir, OUTCOMES_FILENAME)
    
    try:
        with open(response_path, "r", encoding="utf-8") as f:
            old_content = f.read().split('\n', 1)
            topic_title = old_content[0] if len(old_content) > 0 else "Untitled"
        
        with open(response_path, "w", encoding="utf-8") as f:
            f.write(f"{topic_title}\n{new_conclusions}")
        
        context.user_data["gpt_response"] = f"{topic_title}\n{new_conclusions}"
        
        await show_topic_info(update, context)
        return EDIT_TOPIC
    except Exception as e:
        logger.error(f"Error rewriting learning outcomes: {e}")
        await update.message.reply_text(
            "Error saving learning outcomes. Please try again.",
            reply_markup=edit_conclusions_keyboard
        )
        return EDIT_CONCLUSIONS

async def add_comment(update: Update, context: CallbackContext) -> int:
    user_comment = update.message.text
    topic_dir = context.user_data["topic_dir"]
    pdf_path = os.path.join(topic_dir, PDF_FILENAME)
    
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        
        additional_prompt = (
            f"User comment: {user_comment}\n\n"
            "Please regenerate the learning outcomes list based on the document and this comment. "
            "First line should be the document title, then a numbered list of outcomes. "
            "Answer in the same language as the document."
        )
        
        await update.message.reply_text("Regenerating learning outcomes with your comment...")
        gpt_response = await ask_gpt(pdf_text, additional_prompt)
        
        context.user_data["gpt_response"] = gpt_response
        response_filename = os.path.join(topic_dir, OUTCOMES_FILENAME)
        
        with open(response_filename, "w", encoding="utf-8") as f:
            f.write(gpt_response)
        
        await show_topic_info(update, context)
        return EDIT_TOPIC
    except Exception as e:
        logger.error(f"Error regenerating learning outcomes: {e}")
        await update.message.reply_text(
            "Error regenerating learning outcomes. Please try again.",
            reply_markup=edit_conclusions_keyboard
        )
        return EDIT_CONCLUSIONS

async def cancel(update: Update, context: CallbackContext) -> int:
    if "temp_pdf_path" in context.user_data and os.path.exists(context.user_data["temp_pdf_path"]):
        os.remove(context.user_data["temp_pdf_path"])
    context.user_data.clear()
    await update.message.reply_text("Session reset.", reply_markup=main_keyboard)
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT & ~filters.COMMAND, start_with_command)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_pass)],
            LOGIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_name)],
            LOGIN_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_pass)],
            AUTHORIZED: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth_actions)],
            UPLOAD_PDF: [MessageHandler(filters.Document.ALL, upload_pdf)],
            FROM_REG_TO_LOG: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_reg_to_log)],
            EDIT_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_topic)],
            EDIT_TOPIC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_topic_name)],
            EDIT_CONCLUSIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_conclusions)],
            DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_confirm)],
            REWRITE_CONCLUSIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, rewrite_conclusions)],
            ADD_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_comment)],
            VIEW_TOPICS: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_topics)],

            VIEW_TOPICS_INLINE: [
                CallbackQueryHandler(handle_pagination, pattern=r"^(prev_page|next_page|exit)$"),
                CallbackQueryHandler(topic_selected, pattern=r"^topic_")
            ],
            VIEW_LEARNER_TOPICS_INLINE: [
                CallbackQueryHandler(handle_learner_pagination, pattern=r"^learner_(prev_page|next_page|exit)$"),
                CallbackQueryHandler(learner_topic_selected, pattern=r"^learner_topic_")
            ],
            TOPIC_DETAILS: [
                CallbackQueryHandler(handle_topic_actions),
            ],
            LEARNER_TOPIC_DETAILS: [
                CallbackQueryHandler(start_test, pattern="^start_test$"),
                CallbackQueryHandler(handle_learner_actions)
            ],
            INSTRUCTOR_ACTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, instructor_actions)
            ],
            TAKING_TEST: [
                CallbackQueryHandler(handle_test_answer, pattern=r"^test_answer_\d+_\d+$")
            ],
            TEST_RESULTS: [
                CallbackQueryHandler(restart_test, pattern="^restart_test$"),
                CallbackQueryHandler(back_to_topics, pattern="^back_to_topics$")
            ],
            WAITING_FOR_NEXT: [
                CallbackQueryHandler(next_question_handler, pattern=r"^(next_question_\d+|show_results)$")
            ],
            GENERATE_ASSESSMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, regenerate_assessment_with_comment)
            ],
            REVIEW_ASSESSMENT: [
                CallbackQueryHandler(handle_assessment_actions),
                CallbackQueryHandler(back_to_edit, pattern="^back_to_edit$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
