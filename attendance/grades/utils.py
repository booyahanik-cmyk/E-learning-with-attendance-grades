from decimal import Decimal
from .models import Semester, GradeRecord, Subject

DEFAULT_SEMESTER_DATA = {
    1: {
        "semester": 1,
        "sgpa": "9.11",
        "totalSubjects": 5,
        "status": "PASS",
        "totalCredits": 18,
        "stampText": "SEM 1",
        "subjects": [
            { "code": "CS101", "name": "Programming Fundamentals", "credits": 4, "internal": 18, "external": 62, "total": 80, "grade": "A", "gradePoint": "9.0" },
            { "code": "CS102", "name": "Digital Logic Design", "credits": 4, "internal": 16, "external": 54, "total": 70, "grade": "B+", "gradePoint": "8.0" },
            { "code": "CS103", "name": "Computer Organization", "credits": 4, "internal": 20, "external": 68, "total": 88, "grade": "A+", "gradePoint": "10.0" },
            { "code": "MA101", "name": "Engineering Mathematics", "credits": 4, "internal": 17, "external": 58, "total": 75, "grade": "A", "gradePoint": "9.0" },
            { "code": "HS101", "name": "Communication Skills", "credits": 2, "internal": 19, "external": 66, "total": 85, "grade": "A+", "gradePoint": "10.0" }
        ]
    },
    2: {
        "semester": 2,
        "sgpa": "9.20",
        "totalSubjects": 5,
        "status": "PASS",
        "totalCredits": 20,
        "stampText": "SEM 2",
        "subjects": [
            { "code": "CS201", "name": "Data Structures & Algorithms", "credits": 4, "internal": 19, "external": 65, "total": 84, "grade": "A+", "gradePoint": "10.0" },
            { "code": "CS202", "name": "Object Oriented Programming", "credits": 4, "internal": 18, "external": 60, "total": 78, "grade": "A", "gradePoint": "9.0" },
            { "code": "MA201", "name": "Discrete Mathematics", "credits": 4, "internal": 17, "external": 56, "total": 73, "grade": "B+", "gradePoint": "8.0" },
            { "code": "EC201", "name": "Basic Electronic Circuits", "credits": 4, "internal": 18, "external": 64, "total": 82, "grade": "A", "gradePoint": "9.0" },
            { "code": "EV201", "name": "Environmental Sciences", "credits": 4, "internal": 20, "external": 67, "total": 87, "grade": "A+", "gradePoint": "10.0" }
        ]
    },
    3: {
        "semester": 3,
        "sgpa": "9.05",
        "totalSubjects": 5,
        "status": "PASS",
        "totalCredits": 21,
        "stampText": "SEM 3",
        "subjects": [
            { "code": "CS301", "name": "Database Management Systems", "credits": 4, "internal": 19, "external": 63, "total": 82, "grade": "A", "gradePoint": "9.0" },
            { "code": "CS302", "name": "Operating Systems", "credits": 4, "internal": 18, "external": 61, "total": 79, "grade": "A", "gradePoint": "9.0" },
            { "code": "CS303", "name": "Design & Analysis of Algorithms", "credits": 4, "internal": 17, "external": 59, "total": 76, "grade": "A", "gradePoint": "9.0" },
            { "code": "MA301", "name": "Probability & Statistics", "credits": 4, "internal": 16, "external": 55, "total": 71, "grade": "B+", "gradePoint": "8.0" },
            { "code": "CS304", "name": "Software Engineering", "credits": 5, "internal": 20, "external": 70, "total": 90, "grade": "A+", "gradePoint": "10.0" }
        ]
    },
    4: {
        "semester": 4,
        "sgpa": "9.59",
        "totalSubjects": 5,
        "status": "PASS",
        "totalCredits": 22,
        "stampText": "SEM 4",
        "subjects": [
            { "code": "CS401", "name": "Computer Networks", "credits": 4, "internal": 20, "external": 67, "total": 87, "grade": "A+", "gradePoint": "10.0" },
            { "code": "CS402", "name": "Theory of Computation", "credits": 4, "internal": 18, "external": 62, "total": 80, "grade": "A", "gradePoint": "9.0" },
            { "code": "CS403", "name": "Web Technologies", "credits": 4, "internal": 19, "external": 68, "total": 87, "grade": "A+", "gradePoint": "10.0" },
            { "code": "CS404", "name": "Artificial Intelligence", "credits": 5, "internal": 19, "external": 65, "total": 84, "grade": "A+", "gradePoint": "10.0" },
            { "code": "HS401", "name": "Engineering Economics", "credits": 5, "internal": 17, "external": 58, "total": 75, "grade": "A", "gradePoint": "9.0" }
        ]
    }
}


def get_student_semester_grades(student, semester_num=1):
    """Retrieve or compute academic performance metrics for a student in a semester."""
    # Look for database records
    records = GradeRecord.objects.filter(
        student=student,
        semester__number=semester_num
    ).select_related('subject', 'semester')

    if records.exists():
        total_credits = 0
        total_credit_points = Decimal('0.0')
        has_fail = False
        subjects = []
        raw_scores = []
        highest_sub = None
        highest_score = -1

        for r in records:
            cr = r.subject.credits
            total_credits += cr
            total_credit_points += (r.grade_point * cr)
            if r.grade == 'F':
                has_fail = True
            
            score_val = float(r.total_marks)
            raw_scores.append(score_val)
            if score_val > highest_score:
                highest_score = score_val
                highest_sub = f"{r.subject.name} ({r.subject.code} - {score_val:.0f}/100)"

            subjects.append({
                'code': r.subject.code,
                'name': r.subject.name,
                'credits': cr,
                'internal': float(r.internal_marks),
                'external': float(r.external_marks),
                'total': score_val,
                'grade': r.grade,
                'gradePoint': f"{r.grade_point:.1f}"
            })

        sgpa = (total_credit_points / total_credits) if total_credits > 0 else Decimal('0.00')
        avg_raw = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0

        return {
            "semester": semester_num,
            "sgpa": f"{sgpa:.2f}",
            "totalSubjects": len(subjects),
            "status": "FAIL" if has_fail else "PASS",
            "totalCredits": total_credits,
            "stampText": f"SEM {semester_num}",
            "subjects": subjects,
            "avgScore": f"{avg_raw:.1f}",
            "highestSubject": highest_sub or "N/A"
        }

    # If student has no custom records in DB for this semester, check DEFAULT_SEMESTER_DATA
    if semester_num in DEFAULT_SEMESTER_DATA:
        data = dict(DEFAULT_SEMESTER_DATA[semester_num])
        subjects = data['subjects']
        avg_raw = sum(s['total'] for s in subjects) / len(subjects) if subjects else 0.0
        best = max(subjects, key=lambda s: s['total']) if subjects else None
        data['avgScore'] = f"{avg_raw:.1f}"
        data['highestSubject'] = f"{best['name']} ({best['code']} - {best['total']}/100)" if best else "N/A"
        return data

    return {
        "semester": semester_num,
        "sgpa": "0.00",
        "totalSubjects": 0,
        "status": "N/A",
        "totalCredits": 0,
        "stampText": f"SEM {semester_num}",
        "subjects": [],
        "avgScore": "0.0",
        "highestSubject": "N/A"
    }


def get_all_student_semesters(student):
    """Return dictionary of all available semesters with data for client-side instant switching."""
    result = {}
    for sem in [1, 2, 3, 4]:
        result[sem] = get_student_semester_grades(student, sem)
    return result
