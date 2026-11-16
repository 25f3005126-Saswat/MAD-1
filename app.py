from flask import Flask, render_template, redirect, url_for, request, abort, flash
from models import db, User, Course, Exam, Rubric, Slot, Booking, Evaluation, RubricMark
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'emp_secure_university_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def seed_admin():
    with app.app_context():
        db.create_all()
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            hashed_pw = generate_password_hash('Admin@123')
            admin = User(
                username='admin',
                email='admin@emp.com',
                password_hash=hashed_pw,
                role='admin',
                is_approved=True
            )
            db.session.add(admin)
            db.session.commit()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.', 'error')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password)
        is_approved = True if role == 'student' else False
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_pw,
            role=role,
            is_approved=is_approved
        )
        db.session.add(new_user)
        db.session.commit()
        if role == 'examiner':
            flash('Registration successful! Please wait for Admin approval.', 'success')
        else:
            flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/courses', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_courses():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        description = request.form.get('description')
        status = request.form.get('status', 'Active')
        course = Course(code=code, name=name, description=description, status=status)
        db.session.add(course)
        db.session.commit()
        flash('Course added successfully.', 'success')
        return redirect(url_for('manage_courses'))
    courses = Course.query.all()
    return render_template('admin/courses.html', courses=courses)

@app.route('/admin/course/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_course(id):
    course = db.get_or_404(Course, id)
    if request.method == 'POST':
        course.code = request.form.get('code')
        course.name = request.form.get('name')
        course.description = request.form.get('description')
        course.status = request.form.get('status')
        db.session.commit()
        flash('Course updated successfully.', 'success')
        return redirect(url_for('manage_courses'))
    return render_template('admin/edit_course.html', course=course)

@app.route('/admin/course/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_course(id):
    course = db.get_or_404(Course, id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully.', 'success')
    return redirect(url_for('manage_courses'))

@app.route('/admin/exams', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_exams():
    courses = Course.query.filter_by(status='Active').all()
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        name = request.form.get('name')
        exam_type = request.form.get('exam_type')
        duration_minutes = int(request.form.get('duration_minutes'))
        max_marks = int(request.form.get('max_marks'))
        slot_start = datetime.strptime(request.form.get('slot_start'), '%Y-%m-%dT%H:%M')
        slot_end = datetime.strptime(request.form.get('slot_end'), '%Y-%m-%dT%H:%M')
        booking_start = datetime.strptime(request.form.get('booking_start'), '%Y-%m-%dT%H:%M')
        booking_end = datetime.strptime(request.form.get('booking_end'), '%Y-%m-%dT%H:%M')
        status = request.form.get('status', 'Draft')

        exam = Exam(
            course_id=course_id,
            name=name,
            exam_type=exam_type,
            duration_minutes=duration_minutes,
            max_marks=max_marks,
            slot_start=slot_start,
            slot_end=slot_end,
            booking_start=booking_start,
            booking_end=booking_end,
            status=status
        )
        db.session.add(exam)
        db.session.commit()
        flash('Exam created successfully.', 'success')
        return redirect(url_for('manage_exams'))
    exams = Exam.query.all()
    return render_template('admin/exams.html', exams=exams, courses=courses)

@app.route('/admin/exam/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_exam(id):
    exam = db.get_or_404(Exam, id)
    courses = Course.query.filter_by(status='Active').all()
    if request.method == 'POST':
        exam.course_id = request.form.get('course_id')
        exam.name = request.form.get('name')
        exam.exam_type = request.form.get('exam_type')
        exam.duration_minutes = int(request.form.get('duration_minutes'))
        exam.max_marks = int(request.form.get('max_marks'))
        exam.slot_start = datetime.strptime(request.form.get('slot_start'), '%Y-%m-%dT%H:%M')
        exam.slot_end = datetime.strptime(request.form.get('slot_end'), '%Y-%m-%dT%H:%M')
        exam.booking_start = datetime.strptime(request.form.get('booking_start'), '%Y-%m-%dT%H:%M')
        exam.booking_end = datetime.strptime(request.form.get('booking_end'), '%Y-%m-%dT%H:%M')
        exam.status = request.form.get('status')
        db.session.commit()
        flash('Exam updated from edit page.', 'success')
        return redirect(url_for('manage_exams'))
    return render_template('admin/edit_exam.html', exam=exam, courses=courses)

@app.route('/admin/exam/<int:id>/rubrics', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_rubrics(id):
    exam = db.get_or_404(Exam, id)
    if request.method == 'POST':
        criterion_name = request.form.get('criterion_name')
        max_marks = float(request.form.get('max_marks'))
        weightage = float(request.form.get('weightage'))
        description = request.form.get('description')
        rubric = Rubric(exam_id=exam.id, criterion_name=criterion_name, max_marks=max_marks, weightage=weightage, description=description)
        db.session.add(rubric)
        db.session.commit()
        flash('Rubric criterion added.', 'success')
        return redirect(url_for('manage_rubrics', id=exam.id))
    return render_template('admin/rubrics.html', exam=exam)

@app.route('/admin/rubric/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_rubric(id):
    rubric = db.get_or_404(Rubric, id)
    exam_id = rubric.exam_id
    db.session.delete(rubric)
    db.session.commit()
    flash('Rubric criterion deleted.', 'success')
    return redirect(url_for('manage_rubrics', id=exam_id))

@app.route('/admin/examiners')
@login_required
@admin_required
def manage_examiners():
    examiners = User.query.filter_by(role='examiner').all()
    return render_template('admin/examiners.html', examiners=examiners)

@app.route('/admin/examiner/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_examiner(id):
    examiner = db.get_or_404(User, id)
    if examiner.role == 'examiner':
        examiner.is_approved = True
        db.session.commit()
        flash('Examiner approved successfully.', 'success')
    return redirect(url_for('manage_examiners'))

@app.route('/admin/examiner/<int:id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_examiner(id):
    examiner = db.get_or_404(User, id)
    if examiner.role == 'examiner':
        examiner.is_approved = False
        db.session.commit()
        flash('Examiner deactivated successfully.', 'success')
    return redirect(url_for('manage_examiners'))

if __name__ == '__main__':
    seed_admin()
    app.run(debug=True)