from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, RadioField, SelectMultipleField, SubmitField
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from io import BytesIO
import base64
import matplotlib
matplotlib.use('Agg')  # Устанавливаем бэкенд 'Agg' для matplotlib
import matplotlib.pyplot as plt


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///survey.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Модель для хранения ответов на анкету
class SurveyResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    interests = db.Column(db.String(200))
    comments = db.Column(db.Text)

# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(10000))
    responses = db.relationship('SurveyResponse', backref='user', lazy=True)

# Загрузчик пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Кастомный ModelView с проверкой прав доступа
class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.username == 'admin'

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

# Инициализация Flask-Admin
admin = Admin(app, name='Админка', template_mode='bootstrap3')
admin.add_view(AdminModelView(User, db.session))
admin.add_view(AdminModelView(SurveyResponse, db.session))

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь вы можете войти.')
        return redirect(url_for('login'))

    return render_template('register.html')


# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль.')

    return render_template('login.html')

# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# Маршрут для отображения формы
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Маршрут для обработки данных формы
@app.route('/submit', methods=['POST'])
@login_required
def submit():
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        interests = ", ".join(request.form.getlist('interests'))
        comments = request.form.get('comments')

        response = SurveyResponse(
            user_id=current_user.id,
            name=name,
            age=age,
            gender=gender,
            interests=interests,
            comments=comments
        )
        db.session.add(response)
        db.session.commit()

        return redirect(url_for('thank_you'))

@app.route('/results')
@login_required
def results():
    # Получаем все ответы из базы данных
    responses = SurveyResponse.query.all()

    # Подсчет распределения по полу
    genders = [response.gender for response in responses]
    gender_counts = {gender: genders.count(gender) for gender in set(genders)}

    # Создание графика
    plt.bar(gender_counts.keys(), gender_counts.values())
    plt.xlabel('Пол')
    plt.ylabel('Количество ответов')
    plt.title('Распределение по полу')

    # Сохранение графика в формате base64
    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')  # Сохраняем график в буфер
    img.seek(0)  # Перемещаем указатель в начало буфера
    plot_url = base64.b64encode(img.getvalue()).decode()  # Кодируем в base64
    plt.close()  # Закрываем график, чтобы освободить память

    # Передаем график в шаблон
    return render_template('results.html', plot_url=plot_url)

# Маршрут для страницы благодарности
@app.route('/thank_you')
@login_required
def thank_you():
    user_name = current_user.username
    return render_template('thank_you.html', user_name=user_name)

# Создание таблиц в базе данных
with app.app_context():
    db.create_all()
# Проверка, существует ли пользователь 'admin'
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        # Создание пользователя 'admin', если он не существует
        admin_user = User(username='admin', password=generate_password_hash('admin123'))
        db.session.add(admin_user)
        db.session.commit()
        print("Пользователь 'admin' создан.")
    else:
        print("Пользователь 'admin' уже существует.")

if __name__ == '__main__':
    app.run(debug=True)
