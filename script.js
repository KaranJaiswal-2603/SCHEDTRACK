// Dynamically add input sections
function addFaculty() {
    let section = document.getElementById("faculty-section");
    section.innerHTML += `
        <div class="faculty">
            <input type="text" placeholder="Faculty Name" required>
            <input type="email" placeholder="Faculty Email" required>
            <input type="text" placeholder="Department" required>
        </div>
    `;
}

function addSubject() {
    let section = document.getElementById("subject-section");
    section.innerHTML += `
        <div class="subject">
            <input type="text" placeholder="Subject Name" required>
            <input type="text" placeholder="Code" required>
            <input type="number" placeholder="Credits" value="3" required>
            <input type="text" placeholder="Department" required>
            <input type="number" placeholder="Hours/Week" value="3" required>
        </div>
    `;
}

function addClassroom() {
    let section = document.getElementById("classroom-section");
    section.innerHTML += `
        <div class="classroom">
            <input type="text" placeholder="Room Name" required>
            <input type="number" placeholder="Capacity" required>
            <input type="text" placeholder="Room Type" required>
            <input type="text" placeholder="Building" required>
        </div>
    `;
}

// Handle form submission
document.getElementById("timetableForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    // Collect Faculty Data
    let faculty = [];
    document.querySelectorAll(".faculty").forEach(f => {
        let inputs = f.querySelectorAll("input");
        faculty.push({
            name: inputs[0].value,
            email: inputs[1].value,
            department: inputs[2].value
        });
    });

    // Collect Subject Data
    let subjects = [];
    document.querySelectorAll(".subject").forEach(s => {
        let inputs = s.querySelectorAll("input");
        subjects.push({
            name: inputs[0].value,
            code: inputs[1].value,
            credits: parseInt(inputs[2].value),
            department: inputs[3].value,
            hours_per_week: parseInt(inputs[4].value)
        });
    });

    // Collect Classroom Data
    let classrooms = [];
    document.querySelectorAll(".classroom").forEach(c => {
        let inputs = c.querySelectorAll("input");
        classrooms.push({
            name: inputs[0].value,
            capacity: parseInt(inputs[1].value),
            room_type: inputs[2].value,
            building: inputs[3].value
        });
    });

    // Send Data to Flask API
    try {
        let response = await fetch("/api/generate-timetable", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ faculty, subjects, classrooms, constraints: [] })
        });

        let data = await response.json();
        if (data.success) {
            document.getElementById("timetableOutput").textContent = JSON.stringify(data.timetable, null, 2);
        } else {
            document.getElementById("timetableOutput").textContent = "Error: " + data.error;
        }
    } catch (error) {
        document.getElementById("timetableOutput").textContent = "Request failed: " + error;
    }
});
