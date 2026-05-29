import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
CORS(app)

# Database Configuration - Update these with your MySQL details
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345',
    'database': 'grade_tracker'
}

def get_db_connection():
    """Establishes and returns a connection to the MySQL database."""
    return mysql.connector.connect(**db_config)

# ==========================================
# CORE UTILITY & LOGIC FUNCTIONS
# ==========================================

def calculate_grade_and_remarks(score, max_score=100):
    """
    Core Logic Function: Calculates percentage, grade, and remarks based on rules.
    """
    percentage = (float(score) / float(max_score)) * 100

    if percentage >= 90:
        return "A", "Outstanding", percentage
    elif percentage >= 75:
        return "B", "Well done", percentage
    elif percentage >= 60:
        return "C", "Keep improving", percentage
    elif percentage >= 45:
        return "D", "Needs attention", percentage
    else:
        return "F", "Please seek help", percentage

# ==========================================
# STUDENT ENDPOINTS
# ==========================================

@app.route('/students', methods=['GET'])
def get_students():
    """List all students or search them by name using query parameter."""
    name_search = request.args.get('name')
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        if name_search:
            query = "SELECT * FROM students WHERE name LIKE %s"
            cursor.execute(query, (f"%{name_search}%",))
        else:
            query = "SELECT * FROM students"
            cursor.execute(query)
            
        students = cursor.fetchall()
        return jsonify(students), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@app.route('/students/<int:student_id>', methods=['GET'])
