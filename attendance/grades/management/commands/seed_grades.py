from decimal import Decimal
from django.core.management.base import BaseCommand
from attendance.models import User
from grades.models import Semester, Subject, GradeRecord
from grades.utils import DEFAULT_SEMESTER_DATA


class Command(BaseCommand):
    help = "Populate default semester grades for students in the database."

    def handle(self, *args, **options):
        students = User.objects.filter(role=User.Role.STUDENT)
        if not students.exists():
            self.stdout.write(self.style.WARNING("No students found to seed grades for."))
            return

        total_records = 0
        for sem_num, sem_info in DEFAULT_SEMESTER_DATA.items():
            semester, _ = Semester.objects.get_or_create(
                number=sem_num,
                defaults={'name': f"Semester {sem_num}", 'stamp_text': sem_info['stampText']}
            )

            for sub_info in sem_info['subjects']:
                subject, _ = Subject.objects.get_or_create(
                    code=sub_info['code'],
                    defaults={'name': sub_info['name'], 'credits': sub_info['credits']}
                )

                # Seed for all students, with STU001 having exact marks, others with slight variations
                for idx, student in enumerate(students):
                    # For STU001 or first student, keep exact marks
                    if student.username == 'STU001' or idx == 0:
                        internal = Decimal(str(sub_info['internal']))
                        external = Decimal(str(sub_info['external']))
                        total = Decimal(str(sub_info['total']))
                        grade = sub_info['grade']
                        gp = Decimal(str(sub_info['gradePoint']))
                    else:
                        # slight believable variance (-2 to +2 marks)
                        offset = ((idx * 3 + sem_num) % 5) - 2
                        internal = max(Decimal('10.0'), min(Decimal('20.0'), Decimal(str(sub_info['internal'])) + offset))
                        external = max(Decimal('35.0'), min(Decimal('78.0'), Decimal(str(sub_info['external'])) + offset * 2))
                        total = internal + external
                        grade, gp = GradeRecord.calculate_grade_and_point(total)

                    GradeRecord.objects.update_or_create(
                        student=student,
                        semester=semester,
                        subject=subject,
                        defaults={
                            'internal_marks': internal,
                            'external_marks': external,
                            'total_marks': total,
                            'grade': grade,
                            'grade_point': gp
                        }
                    )
                    total_records += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {total_records} grade records across {students.count()} students."))
