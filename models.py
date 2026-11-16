from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin


db = SQLAlchemy()

class User(db.Model, UserMixin):
    """Stores all users (Admin, Examiner, Student) in a single table with a role column."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_approved = db.Column(db.Boolean, default=False) 

    # Relationships
    slots_created = db.relationship('Slot', backref='examiner', lazy=True)
    bookings = db.relationship('Booking', backref='student', lazy=True)
    evaluations_given = db.relationship('Evaluation', backref='examiner', lazy=True)


class Course(db.Model):
    """Represents university courses managed by the admin."""
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Active')  

    exams = db.relationship('Exam', backref='course', lazy=True, cascade='all, delete-orphan')


class Exam(db.Model):
    """Represents an exam session for a course with specific timelines and types."""
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    exam_type = db.Column(db.String(30), nullable=False) 
    duration_minutes = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    
    # Timeline windows
    slot_start = db.Column(db.DateTime, nullable=False)
    slot_end = db.Column(db.DateTime, nullable=False)
    booking_start = db.Column(db.DateTime, nullable=False)
    booking_end = db.Column(db.DateTime, nullable=False)
    
    status = db.Column(db.String(30), default='Draft')  

    rubrics = db.relationship('Rubric', backref='exam', lazy=True, cascade='all, delete-orphan')
    slots = db.relationship('Slot', backref='exam', lazy=True, cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='exam', lazy=True, cascade='all, delete-orphan')


class Rubric(db.Model):
    """Grading criteria defined for an exam."""
    __tablename__ = 'rubrics'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    criterion_name = db.Column(db.String(100), nullable=False)
    max_marks = db.Column(db.Float, nullable=False)
    weightage = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)

    marks = db.relationship('RubricMark', backref='rubric', lazy=True, cascade='all, delete-orphan')


class Slot(db.Model):
    """Time slots created by examiners for exams."""
    __tablename__ = 'slots'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    booked_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='Available')  

    bookings = db.relationship('Booking', backref='slot', lazy=True)


class Booking(db.Model):
    """Student exam slot bookings maintaining complete history."""
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slots.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    status = db.Column(db.String(20), default='Booked')  

    evaluation = db.relationship('Evaluation', backref='booking', uselist=False, cascade='all, delete-orphan')


class Evaluation(db.Model):
    """Examiner evaluation record for a student's booked slot."""
    __tablename__ = 'evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    total_marks = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    rubric_marks = db.relationship('RubricMark', backref='evaluation', lazy=True, cascade='all, delete-orphan')


class RubricMark(db.Model):
    """Marks awarded per rubric criterion during an evaluation."""
    __tablename__ = 'rubric_marks'
    
    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey('evaluations.id'), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey('rubrics.id'), nullable=False)
    marks_awarded = db.Column(db.Float, nullable=False)