def get_student_by_id(student_id):
    """Get a single student by ID."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404
            
        return jsonify(student), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@app.route('/students', methods=['POST'])
def add_student():
    """Add a new student."""
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email')
    
    if not name or not email:
        return jsonify({"error": "Missing required fields: 'name' and 'email'"}), 400
        
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT id FROM students WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": f"Student with email '{email}' already exists"}), 409
            
        query = "INSERT INTO students (name, email) VALUES (%s, %s)"
        cursor.execute(query, (name, email))
        connection.commit()
        
        new_id = cursor.lastrowid
        return jsonify({"message": "Student created successfully", "student_id": new_id}), 201
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@app.route('/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    """Update student name or email."""
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email')
    
    if not name and not email:
        return jsonify({"error": "Provide at least one field to update: 'name' or 'email'"}), 400
        
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify student exists
        cursor.execute("SELECT id FROM students WHERE id = %s", (student_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404
            
        if email:
            # Verify email uniqueness for other users
            cursor.execute("SELECT id FROM students WHERE email = %s AND id != %s", (email, student_id))
            if cursor.fetchone():
                return jsonify({"error": f"Email '{email}' is already in use by another student"}), 409
        
        # Dynamically build update query
        fields = []
        values = []
        if name:
            fields.append("name = %s")
            values.append(name)
        if email:
            fields.append("email = %s")
            values.append(email)
            
        values.append(student_id)
        query = f"UPDATE students SET {', '.join(fields)} WHERE id = %s"
        
        cursor.execute(query, tuple(values))
        connection.commit()
        
        return jsonify({"message": f"Student {student_id} updated successfully"}), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@app.route('/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    """Delete a student and all their marks via CASCADE."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT id FROM students WHERE id = %s", (student_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404
            
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
        connection.commit()
        
        return jsonify({"message": f"Student {student_id} and all related marks deleted successfully"}), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ==========================================
# MARKS ENDPOINTS
# ==========================================

@app.route('/students/<int:student_id>/marks', methods=['GET'])
def get_student_marks(student_id):
    """Get all marks for a student, with filter option by subject."""
    subject_filter = request.args.get('subject')
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Verify student exists
        cursor.execute("SELECT id FROM students WHERE id = %s", (student_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404
            
        if subject_filter:
            query = "SELECT * FROM marks WHERE student_id = %s AND subject = %s"
            cursor.execute(query, (student_id, subject_filter))
        else:
            query = "SELECT * FROM marks WHERE student_id = %s"
            cursor.execute(query, (student_id,))
            
        marks = cursor.fetchall()
        
        # Inject dynamic python logic details
        for row in marks:
            grade, remark, percentage = calculate_grade_and_remarks(row['score'], row['max_score'])
            row['percentage'] = round(percentage, 2)
            row['grade'] = grade
            row['remark'] = remark
            row['score'] = float(row['score'])
            row['max_score'] = float(row['max_score'])
            
        return jsonify(marks), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@app.route('/students/<int:student_id>/marks', methods=['POST'])
def add_student_mark(student_id):
    """Add a mark entry for a student."""
    data = request.get_json() or {}
    subject = data.get('subject')
    score = data.get('score')
    max_score = data.get('max_score', 100) # Defaults to 100 if omitted
    
    if not subject or score is None:
        return jsonify({"error": "Missing required fields: 'subject' and 'score'"}), 400
        
    try:
        score_val = float(score)
        max_score_val = float(max_score)
    except ValueError:
        return jsonify({"error": "Score and Max Score must be valid numerical values"}), 400
        
    # Input Constraints Validations
    if score_val < 0:
        return jsonify({"error": "Invalid Input: Score cannot be negative."}), 400
    if score_val > max_score_val:
        return jsonify({"error": f"Invalid Input: Score ({score_val}) cannot exceed maximum allowed score ({max_score_val})."}), 400
        
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify student exists
        cursor.execute("SELECT id FROM students WHERE id = %s", (student_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404
            
        query = "INSERT INTO marks (student_id, subject, score, max_score) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (student_id, subject, score_val, max_score_val))
        connection.commit()
        
        return jsonify({"message": "Mark entry added successfully", "mark_id": cursor.lastrowid}), 201
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@app.route('/marks/<int:mark_id>', methods=['DELETE'])
def delete_mark(mark_id):
    """Delete a specific mark record row."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT id FROM marks WHERE id = %s", (mark_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Mark record with ID {mark_id} not found"}), 404
            
        cursor.execute("DELETE FROM marks WHERE id = %s", (mark_id,))
        connection.commit()
        
        return jsonify({"message": f"Mark entry {mark_id} deleted successfully"}), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ==========================================
# REPORT & SUMMARY ENDPOINTS
# ==========================================

@app.route('/students/<int:student_id>/report', methods=['GET'])
def get_student_report(student_id):
    """Generates complete calculated performance report metrics for one student."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Fetch Student Metadata
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        if not student:
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404
            
        # Fetch Student Performance records
        cursor.execute("SELECT subject, score, max_score FROM marks WHERE student_id = %s", (student_id,))
        marks_data = cursor.fetchall()
        
        if not marks_data:
            return jsonify({
                "student": student,
                "message": "No marks records found to calculate performance metrics.",
                "subjects": [],
                "average_percentage": 0.0,
                "overall_grade": "N/A",
                "status": "N/A"
            }), 200

        subjects_list = []
        total_percentage = 0.0
        best_subject = None
        weakest_subject = None
        highest_pct = -1.0
        lowest_pct = 101.0
        
        for item in marks_data:
            grade, remark, percentage = calculate_grade_and_remarks(item['score'], item['max_score'])
            total_percentage += percentage
            
            subject_detail = {
                "subject": item['subject'],
                "score": float(item['score']),
                "max_score": float(item['max_score']),
                "percentage": round(percentage, 2),
                "grade": grade,
                "remark": remark
            }
            subjects_list.append(subject_detail)
            
            # Identify Best/Weakest subject tracks
            if percentage > highest_pct:
                highest_pct = percentage
                best_subject = {"subject": item['subject'], "percentage": round(percentage, 2)}
            if percentage < lowest_pct:
                lowest_pct = percentage
                weakest_subject = {"subject": item['subject'], "percentage": round(percentage, 2)}
                
        avg_percentage = total_percentage / len(marks_data)
        overall_grade, _, _ = calculate_grade_and_remarks(avg_percentage, 100)
        status = "Pass" if overall_grade != "F" else "Fail"
        
        report = {
            "student": student,
            "subjects": subjects_list,
            "average_percentage": round(avg_percentage, 2),
            "overall_grade": overall_grade,
            "status": status,
            "best_subject": best_subject,
            "weakest_subject": weakest_subject
        }
        return jsonify(report), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@app.route('/summary', methods=['GET'])
def get_class_summary():
    """Generates global class aggregation metrics alongside rank lists."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 1. Total Student Base
        cursor.execute("SELECT COUNT(*) as total FROM students")
        total_students = cursor.fetchone()['total']
        
        # 2. Get performance lists for all records to process via Python logic
        query = """
            SELECT s.id, s.name, m.score, m.max_score 
            FROM students s 
            JOIN marks m ON s.id = m.student_id
        """
        cursor.execute(query)
        all_marks = cursor.fetchall()
        
        if not all_marks:
            return jsonify({
                "total_students": total_students,
                "class_average_percentage": 0,
                "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
                "pass_count": 0,
                "fail_count": 0,
                "highest_scoring_student": None,
                "lowest_scoring_student": None,
                "leaderboard_rankings": []
            }), 200

        # Group data records natively by student
        student_data = {}
        for entry in all_marks:
            sid = entry['id']
            if sid not in student_data:
                student_data[sid] = {'name': entry['name'], 'total_pct': 0.0, 'count': 0}
            
            _, _, pct = calculate_grade_and_remarks(entry['score'], entry['max_score'])
            student_data[sid]['total_pct'] += pct
            student_data[sid]['count'] += 1

        # Evaluate performance properties per student item
        processed_students = []
        global_pct_sum = 0.0
        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        pass_count = 0
        fail_count = 0
        
        for sid, details in student_data.items():
            final_avg = details['total_pct'] / details['count']
            global_pct_sum += final_avg
            grade, _, _ = calculate_grade_and_remarks(final_avg, 100)
            
            grade_dist[grade] += 1
            if grade == "F":
                fail_count += 1
            else:
                pass_count += 1
                
            processed_students.append({
                "student_id": sid,
                "name": details['name'],
                "average_percentage": round(final_avg, 2),
                "grade": grade
            })
            
        # Rank students from highest score to lowest
        processed_students.sort(key=lambda x: x['average_percentage'], reverse=True)
        
        # Assign formal leaderboard placement numbers
        for rank, student in enumerate(processed_students, start=1):
            student['rank'] = rank
            
        class_avg = global_pct_sum / len(student_data)
        
        summary = {
            "total_students": total_students,
            "class_average_percentage": round(class_avg, 2),
            "grade_distribution": grade_dist,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "highest_scoring_student": {
                "name": processed_students[0]['name'],
                "average_percentage": processed_students[0]['average_percentage']
            },
            "lowest_scoring_student": {
                "name": processed_students[-1]['name'],
                "average_percentage": processed_students[-1]['average_percentage']
            },
            "leaderboard_rankings": processed_students
        }
        return jsonify(summary), 200
    except Error as e:
        return jsonify({"error": "Database error occurred", "details": str(e)}), 400
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)