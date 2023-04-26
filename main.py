import sqlite3

from flask import Flask, render_template, abort, request, flash, url_for
from flask_restful import Api
from werkzeug.utils import redirect, secure_filename

from data import db_session, news_api
from data.users import User
from data.news import News
from forms.user import RegisterForm, LoginForm
from flask_login import LoginManager, login_user, logout_user, login_required, \
    current_user
import json
from forms.news import NewsForm
import os


UPLOAD_FOLDER = os.path.abspath(os.curdir) + r"\static\users_files"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
api = Api(app)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

login_manager = LoginManager()
login_manager.init_app(app)


def allowed_file(filename):
    """ Функция проверки расширения файла """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # проверим, передается ли в запросе файл
        if 'file' not in request.files:
            # После перенаправления на страницу загрузки
            # покажем сообщение пользователю
            flash('Не могу прочитать файл')
            return redirect(request.url)
        file = request.files['file']
        # Если файл не выбран, то браузер может
        # отправить пустой файл без имени.
        if file.filename == '':
            flash('Нет выбранного файла')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            # безопасно извлекаем оригинальное имя файла
            filename = secure_filename(file.filename)
            # сохраняем файл
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # если все прошло успешно, то перенаправляем
            # на функцию-представление `download_file`
            # для скачивания файла
            conn = sqlite3.connect("db/blogs.db")
            cur = conn.cursor()
            res = cur.execute(f"""UPDATE users
                                 SET avatar = '{filename}'
                                 WHERE id = {current_user.id}""")
            conn.commit()
            return redirect("/profile_settings")
    return render_template("upload.html")

@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


def main():  # главная функция запуска сайта
    db_session.global_init("db/blogs.db")
    app.register_blueprint(news_api.blueprint)
    app.run()


@app.route("/")
def index():  # главная страница сайта
    db_sess = db_session.create_session()
    if current_user.is_authenticated:
        news = db_sess.query(News).filter(
            (News.user == current_user) | (News.is_private != True))
    else:
        news = db_sess.query(News).filter(News.is_private != True)
    return render_template("index.html", news=news)


@app.route("/profile")
def profile():  # вкладка профиля
    db_sess = db_session.create_session()
    if current_user.is_authenticated:
        news = db_sess.query(News).filter(
            News.user == current_user)
    else:
        error_ = 101
    # если пользователь не зарегистрирован то перекидывает на страницу ошибки
        return redirect(f"/error/{error_}")

    return render_template("profile.html", news=news)


@app.route("/profile_settings")
def profile_settings():  # вкладка профиля
    db_sess = db_session.create_session()
    if not current_user.is_authenticated:
        error_ = 101
    # если пользователь не зарегистрирован то перекидывает на страницу ошибки
        return redirect(f"/error/{error_}")

    return render_template("profile_settings.html")



@app.route("/error/<error_code>", methods=['GET', 'POST'])
def error(error_code):  # страница ошибки
    with open('data/errors_codes.json', 'r',
              encoding='utf-8') as f:
        codes = json.load(f)

    return render_template("error_window.html", error_name="Упс!",
                           error_text=codes[error_code])


@app.route("/like/<news_id>", methods=['GET', 'POST'])
def like(news_id):  # системная страница, чтобы ставить лайки
    db_sess = db_session.create_session()
    new = db_sess.query(News).filter(News.id == news_id).first()
    if current_user.name not in str(new.liked_users):
        conn = sqlite3.connect("db/blogs.db")
        cur = conn.cursor()
        res = cur.execute(f"""UPDATE news
                            SET likes = {new.likes + 1}
                            WHERE id = {news_id}""")
        if new.liked_users:
            res1 = cur.execute(f"""UPDATE news
                                  SET liked_users = '{str(new.liked_users)
                                                      + f";{current_user.name}"}'
                                  WHERE id = {news_id}""")
        else:
            res1 = cur.execute(f"""UPDATE news
                                  SET liked_users = '{current_user.name}'
                                  WHERE id = {news_id}""")
        conn.commit()
    print(new.id)
    return redirect(f"/#{new.id}")


@app.route("/dislike/<news_id>", methods=['GET', 'POST'])
def dislike(news_id):  # страница для дизлайков
    db_sess = db_session.create_session()
    new = db_sess.query(News).filter(News.id == news_id).first()
    if current_user.name in str(new.liked_users):
        conn = sqlite3.connect("db/blogs.db")
        cur = conn.cursor()
        res = cur.execute(f"""UPDATE news
                            SET likes = {new.likes - 1}
                            WHERE id = {news_id}""")
        if ";" not in new.liked_users:
            res1 = cur.execute(f"""UPDATE news
                                  SET liked_users = '{str(new.liked_users).
                               replace(f"{current_user.name}", "")}'
                                  WHERE id = {news_id}""")
        else:
            res1 = cur.execute(f"""UPDATE news
                                   SET liked_users = '{str(new.liked_users).
                               replace(f";{current_user.name}", "")}'
                                              WHERE id = {news_id}""")
        conn.commit()
    print(new.id)
    return redirect(f"/#{new.id}")


@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Такой пользователь уже есть")
        user = User(
            name=form.name.data,
            email=form.email.data,
            about=form.about.data
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')
    return render_template('register.html', title='Регистрация', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/news', methods=['GET', 'POST'])
@login_required
def add_news():
    form = NewsForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        news = News()
        news.title = form.title.data
        news.content = form.content.data
        news.is_private = form.is_private.data
        current_user.news.append(news)
        db_sess.merge(current_user)
        db_sess.commit()
        return redirect('/')
    return render_template('news.html', title='Добавление новости',
                           form=form)


@app.route('/news/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_news(id):
    form = NewsForm()
    if request.method == "GET":
        db_sess = db_session.create_session()
        news = db_sess.query(News).filter(News.id == id,
                                          News.user == current_user
                                          ).first()
        if news:
            form.title.data = news.title
            form.content.data = news.content
            form.is_private.data = news.is_private
        else:
            abort(404)
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        news = db_sess.query(News).filter(News.id == id,
                                          News.user == current_user
                                          ).first()
        if news:
            news.title = form.title.data
            news.content = form.content.data
            news.is_private = form.is_private.data
            db_sess.commit()
            return redirect('/')
        else:
            abort(404)
    return render_template('news.html',
                           title='Редактирование новости',
                           form=form
                           )


@app.route('/news_delete/<int:id>', methods=['GET', 'POST'])
@login_required
def news_delete(id):
    db_sess = db_session.create_session()
    news = db_sess.query(News).filter(News.id == id,
                                      News.user == current_user
                                      ).first()
    if news:
        db_sess.delete(news)
        db_sess.commit()
    else:
        abort(404)
    return redirect('/')


if __name__ == '__main__':
    main()
