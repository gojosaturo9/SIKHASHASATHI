from src.database.config import supabase
import bcrypt

def hash_pass(pwd):
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


def check_pass(pwd, hashed):
    return bcrypt.checkpw(pwd.encode(), hashed.encode())



def register_teacher(username, name, email, password, confirm_password):
    # 0. NAYA FIX: Pehle check karein ki koi field khali (empty) toh nahi chhut gayi
    if not username or not name or not email or not password or not confirm_password:
        return False, "All fields are required! Please fill everything."

    # 1. Check if passwords match
    if password != confirm_password:
        return False, "Passwords do not match!"
        
    # 2. Check if username already exists
    existing_user = supabase.table("teachers").select("username").eq("username", username).execute()
    if len(existing_user.data) > 0:
        return False, "Username already exists! Try another one."
        
    # 3. Check if email already exists
    existing_email = supabase.table("teachers").select("email_id").eq("email_id", email).execute()
    if len(existing_email.data) > 0:
        return False, "Email already registered! Try logging in."

    # 4. Insert new teacher into database
    try:
        data = {
            "username": username,
            "name": name,
            "email_id": email,
            "password": hash_pass(password), 
            "is_verified": False             
        }
        supabase.table("teachers").insert(data).execute()
        return True, "Registration successful! Please wait for Admin approval."
    except Exception as e:
        # Pata chalega ki exactly kya error aaya hai
        return False, f"Something went wrong: {e}"
    






def get_all_students():
    response = supabase.table('students').select("*").execute()
    return response.data



def create_student(name, email_id, enrollment_no, branch, semester, section, face_embedding=None, voice_embedding=None):
    

    new_student_data = {
        "name": name,
        "email_id": email_id,         
        "enrollment_no": enrollment_no,
        "branch": branch,
        "semester": semester,        
        "section": section,
        "face_embedding": face_embedding,
        "voice_embedding": voice_embedding
    }

    response = supabase.table('students').insert(new_student_data).execute()
    return response.data



def create_subject(subject_code, name, section, teacher_id):
    data = {"subject_code": subject_code, "name": name, "section": section, "teacher_id": teacher_id}
    response = supabase.table("subjects").insert(data).execute()
    return response.data

def get_teacher_subjects(teacher_id):
    response = supabase.table('subjects').select("*, subject_students(count), attendance_logs(timestamp)").eq("teacher_id", teacher_id).execute()
    subjects = response.data


    for sub in subjects:
        sub['total_students'] = sub.get("subject_students", [{}])[0].get('count', 0) if sub.get('subject_students') else 0
        attendance = sub.get('attendance_logs', [])
        unique_sessions = len(set(log['timestamp'] for log in attendance))
        sub['total_classes'] = unique_sessions


        sub.pop('subject_student', None)
        sub.pop('attendance_logs', None)

    return subjects



def  enroll_student_to_subject(student_id, subject_id):
    data = {'student_id': student_id, "subject_id": subject_id}
    response= supabase.table('subject_students').insert(data).execute()
    return response.data


def  unenroll_student_to_subject(student_id, subject_id):
    response= supabase.table('subject_students').delete().eq('student_id', student_id).eq('subject_id', subject_id).execute()
    return response.data



def get_student_subjects(student_id):
    response = supabase.table('subject_students').select('*, subjects(*)').eq('student_id', student_id).execute()
    return response.data


def get_student_attendance(student_id):
    response = supabase.table('attendance_logs').select('*, subjects(*)').eq('student_id', student_id).execute()
    return response.data


def create_attendance(logs):
    response = supabase.table('attendance_logs').insert(logs).execute()
    return response.data

def get_attendance_for_teacher(teacher_id):
    response = (supabase.table('attendance_logs')
                .select("*, subjects!inner(*), students!inner(name, student_id)")
                .eq('subjects.teacher_id', teacher_id)
                .execute())
    return response.data



def get_all_attendance_records():
    # 'smester' ko 'semester' kar diya gaya hai (agar DB mein bhi semester hai toh)
    response = supabase.table('attendance_logs').select(
        "timestamp, is_present, students(name, branch, semester, section), subjects(name)"
    ).execute()
    
    flattened_data = []
    for row in response.data:
        student_info = row.get('students', {}) or {}
        subject_info = row.get('subjects', {}) or {}
        
        raw_date = row.get('timestamp', '')
        formatted_date = raw_date.split('T')[0] if raw_date else '-'

        flattened_data.append({
            "Date": formatted_date,
            "Student Name": student_info.get('name', 'N/A'),
            "Subject": subject_info.get('name', 'N/A'),
            "branch": student_info.get('branch', 'N/A'),
            "semester": student_info.get('semester', 'N/A'), # 👈 Yahan bhi update kiya
            "section": student_info.get('section', 'N/A'),
            "Status": "✅ Present" if row.get('is_present') else "❌ Absent"
        })
        
    return flattened_data