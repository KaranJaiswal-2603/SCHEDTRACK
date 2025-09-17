from flask import Flask, request, jsonify , render_template 
from flask_cors import CORS
from ortools.sat.python import cp_model
from datetime import datetime

app = Flask(__name__)
CORS(app)

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
                ) == subject.get('credits', 3)
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
        
        # 4. Subject-Faculty assignment (only same dept faculty can teach)
        for s_idx, subject in enumerate(self.subjects):
            for f_idx, faculty in enumerate(self.faculty):
                if subject.get('department') != faculty.get('department'):
                    for r_idx in range(len(self.classrooms)):
                        for d_idx in range(len(self.days)):
                            for t_idx in range(len(self.time_slots)):
                                model.Add(x[s_idx, f_idx, r_idx, d_idx, t_idx] == 0)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
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
                                    "type": "Lecture"
                                })
        return {"timetable": timetable, "status": "success"}


@app.route('/')
def home():
    return render_template("index.html")




# API Routes
@app.route('/api/generate-timetable', methods=['POST'])
def generate_timetable():
    try:
        data = request.get_json()
        faculty_list = data.get('faculty', [])
        subjects_list = data.get('subjects', [])
        classrooms_list = data.get('classrooms', [])
        constraints_list = data.get('constraints', [])
        
        if not all([faculty_list, subjects_list, classrooms_list]):
            return jsonify({"error": "Missing required data: faculty, subjects, or classrooms"}), 400
        
        generator = TimetableGenerator(faculty_list, subjects_list, classrooms_list, constraints_list)
        result = generator.generate_timetable()
        
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify({
            "success": True,
            "timetable": result['timetable'],
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
