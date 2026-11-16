from flask import Flask, render_template, redirect, url_for, request, abort, flash
from models import db, User, Course, Exam, Rubric, Slot, Booking, Evaluation, RubricMark
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, time
from functools import wraps
from sqlalchemy import or_

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

def examiner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'examiner' or not current_user.is_approved:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

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
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'examiner':
        if not current_user.is_approved:
            return render_template('dashboard.html')
        return redirect(url_for('examiner_dashboard'))
    elif current_user.role == 'student':
        return redirect(url_for('student_dashboard'))
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    counts = {
        'courses': Course.query.count(),
        'exams': Exam.query.count(),
        'examiners': User.query.filter_by(role='examiner').count(),
        'students': User.query.filter_by(role='student').count(),
        'slots': Slot.query.count(),
        'bookings': Booking.query.count()
    }
    
    search_query = request.args.get('q', '')
    results = {'exams': [], 'students': [], 'examiners': [], 'bookings': []}
    
    if search_query:
        results['exams'] = Exam.query.filter(or_(Exam.name.ilike(f'%{search_query}%'), Exam.id == (int(search_query) if search_query.isdigit() else 0))).all()
        results['students'] = User.query.filter(User.role == 'student', or_(User.username.ilike(f'%{search_query}%'), User.email.ilike(f'%{search_query}%'), User.id == (int(search_query) if search_query.isdigit() else 0))).all()
        results['examiners'] = User.query.filter(User.role == 'examiner', or_(User.username.ilike(f'%{search_query}%'), User.email.ilike(f'%{search_query}%'), User.id == (int(search_query) if search_query.isdigit() else 0))).all()
        results['bookings'] = Booking.query.filter(or_(Booking.id == (int(search_query) if search_query.isdigit() else 0))).all()

    all_bookings = Booking.query.all()
    all_slots = Slot.query.all()
    
    return render_template('admin/dashboard.html', counts=counts, search_query=search_query, results=results, all_bookings=all_bookings, all_slots=all_slots)

