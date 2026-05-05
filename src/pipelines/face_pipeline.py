# import dlib
# import numpy as np
# import face_recognition_models
# from sklearn.svm import SVC
# import streamlit as st

# from src.database.db import get_students_for_subject, get_all_students

# from src.pipelines.anti_spoofing import check_liveness


# @st.cache_resource
# def load_dlib_models():
#     detector = dlib.get_frontal_face_detector()

#     sp = dlib.shape_predictor(face_recognition_models.pose_predictor_model_location())

#     facerec = dlib.face_recognition_model_v1(
#         face_recognition_models.face_recognition_model_location()
#     )

#     return detector, sp, facerec


# def get_face_embeddings(image_np):
#     detector, sp, facerec = load_dlib_models()
#     faces = detector(image_np, 1)

#     encodings = []

#     for face in faces:
#         shape = sp(image_np, face)
#         face_descriptor = facerec.compute_face_descriptor(
#             image_np, shape, 1
#         )  # 128 embedding

#         encodings.append(np.array(face_descriptor))
#     return encodings


# @st.cache_resource
# def get_trained_model(subject_id=None):
#     X = []
#     y = []

#     # Agar subject_id nahi hai (Student Login), toh saare bacche lao
#     if subject_id is None:
#         student_db = get_all_students()
#     # Agar subject_id hai (Teacher Attendance), toh sirf us class ke bacche lao
#     else:
#         student_db = get_students_for_subject(subject_id)

#     if not student_db:
#         return None

#     for student in student_db:
#         embedding = student.get("face_embedding")
#         if embedding:
#             X.append(np.array(embedding))
#             y.append(student.get("student_id"))

#     if len(X) == 0:
#         return 0

#     clf = SVC(kernel="linear", probability=True, class_weight="balanced", C=10)

#     try:
#         clf.fit(X, y)
#     except ValueError:
#         pass

#     return {"clf": clf, "X": X, "y": y, "students_data": student_db}


# def train_classifier():
#     st.cache_resource.clear()
#     return True


# # 🚀 NAYA FIX: Ab predict karte waqt subject_id pass karni hogi
# def predict_attendance(class_image_np, subject_id=None):
#     encodings = get_face_embeddings(class_image_np)

#     detected_student = {}

#     model_data = get_trained_model(subject_id)

#     if not model_data:
#         return detected_student, [], len(encodings)

#     clf = model_data["clf"]
#     X_train = model_data["X"]
#     y_train = model_data["y"]

#     all_students = sorted(list(set(y_train)))

#     for encoding in encodings:
#         if len(all_students) >= 2:
#             predicted_id = int(clf.predict([encoding])[0])
#         else:
#             predicted_id = int(all_students[0])

#         student_embedding = X_train[y_train.index(predicted_id)]

#         best_match_score = np.linalg.norm(student_embedding - encoding)

#         #0.45 se 0.40 kar diya taaki accuracy 100% rahe badi classes mein
#         resemblance_threshold = 0.45

#         if best_match_score <= resemblance_threshold:
#             detected_student[predicted_id] = True

#     return detected_student, all_students, len(encodings)


# with spoofing


import dlib
import numpy as np
import face_recognition_models
from sklearn.svm import SVC
import streamlit as st
import cv2

from src.database.db import get_students_for_subject, get_all_students
from src.pipelines.anti_spoofing import check_liveness


@st.cache_resource
def load_dlib_models():
    detector = dlib.get_frontal_face_detector()
    sp = dlib.shape_predictor(face_recognition_models.pose_predictor_model_location())
    facerec = dlib.face_recognition_model_v1(
        face_recognition_models.face_recognition_model_location()
    )
    return detector, sp, facerec


def get_face_embeddings(image_np):
    detector, sp, facerec = load_dlib_models()
    faces = detector(image_np, 1)

    encodings = []

    for face in faces:
        # Purana wala — seedha embedding nikalo
        shape = sp(image_np, face)
        face_descriptor = facerec.compute_face_descriptor(image_np, shape, 2)
        encoding = np.array(face_descriptor)

        # Anti spoofing — face crop nikalo aur check karo
        x1 = max(0, face.left())
        y1 = max(0, face.top())
        x2 = min(image_np.shape[1], face.right())
        y2 = min(image_np.shape[0], face.bottom())

        if (x2 - x1) <= 0 or (y2 - y1) <= 0:
            continue

        face_crop_rgb = image_np[y1:y2, x1:x2]
        face_crop_bgr = cv2.cvtColor(face_crop_rgb, cv2.COLOR_RGB2BGR)

        is_real = check_liveness(face_crop_bgr)

        if not is_real:
            print("[Pipeline] ❌ Spoof detected — skip")
            continue

        print("[Pipeline] ✅ Real face — embedding add kiya")
        encodings.append(encoding)

    return encodings


def get_trained_model(subject_id=None):
    X = []
    y = []

    if subject_id is None:
        student_db = get_all_students()
    else:
        student_db = get_students_for_subject(subject_id)

    if not student_db:
        return None

    for student in student_db:
        embedding = student.get("face_embedding")
        if embedding:
            X.append(np.array(embedding))
            y.append(student.get("student_id"))

    if len(X) == 0:
        return 0

    clf = SVC(kernel="linear", probability=True, class_weight="balanced", C=100)

    try:
        clf.fit(X, y)
    except ValueError:
        pass

    return {"clf": clf, "X": X, "y": y, "students_data": student_db}


def train_classifier():
    st.cache_resource.clear()
    return True


def predict_attendance(class_image_np, subject_id=None):
    encodings = get_face_embeddings(class_image_np)

    detected_student = {}

    model_data = get_trained_model(subject_id)

    if not model_data:
        return detected_student, [], len(encodings)

    clf = model_data["clf"]
    X_train = model_data["X"]
    y_train = model_data["y"]

    all_students = sorted(list(set(y_train)))

    for encoding in encodings:
        if len(all_students) >= 2:
            
            predicted_id = int(clf.predict([encoding])[0])
        else:
            predicted_id = int(all_students[0])

        student_embeddings = X_train[y_train.index(predicted_id)]
        
        best_match_score = np.linalg.norm(student_embeddings - encoding)

        resemblance_threshold = 0.40

        if best_match_score <= resemblance_threshold:
            detected_student[predicted_id] = True
            print(
                f"[Pipeline] ✅ Student {predicted_id} detected (score: {best_match_score:.3f})"
            )
        else:
            print(f"[Pipeline] ❌ No match (score: {best_match_score:.3f})")

    return detected_student, all_students, len(encodings)
