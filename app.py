from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from ortools.sat.python import cp_model
from flask import render_template

import os
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///schedtrack.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    department = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    department = db.Column(db.String(50), nullable=False)
    hours_per_week = db.Column(db.Integer, default=3)

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    room_type = db.Column(db.String(30), nullable=False)
    building = db.Column(db.String(50), nullable=False)

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    version_name = db.Column(db.String(100), nullable=False)
    schedule_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

# Timetable Generation Engine
class TimetableGenerator:
    def __init__(self, faculty_list, subjects_list, classrooms_list, constraints_list):
        self.faculty = faculty_list
        self.subjects = subjects_list
        self.classrooms = classrooms_list
        self.constraints = constraints_list
        

       

        # Time slots (9 AM to 5 PM, excluding 12-1 PM lunch)
        self.time_slots = [
            "9:00-10:00", "10:00-11:00", "11:00-12:00",
            "1:00-2:00", "2:00-3:00", "3:00-4:00", "4:00-5:00"
        ]
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        
    def generate_timetable(self):
        model = cp_model.CpModel()
        
        # Decision variables
        # x[s][f][r][d][t] = 1 if subject s is taught by faculty f in room r on day d at time t
        x = {}
        
        for s_idx, subject in enumerate(self.subjects):
            for f_idx, faculty in enumerate(self.faculty):
                for r_idx, room in enumerate(self.classrooms):
                    for d_idx, day in enumerate(self.days):
                        for t_idx, time_slot in enumerate(self.time_slots):
                            x[s_idx, f_idx, r_idx, d_idx, t_idx] = model.NewBoolVar(
                                f'x_s{s_idx}_f{f_idx}_r{r_idx}_d{d_idx}_t{t_idx}'
                            )
        
        # Constraints
        
        # 1. Each subject must be scheduled for required hours per week
        for s_idx, subject in enumerate(self.subjects):
            model.Add(
                sum(x[s_idx, f_idx, r_idx, d_idx, t_idx]
                    for f_idx in range(len(self.faculty))
                    for r_idx in range(len(self.classrooms))
                    for d_idx in range(len(self.days))
                    for t_idx in range(len(self.time_slots))
                ) == subject.get('credits', 3)  # Default 3 hours per week
            )
        
        # 2. No faculty can teach two subjects at the same time
        for f_idx in range(len(self.faculty)):
            for d_idx in range(len(self.days)):
                for t_idx in range(len(self.time_slots)):
                    model.Add(
                        sum(x[s_idx, f_idx, r_idx, d_idx, t_idx]
                            for s_idx in range(len(self.subjects))
                            for r_idx in range(len(self.classrooms))
                        ) <= 1
                    )
        
        # 3. No room can host two subjects at the same time
        for r_idx in range(len(self.classrooms)):
            for d_idx in range(len(self.days)):
                for t_idx in range(len(self.time_slots)):
                    model.Add(
                        sum(x[s_idx, f_idx, r_idx, d_idx, t_idx]
                            for s_idx in range(len(self.subjects))
                            for f_idx in range(len(self.faculty))
                        ) <= 1
                    )
        
        # 4. Subject-Faculty assignment (only qualified faculty can teach subjects)
        for s_idx, subject in enumerate(self.subjects):
            for f_idx, faculty in enumerate(self.faculty):
                if subject.get('department') != faculty.get('department'):
                    for r_idx in range(len(self.classrooms)):
                        for d_idx in range(len(self.days)):
                            for t_idx in range(len(self.time_slots)):
                                model.Add(x[s_idx, f_idx, r_idx, d_idx, t_idx] == 0)
        
        # Solve the model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0  # 30 second timeout
        
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return self._extract_solution(solver, x)
        else:
            return {"error": "Could not find a feasible solution", "status": status}
    
    def _extract_solution(self, solver, x):
        timetable = {}
        
        for d_idx, day in enumerate(self.days):
            timetable[day] = []
            
            for t_idx, time_slot in enumerate(self.time_slots):
                for s_idx, subject in enumerate(self.subjects):
                    for f_idx, faculty in enumerate(self.faculty):
                        for r_idx, room in enumerate(self.classrooms):
                            if solver.Value(x[s_idx, f_idx, r_idx, d_idx, t_idx]) == 1:
                                timetable[day].append({
                                    "time": time_slot,
                                    "subject": subject['name'],
                                    "code": subject['code'],
                                    "faculty": faculty['name'],
                                    "room": room['name'],
                                    "type": "Lecture"  # Can be enhanced based on room type
                                })
        
        return {"timetable": timetable, "status": "success"}

# API Routes
@app.route('/api/generate-timetable', methods=['POST'])
def generate_timetable():
    try:
        data = request.get_json()
        
        faculty_list = data.get('faculty', [])
        subjects_list = data.get('subjects', [])
        classrooms_list = data.get('classrooms', [])
        constraints_list = data.get('constraints', [])
        
        # Validate input
        if not all([faculty_list, subjects_list, classrooms_list]):
            return jsonify({
                "error": "Missing required data: faculty, subjects, or classrooms"
            }), 400
        
        # Generate timetable
        generator = TimetableGenerator(faculty_list, subjects_list, classrooms_list, constraints_list)
        result = generator.generate_timetable()
        
        if "error" in result:
            return jsonify(result), 400
        
        # Save to database
        timetable_entry = Timetable(
            version_name=f"Timetable_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            schedule_data=result['timetable']
        )
        db.session.add(timetable_entry)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "timetable": result['timetable'],
            "timetable_id": timetable_entry.id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/timetables', methods=['GET'])
def get_timetables():
    timetables = Timetable.query.order_by(Timetable.created_at.desc()).all()
    return jsonify([{
        "id": t.id,
        "version_name": t.version_name,
        "created_at": t.created_at.isoformat(),
        "is_active": t.is_active
    } for t in timetables])

@app.route('/api/timetables/<int:timetable_id>', methods=['GET'])
def get_timetable(timetable_id):
    timetable = Timetable.query.get_or_404(timetable_id)
    return jsonify({
        "id": timetable.id,
        "version_name": timetable.version_name,
        "schedule_data": timetable.schedule_data,
        "created_at": timetable.created_at.isoformat()
    })

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