@app.route('/admin/booking/<int:booking_id>/reschedule', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_reschedule(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    available_slots = Slot.query.filter_by(exam_id=booking.exam_id, status='Available').all()
    
    if request.method == 'POST':
        new_slot_id = int(request.form.get('new_slot_id'))
        new_slot = db.get_or_404(Slot, new_slot_id)
        
        if new_slot.status != 'Available' or new_slot.booked_count >= new_slot.capacity:
            flash('Selected slot is full.', 'error')
            return redirect(url_for('admin_reschedule', booking_id=booking.id))
            
        old_slot = booking.slot
        old_slot.booked_count -= 1
        if old_slot.status == 'Full':
            old_slot.status = 'Available'
            
        booking.slot_id = new_slot.id
        new_slot.booked_count += 1
        if new_slot.booked_count >= new_slot.capacity:
            new_slot.status = 'Full'
            
        db.session.commit()
        flash('Booking rescheduled successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin/reschedule.html', booking=booking, available_slots=available_slots)

@app.route('/admin/slot/<int:slot_id>/change_examiner', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_change_examiner(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    approved_examiners = User.query.filter_by(role='examiner', is_approved=True).all()
    
    if request.method == 'POST':
        new_examiner_id = int(request.form.get('new_examiner_id'))
        slot.examiner_id = new_examiner_id
        db.session.commit()
        flash('Examiner reassigned successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin/change_examiner.html', slot=slot, approved_examiners=approved_examiners)

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
        flash('Exam updated successfully.', 'success')
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

@app.route('/examiner/dashboard')
@login_required
@examiner_required
def examiner_dashboard():
    exams = Exam.query.filter(Exam.status.in_(['Slot Creation', 'Booking Open', 'Closed'])).all()
    slots = Slot.query.filter_by(examiner_id=current_user.id).all()
    return render_template('examiner/dashboard.html', exams=exams, slots=slots)

@app.route('/examiner/exam/<int:exam_id>/slot/new', methods=['GET', 'POST'])
@login_required
@examiner_required
def create_slot(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    now = datetime.now()
    if not (exam.slot_start <= now <= exam.slot_end):
        flash('Slot creation window is not active for this exam.', 'error')
        return redirect(url_for('examiner_dashboard'))
    if request.method == 'POST':
        slot_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        capacity = int(request.form.get('capacity'))
        slot = Slot(
            exam_id=exam.id,
            examiner_id=current_user.id,
            date=slot_date,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            booked_count=0,
            status='Available'
        )
        db.session.add(slot)
        db.session.commit()
        flash('Slot created successfully.', 'success')
        return redirect(url_for('examiner_dashboard'))
    return render_template('examiner/create_slot.html', exam=exam)

@app.route('/examiner/slot/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@examiner_required
def edit_slot(id):
    slot = db.get_or_404(Slot, id)
    if slot.examiner_id != current_user.id:
        abort(403)
    now = datetime.now()
    if now >= slot.exam.booking_start:
        flash('Cannot edit slot after booking has started.', 'error')
        return redirect(url_for('examiner_dashboard'))
    if request.method == 'POST':
        slot.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        slot.start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        slot.end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        slot.capacity = int(request.form.get('capacity'))
        db.session.commit()
        flash('Slot updated successfully.', 'success')
        return redirect(url_for('examiner_dashboard'))
    return render_template('examiner/edit_slot.html', slot=slot)

@app.route('/examiner/slot/<int:id>/delete', methods=['POST'])
@login_required
@examiner_required
def delete_slot(id):
    slot = db.get_or_404(Slot, id)
    if slot.examiner_id != current_user.id:
        abort(403)
    now = datetime.now()
    if now >= slot.exam.booking_start:
        flash('Cannot delete slot after booking has started.', 'error')
        return redirect(url_for('examiner_dashboard'))
    db.session.delete(slot)
    db.session.commit()
    flash('Slot deleted successfully.', 'success')
    return redirect(url_for('examiner_dashboard'))

@app.route('/examiner/slot/<int:id>/students')
@login_required
@examiner_required
def view_slot_students(id):
    slot = db.get_or_404(Slot, id)
    if slot.examiner_id != current_user.id:
        abort(403)
    return render_template('examiner/view_slot_students.html', slot=slot)

@app.route('/examiner/booking/<int:booking_id>/evaluate', methods=['GET', 'POST'])
@login_required
@examiner_required
def evaluate_student(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.slot.examiner_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        total_marks = 0.0
        rubric_marks_list = []
        for rubric in booking.exam.rubrics:
            awarded = float(request.form.get(f'rubric_{rubric.id}', 0))
            total_marks += awarded
            rubric_marks_list.append((rubric.id, awarded))
        
        remarks = request.form.get('remarks')
        
        evaluation = Evaluation(
            booking_id=booking.id,
            examiner_id=current_user.id,
            remarks=remarks,
            total_marks=total_marks
        )
        db.session.add(evaluation)
        db.session.flush()
        
        for r_id, marks in rubric_marks_list:
            rm = RubricMark(
                evaluation_id=evaluation.id,
                rubric_id=r_id,
                marks_awarded=marks
            )
            db.session.add(rm)
        
        booking.status = 'Completed'
        db.session.commit()
        flash('Evaluation submitted successfully.', 'success')
        return redirect(url_for('view_slot_students', id=booking.slot_id))
    return render_template('examiner/evaluate_student.html', booking=booking)

@app.route('/student/dashboard')
@login_required
@student_required
def student_dashboard():
    search_query = request.args.get('q', '')
    exams_query = Exam.query.filter(Exam.status.in_(['Booking Open', 'Closed']))
    if search_query:
        exams_query = exams_query.join(Course).filter(
            or_(
                Exam.name.ilike(f'%{search_query}%'),
                Course.code.ilike(f'%{search_query}%'),
                Course.name.ilike(f'%{search_query}%')
            )
        )
    exams = exams_query.all()
    bookings = Booking.query.filter_by(student_id=current_user.id).all()
    return render_template('student/dashboard.html', exams=exams, bookings=bookings, search_query=search_query)

@app.route('/student/slot/<int:slot_id>/book', methods=['POST'])
@login_required
@student_required
def book_slot(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    exam = slot.exam
    now = datetime.now()

    if not (exam.booking_start <= now <= exam.booking_end):
        flash('Booking period is not active for this exam.', 'error')
        return redirect(url_for('student_dashboard'))

    existing_active_booking = Booking.query.filter_by(
        student_id=current_user.id,
        exam_id=exam.id,
        status='Booked'
    ).first()

    if existing_active_booking:
        flash('You already have an active booking for this exam.', 'error')
        return redirect(url_for('student_dashboard'))

    if slot.status != 'Available' or slot.booked_count >= slot.capacity:
        flash('Selected slot is full.', 'error')
        return redirect(url_for('student_dashboard'))

    booking = Booking(
        slot_id=slot.id,
        student_id=current_user.id,
        exam_id=exam.id,
        status='Booked'
    )
    db.session.add(booking)

    slot.booked_count += 1
    if slot.booked_count >= slot.capacity:
        slot.status = 'Full'

    db.session.commit()
    flash('Slot booked successfully.', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/booking/<int:booking_id>/cancel', methods=['POST'])
@login_required
@student_required
def cancel_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.student_id != current_user.id:
        abort(403)

    exam = booking.exam
    now = datetime.now()

    if now > exam.booking_end:
        flash('Cannot cancel booking after the booking deadline.', 'error')
        return redirect(url_for('student_dashboard'))

    if booking.status != 'Booked':
        flash('Booking is not active.', 'error')
        return redirect(url_for('student_dashboard'))

    booking.status = 'Cancelled'
    slot = booking.slot
    slot.booked_count -= 1
    if slot.status == 'Full':
        slot.status = 'Available'

    db.session.commit()
    flash('Booking cancelled successfully.', 'success')
    return redirect(url_for('student_dashboard'))

if __name__ == '__main__':
    seed_admin()
    app.run(debug=True)