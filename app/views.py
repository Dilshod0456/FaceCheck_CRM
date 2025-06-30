from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic.base import TemplateView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Avg, Sum, Q, F
from django.db.models.functions import ExtractMonth, ExtractWeek
from .models import *
import face_recognition
import cv2
import numpy as np
from datetime import datetime, timedelta
import json
import pandas as pd
from django.utils import timezone

# Create your views here.
class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = 'details/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Home'
        messages.success(self.request, "Siz muvaffaqiyatli tizimga kirdingiz.")
        # messages.info(self.request, "Sizning hisobingizga xush kelibsiz.")
        # messages.warning(self.request, "Eslatma: Parolingizni o'zgartirishni unutmang.")
        # messages.error(self.request, "Agar muammo yuzaga kelsa, administrator bilan bog'laning.")
        
        return context
    
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            # Emailga mos username ni topish
            user = CustomUser.objects.get(email=email)
            # Username va parol bilan autentifikatsiya
            authenticated_user = authenticate(request, username=user.username, password=password)
            if authenticated_user is not None:
                login(request, authenticated_user)
                return redirect('app:home')
            else:
                messages.error(request, "Noto'g'ri email yoki parol")
        except CustomUser.DoesNotExist:
            messages.error(request, "Bu email bilan ro'yxatdan o'tilmagan")
            
    return render(request, 'auth/login.html')

def logout_view(request):
    logout(request)
    return redirect('app:login')

@login_required
def home(request):
    user = request.user
    context = {'title': 'Bosh sahifa'}
    
    if user.user_type == 'super_admin':
        # Super admin uchun statistika
        context.update({
            'total_students': Student.objects.count(),
            'total_groups': Group.objects.count(),
            'total_departments': Department.objects.count(),
            'recent_attendance': Attendance.objects.select_related('student', 'group').order_by('-date', '-time')[:10]
        })
    elif user.user_type == 'management':
        # Rahbariyat uchun statistika
        context.update({
            'departments': Department.objects.annotate(student_count=Count('groups__students')),
            'attendance_stats': get_attendance_stats()
        })
    elif user.user_type == 'teacher':
        # O'qituvchi uchun statistika
        teacher_groups = Group.objects.filter(teacher=user)
        context.update({
            'groups': teacher_groups,
            'today_attendance': get_today_attendance(teacher_groups)
        })
    elif user.user_type == 'student':
        # O'quvchi uchun statistika
        student = Student.objects.get(user=user)
        context.update({
            'student': student,
            'attendance_history': get_student_attendance(student)
        })
    elif user.user_type == 'parent':
        # Ota-ona uchun statistika
        children = Student.objects.filter(parents=user)
        context.update({
            'children': children,
            'children_attendance': get_children_attendance(children)
        })
    
    return render(request, 'details/home.html', context)

@login_required
def dashboard(request):
    user = request.user
    today = datetime.now().date()
    
    if user.user_type in ['super_admin', 'management']:
        # Bugungi umumiy statistika
        total_students = Student.objects.count()
        present_today = Attendance.objects.filter(
            date=today, 
            status='present'
        ).count()
        
        attendance_percentage = (present_today / total_students * 100) if total_students > 0 else 0
        
        context = {
            'total_students': total_students,
            'present_today': present_today,
            'absent_today': total_students - present_today,
            'attendance_percentage': round(attendance_percentage, 1),
            'recent_attendance': Attendance.objects.select_related(
                'student', 'group'
            ).order_by('-date', '-time')[:10]
        }
        
        # Guruhlar bo'yicha statistika
        groups_stats = Group.objects.annotate(
            total_students=Count('students', distinct=True),
            present_students=Count(
                'attendances',
                filter=Q(attendances__date=today) & Q(attendances__status='present'),
                distinct=True
            )
        ).order_by('present_students')[:5]
        
        context['low_attendance_groups'] = groups_stats
        
        return render(request, 'details/dashboard.html', context)
    
    return redirect('app:home')

def get_attendance_stats():
    today = datetime.now().date()
    stats = {}
    
    # Bugungi statistika
    stats['today'] = {
        'total': Student.objects.count(),
        'present': Attendance.objects.filter(date=today, status='present').count(),
        'absent': Attendance.objects.filter(date=today, status='absent').count(),
        'late': Attendance.objects.filter(date=today, status='late').count()
    }
    
    # Haftalik statistika
    week_start = today - timedelta(days=today.weekday())
    stats['weekly'] = get_period_stats(week_start, today)
    
    # Oylik statistika
    month_start = today.replace(day=1)
    stats['monthly'] = get_period_stats(month_start, today)
    
    return stats

def get_period_stats(start_date, end_date):
    return {
        'total': Attendance.objects.filter(date__range=[start_date, end_date]).count(),
        'present': Attendance.objects.filter(
            date__range=[start_date, end_date], 
            status='present'
        ).count(),
        'absent': Attendance.objects.filter(
            date__range=[start_date, end_date], 
            status='absent'
        ).count(),
        'late': Attendance.objects.filter(
            date__range=[start_date, end_date], 
            status='late'
        ).count()
    }

def get_today_attendance(groups):
    today = datetime.now().date()
    attendance_data = {}
    
    for group in groups:
        total_students = group.students.count()
        present_students = Attendance.objects.filter(
            group=group,
            date=today,
            status='present'
        ).count()
        
        attendance_data[group.id] = {
            'group_name': group.name,
            'total_students': total_students,
            'present_students': present_students,
            'attendance_percentage': round((present_students / total_students * 100), 1) if total_students > 0 else 0
        }
    
    return attendance_data

def get_student_attendance(student):
    today = datetime.now().date()
    month_start = today.replace(day=1)
    
    # Oylik statistika
    monthly_data = Attendance.objects.filter(
        student=student,
        date__range=[month_start, today]
    ).values('status').annotate(count=Count('id'))
    
    # Kunlik statistika
    daily_data = Attendance.objects.filter(
        student=student,
        date=today
    ).first()
    
    # O'rtacha davomati
    total_classes = Attendance.objects.filter(student=student).count()
    present_classes = Attendance.objects.filter(
        student=student, 
        status='present'
    ).count()
    
    attendance_rate = (present_classes / total_classes * 100) if total_classes > 0 else 0
    
    return {
        'monthly': monthly_data,
        'today': daily_data,
        'total_rate': round(attendance_rate, 1)
    }

def get_children_attendance(children):
    today = datetime.now().date()
    children_data = {}
    
    for child in children:
        # Bugungi davomat
        today_attendance = Attendance.objects.filter(
            student=child,
            date=today
        ).first()
        
        # Ohirgi 30 kun statistikasi
        month_ago = today - timedelta(days=30)
        monthly_stats = Attendance.objects.filter(
            student=child,
            date__range=[month_ago, today]
        ).values('status').annotate(count=Count('id'))
        
        # Ketma-ket dars qoldirish holatlari
        consecutive_absences = get_consecutive_absences(child)
        
        children_data[child.id] = {
            'name': child.user.get_full_name(),
            'today': today_attendance,
            'monthly_stats': monthly_stats,
            'consecutive_absences': consecutive_absences
        }
    
    return children_data

def get_consecutive_absences(student):
    absences = Attendance.objects.filter(
        student=student,
        status='absent'
    ).order_by('-date')
    
    consecutive_days = 0
    current_date = None
    
    for absence in absences:
        if current_date is None:
            current_date = absence.date
            consecutive_days = 1
        elif (current_date - absence.date).days == 1:
            consecutive_days += 1
            current_date = absence.date
        else:
            break
    
    return consecutive_days

def get_student_ranking(student, group):
    students = Student.objects.filter(groups=group)
    rankings = []
    
    for s in students:
        total_classes = Attendance.objects.filter(student=s, group=group).count()
        present_classes = Attendance.objects.filter(
            student=s, 
            group=group, 
            status='present'
        ).count()
        
        attendance_rate = (present_classes / total_classes * 100) if total_classes > 0 else 0
        rankings.append({
            'student_id': s.id,
            'rate': attendance_rate
        })
    
    # Tartibga solish
    rankings.sort(key=lambda x: x['rate'], reverse=True)
    
    # O'quvchi o'rnini aniqlash
    student_rank = next(
        (i + 1 for i, x in enumerate(rankings) if x['student_id'] == student.id),
        0
    )
    
    return {
        'rank': student_rank,
        'total_students': len(rankings)
    }

def export_attendance(request, format='excel'):
    if format == 'excel':
        # Excel export
        df = pd.DataFrame(list(Attendance.objects.values(
            'date', 'time', 'status', 'student__user__first_name',
            'student__user__last_name', 'group__name'
        )))
        
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="attendance_report.xlsx"'
        
        df.to_excel(response, index=False)
        return response
    
    elif format == 'pdf':
        # PDF export логикаси
        pass
    
    return HttpResponse('Format not supported')

# Department views
@login_required
def department_list(request):
    departments = Department.objects.all()
    return render(request, 'departments/list.html', {'departments': departments})

@login_required
def department_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        Department.objects.create(name=name, description=description)
        messages.success(request, "Bo'lim muvaffaqiyatli qo'shildi")
        return redirect('app:department_list')
    return render(request, 'departments/add.html')

@login_required
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        department.name = name
        department.description = description
        department.save()
        messages.success(request, "Bo'lim muvaffaqiyatli yangilandi")
        return redirect('app:department_list')
    return render(request, 'departments/edit.html', {'department': department})

@login_required
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        department.delete()
        messages.success(request, "Bo'lim muvaffaqiyatli o'chirildi")
        return redirect('app:department_list')
    return render(request, 'departments/delete.html', {'department': department})

@login_required
def group_list(request):
    groups = Group.objects.all()
    return render(request, 'groups/list.html', {'groups': groups})

@login_required
def group_add(request):
    if request.method == 'POST':
        group = Group.objects.create(
            name=request.POST.get('name'),
            department_id=request.POST.get('department'),
            teacher_id=request.POST.get('teacher'),
            start_date=request.POST.get('start_date'),
            end_date=request.POST.get('end_date'),
            active=request.POST.get('active') == 'on'
        )
        
        messages.success(request, "Yangi guruh muvaffaqiyatli qo'shildi")
        return redirect('app:group_list')
    
    departments = Department.objects.all()
    teachers = CustomUser.objects.filter(user_type='teacher')
    
    return render(request, 'groups/edit.html', {
        'departments': departments,
        'teachers': teachers
    })

@login_required
def group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk)
    students = Student.objects.filter(groups=group)
    attendance = Attendance.objects.filter(group=group).order_by('-date', '-time')[:10]
    
    return render(request, 'groups/detail.html', {
        'group': group,
        'students': students,
        'attendance': attendance
    })

@login_required
def group_edit(request, pk):
    group = get_object_or_404(Group, pk=pk)
    
    if request.method == 'POST':
        group.name = request.POST.get('name')
        group.department_id = request.POST.get('department')
        group.teacher_id = request.POST.get('teacher')
        group.start_date = request.POST.get('start_date')
        group.end_date = request.POST.get('end_date')
        group.active = request.POST.get('active') == 'on'
        group.save()
        
        messages.success(request, "Guruh ma'lumotlari muvaffaqiyatli yangilandi")
        return redirect('app:group_list')
    
    departments = Department.objects.all()
    teachers = CustomUser.objects.filter(user_type='teacher')
    
    return render(request, 'groups/edit.html', {
        'group': group,
        'departments': departments,
        'teachers': teachers
    })

@login_required
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        group.delete()
        messages.success(request, "Guruh muvaffaqiyatli o'chirildi")
        return redirect('app:group_list')
    return render(request, 'groups/delete.html', {'group': group})

# Face recognition functions
def process_attendance_image(image_path, group_id):
    # Rasmni o'qish
    image = face_recognition.load_image_file(image_path)
    
    # Yuzlarni aniqlash
    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)
    
    # Guruh o'quvchilarining yuz kodlarini olish
    group = Group.objects.get(id=group_id)
    students = Student.objects.filter(groups=group)
    known_face_encodings = []
    known_students = []
    
    for student in students:
        if student.user.face_encoding:
            known_face_encodings.append(np.frombuffer(student.user.face_encoding))
            known_students.append(student)
    
    # Har bir yuzni tekshirish
    attendance_results = []
    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        if True in matches:
            student = known_students[matches.index(True)]
            attendance_results.append({
                'student': student,
                'confidence': face_recognition.face_distance([known_face_encodings[matches.index(True)]], face_encoding)[0]
            })
    
    return attendance_results

@login_required
def attendance_capture(request):
    if request.method == 'POST' and request.FILES.get('image'):
        group_id = request.POST.get('group_id')
        image = request.FILES['image']
        
        # Rasmni saqlash
        attendance_image = AttendanceImage.objects.create(image=image)
        
        # Rasmni qayta ishlash
        results = process_attendance_image(attendance_image.image.path, group_id)
        
        # Davomatni saqlash
        now = datetime.now()
        for result in results:
            Attendance.objects.create(
                student=result['student'],
                group_id=group_id,
                date=now.date(),
                time=now.time(),
                status='present',
                face_confidence=result['confidence'],
                marked_by=request.user
            )        
        return JsonResponse({'success': True, 'detected_count': len(results)})
    
    return render(request, 'attendance/capture.html', {
        'groups': Group.objects.filter(active=True),
        'departments': Department.objects.all()
    })

@login_required
def student_list(request):
    students = Student.objects.select_related('user').all()
    return render(request, 'students/list.html', {'students': students})

@login_required
def student_add(request):
    if request.method == 'POST':
        # User ma'lumotlarini olish
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        
        # CustomUser yaratish
        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            user_type='student'
        )
        
        # Student yaratish
        student = Student.objects.create(
            user=user,
            student_id=request.POST.get('student_id')
        )
        
        # Guruhlarni qo'shish
        group_ids = request.POST.getlist('groups')
        student.groups.set(group_ids)
        
        # Ota-onalarni qo'shish
        parent_ids = request.POST.getlist('parents')
        if parent_ids:
            student.parents.set(parent_ids)
        
        messages.success(request, "O'quvchi muvaffaqiyatli qo'shildi")
        return redirect('app:student_list')
    
    groups = Group.objects.all()
    parents = CustomUser.objects.filter(user_type='parent')
    return render(request, 'students/add.html', {
        'groups': groups,
        'parents': parents
    })

@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)
    attendance = Attendance.objects.filter(student=student).order_by('-date', '-time')[:10]
    
    # O'quvchining guruhlaridagi reytingi
    rankings = {}
    for group in student.groups.all():
        rankings[group.name] = get_student_ranking(student, group)
    
    return render(request, 'students/detail.html', {
        'student': student,
        'attendance': attendance,
        'rankings': rankings
    })

@login_required
def student_edit(request, pk):
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)
    if request.method == 'POST':
        # User ma'lumotlarini yangilash
        user = student.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.phone_number = request.POST.get('phone_number')
        
        if request.POST.get('password'):
            user.set_password(request.POST.get('password'))
        
        user.save()
        
        # Student ma'lumotlarini yangilash
        student.student_id = request.POST.get('student_id')
        student.save()
        
        # Guruhlarni yangilash
        group_ids = request.POST.getlist('groups')
        student.groups.set(group_ids)
        
        # Ota-onalarni yangilash
        parent_ids = request.POST.getlist('parents')
        if parent_ids:
            student.parents.set(parent_ids)
        
        messages.success(request, "O'quvchi ma'lumotlari muvaffaqiyatli yangilandi")
        return redirect('app:student_list')
    
    groups = Group.objects.all()
    parents = CustomUser.objects.filter(user_type='parent')
    return render(request, 'students/edit.html', {
        'student': student,
        'groups': groups,
        'parents': parents
    })

@login_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        user = student.user
        student.delete()
        user.delete()
        messages.success(request, "O'quvchi muvaffaqiyatli o'chirildi")
        return redirect('app:student_list')
    return render(request, 'students/delete.html', {'student': student})

@login_required
def attendance_list(request):
    # Get query parameters for filtering
    group_id = request.GET.get('group')
    date = request.GET.get('date')
    status = request.GET.get('status')
    
    # Base queryset
    attendances = Attendance.objects.select_related('student__user', 'group').all()
    
    # Apply filters
    if group_id:
        attendances = attendances.filter(group_id=group_id)
    if date:
        attendances = attendances.filter(date=date)
    if status:
        attendances = attendances.filter(status=status)
        
    # Order by most recent
    attendances = attendances.order_by('-date', '-time')
    
    # Get active groups for filter dropdown
    groups = Group.objects.filter(active=True)
    
    return render(request, 'attendance/list.html', {
        'attendances': attendances,
        'groups': groups,
        'selected_group': group_id,
        'selected_date': date,
        'selected_status': status,
        'status_choices': Attendance.ATTENDANCE_STATUS
    })

@login_required
def attendance_add(request):
    if request.method == 'POST':
        student_id = request.POST.get('student')
        group_id = request.POST.get('group')
        date = request.POST.get('date')
        time = request.POST.get('time')
        status = request.POST.get('status')
        note = request.POST.get('note')
        
        Attendance.objects.create(
            student_id=student_id,
            group_id=group_id,
            date=date,
            time=time,
            status=status,
            note=note,
            marked_by=request.user
        )
        
        messages.success(request, "Davomat muvaffaqiyatli kiritildi")
        return redirect('app:attendance_list')
    
    students = Student.objects.select_related('user').all()
    groups = Group.objects.filter(active=True)
    
    return render(request, 'attendance/add.html', {
        'students': students,
        'groups': groups,
        'status_choices': Attendance.ATTENDANCE_STATUS
    })

@login_required
def attendance_detail(request, pk):
    attendance = get_object_or_404(
        Attendance.objects.select_related('student__user', 'group', 'marked_by'),
        pk=pk
    )
    return render(request, 'attendance/detail.html', {'attendance': attendance})

@login_required
def group_attendance(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    date = request.GET.get('date', datetime.now().date())
    
    attendances = Attendance.objects.filter(
        group=group,
        date=date
    ).select_related('student__user')
    
    # Get all students in the group
    students = group.students.select_related('user').all()
    
    # Create a dictionary of attendance records
    attendance_dict = {att.student_id: att for att in attendances}
    
    # Combine with students who don't have attendance records
    attendance_data = []
    for student in students:
        attendance_data.append({
            'student': student,
            'attendance': attendance_dict.get(student.id)
        })
    
    return render(request, 'attendance/group.html', {
        'group': group,
        'date': date,
        'attendance_data': attendance_data,
        'status_choices': Attendance.ATTENDANCE_STATUS
    })

@login_required
def student_attendance(request, student_id):
    student = get_object_or_404(Student.objects.select_related('user'), pk=student_id)
    
    # Filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    group_id = request.GET.get('group')
    
    # Base queryset
    attendances = Attendance.objects.filter(student=student)
    
    # Apply filters
    if start_date:
        attendances = attendances.filter(date__gte=start_date)
    if end_date:
        attendances = attendances.filter(date__lte=end_date)
    if group_id:
        attendances = attendances.filter(group_id=group_id)
    
    # Get student's groups for filter
    groups = student.groups.all()
    
    return render(request, 'attendance/student.html', {
        'student': student,
        'attendances': attendances,
        'groups': groups,
        'selected_group': group_id,
        'start_date': start_date,
        'end_date': end_date
    })

@login_required
def process_attendance(request):
    if not request.method == 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    group_id = request.POST.get('group_id')
    image_data = request.POST.get('image_data')
    
    if not all([group_id, image_data]):
        return JsonResponse({'success': False, 'error': 'Missing required data'})
    
    try:
        # Process the attendance using face recognition
        results = process_attendance_image(image_data, group_id)
        
        # Save attendance records
        now = datetime.now()
        for result in results:
            Attendance.objects.create(
                student=result['student'],
                group_id=group_id,
                date=now.date(),
                time=now.time(),
                status='present',
                face_confidence=result['confidence'],
                marked_by=request.user
            )
        
        return JsonResponse({
            'success': True,
            'detected_count': len(results),
            'message': f"{len(results)} ta o'quvchi aniqlandi"
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def department_report(request):
    departments = Department.objects.all()
    department_stats = []
    
    for dept in departments:
        groups = dept.groups.all()
        total_students = Student.objects.filter(groups__in=groups).distinct().count()
        total_attendance = Attendance.objects.filter(group__in=groups).count()
        present_attendance = Attendance.objects.filter(
            group__in=groups,
            status='present'
        ).count()
        
        attendance_rate = (present_attendance / total_attendance * 100) if total_attendance > 0 else 0
        
        department_stats.append({
            'department': dept,
            'group_count': groups.count(),
            'student_count': total_students,
            'attendance_rate': round(attendance_rate, 1)
        })
    
    return render(request, 'reports/department.html', {
        'department_stats': department_stats
    })

@login_required
def group_report(request):
    groups = Group.objects.all()
    group_stats = []
    
    for group in groups:
        total_students = group.students.count()
        total_attendance = Attendance.objects.filter(group=group).count()
        present_attendance = Attendance.objects.filter(
            group=group,
            status='present'
        ).count()
        
        attendance_rate = (present_attendance / total_attendance * 100) if total_attendance > 0 else 0
        
        group_stats.append({
            'group': group,
            'student_count': total_students,
            'attendance_rate': round(attendance_rate, 1),
            'department': group.department.name
        })
    
    return render(request, 'reports/group.html', {
        'group_stats': group_stats
    })

@login_required
def student_report(request):
    students = Student.objects.select_related('user').all()
    student_stats = []
    
    for student in students:
        total_classes = Attendance.objects.filter(student=student).count()
        present_count = Attendance.objects.filter(
            student=student,
            status='present'
        ).count()
        
        attendance_rate = (present_count / total_classes * 100) if total_classes > 0 else 0
        
        student_stats.append({
            'student': student,
            'total_classes': total_classes,
            'present_count': present_count,
            'attendance_rate': round(attendance_rate, 1)
        })
    
    return render(request, 'reports/student.html', {
        'student_stats': student_stats
    })

@login_required
def export_report(request):
    report_type = request.GET.get('type', 'attendance')
    format = request.GET.get('format', 'excel')
    
    if report_type == 'attendance':
        data = Attendance.objects.values(
            'date', 'time', 'status',
            'student__user__first_name', 'student__user__last_name',
            'group__name', 'marked_by__username'
        )
    elif report_type == 'student':
        data = Student.objects.values(
            'user__first_name', 'user__last_name', 'student_id',
            'groups__name'
        )
    else:
        return HttpResponse('Invalid report type')
    
    if format == 'excel':
        df = pd.DataFrame(list(data))
        
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_report.xlsx"'
        
        df.to_excel(response, index=False)
        return response
    
    return HttpResponse('Format not supported')

# HTMX API endpoints
@login_required
def mark_attendance(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        group_id = request.POST.get('group_id')
        status = request.POST.get('status')
        date = request.POST.get('date', datetime.now().date())
        
        attendance, created = Attendance.objects.update_or_create(
            student_id=student_id,
            group_id=group_id,
            date=date,
            defaults={
                'status': status,
                'time': datetime.now().time(),
                'marked_by': request.user
            }
        )
        
        status_class = "bg-green-100 text-green-800" if status == "present" else "bg-red-100 text-red-800"
        status_text = dict(Attendance.ATTENDANCE_STATUS)[status]
        return HttpResponse(
            f'<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_class}">'
            f'{status_text}</span>'
        )
    
    return HttpResponse('Invalid request')

@login_required
def filter_groups(request):
    department_id = request.GET.get('department')
    if department_id:
        groups = Group.objects.filter(department_id=department_id, active=True)
    else:
        groups = Group.objects.filter(active=True)
    
    return render(request, 'partials/group_options.html', {'groups': groups})

@login_required
def filter_students(request):
    group_id = request.GET.get('group')
    if group_id:
        students = Student.objects.filter(groups__id=group_id)
    else:
        students = Student.objects.all()
    
    return render(request, 'partials/student_options.html', {'students': students})

@login_required
def user_profile(request):
    user = request.user
    context = {
        'title': 'Profile',
        'user': user
    }
    
    if request.method == 'POST':
        # Handle profile updates here if needed
        pass
        
    return render(request, 'auth/profile.html', context)

@login_required
def teacher_list(request):
    teachers = CustomUser.objects.filter(user_type='teacher')
    return render(request, 'teachers/list.html', {'teachers': teachers})

@login_required
def teacher_add(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        
        teacher = CustomUser.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            user_type='teacher'
        )
        
        messages.success(request, "O'qituvchi muvaffaqiyatli qo'shildi")
        return redirect('app:teacher_list')
    
    return render(request, 'teachers/add.html')

@login_required
def teacher_detail(request, pk):
    teacher = get_object_or_404(CustomUser.objects.filter(user_type='teacher'), pk=pk)
    groups = Group.objects.filter(teacher=teacher)
    
    return render(request, 'teachers/detail.html', {
        'teacher': teacher,
        'groups': groups
    })

@login_required
def teacher_edit(request, pk):
    teacher = get_object_or_404(CustomUser.objects.filter(user_type='teacher'), pk=pk)
    if request.method == 'POST':
        teacher.first_name = request.POST.get('first_name')
        teacher.last_name = request.POST.get('last_name')
        teacher.email = request.POST.get('email')
        teacher.phone_number = request.POST.get('phone_number')
        
        if request.POST.get('password'):
            teacher.set_password(request.POST.get('password'))
            
        teacher.save()
        messages.success(request, "O'qituvchi ma'lumotlari muvaffaqiyatli yangilandi")
        return redirect('app:teacher_list')
    
    return render(request, 'teachers/edit.html', {'teacher': teacher})

@login_required
def teacher_delete(request, pk):
    teacher = get_object_or_404(CustomUser.objects.filter(user_type='teacher'), pk=pk)
    if request.method == 'POST':
        teacher.delete()
        messages.success(request, "O'qituvchi muvaffaqiyatli o'chirildi")
        return redirect('app:teacher_list')
    return render(request, 'teachers/delete.html', {'teacher': teacher})

# Camera management views
@login_required
def camera_list(request):
    cameras = Camera.objects.prefetch_related('groups').all()
    return render(request, 'cameras/list.html', {'cameras': cameras})

@login_required
def camera_add(request):
    if request.method == 'POST':
        camera = Camera.objects.create(
            name=request.POST.get('name'),
            ip_address=request.POST.get('ip_address'),
            location=request.POST.get('location'),
            username=request.POST.get('username'),
            password=request.POST.get('password'),
            active=request.POST.get('active') == 'on'
        )
        # Add groups
        group_ids = request.POST.getlist('groups')
        camera.groups.set(group_ids)
        
        messages.success(request, "Yangi kamera muvaffaqiyatli qo'shildi")
        return redirect('app:camera_list')
    
    groups = Group.objects.filter(active=True)
    return render(request, 'cameras/edit.html', {'groups': groups})

@login_required
def camera_edit(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    
    if request.method == 'POST':
        camera.name = request.POST.get('name')
        camera.ip_address = request.POST.get('ip_address')
        camera.location = request.POST.get('location')
        camera.username = request.POST.get('username')
        camera.password = request.POST.get('password')
        camera.active = request.POST.get('active') == 'on'
        camera.save()
        
        # Update groups
        group_ids = request.POST.getlist('groups')
        camera.groups.set(group_ids)
        
        messages.success(request, "Kamera ma'lumotlari muvaffaqiyatli yangilandi")
        return redirect('app:camera_list')
    
    groups = Group.objects.filter(active=True)
    return render(request, 'cameras/edit.html', {
        'camera': camera,
        'groups': groups
    })

@login_required
def camera_toggle(request, pk):
    if request.method == 'POST':
        camera = get_object_or_404(Camera, pk=pk)
        camera.active = not camera.active
        camera.save()
        
        status = "yoqildi" if camera.active else "o'chirildi"
        messages.success(request, f"Kamera muvaffaqiyatli {status}")
    
    return redirect('app:camera_list')

@login_required
def camera_test(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    
    try:
        import cv2
        import matplotlib.pyplot as plt
        import numpy as np
        cap = cv2.VideoCapture(camera.http_url)
        if not cap.isOpened():
            raise Exception("Could not connect to camera")
        
        ret, frame = cap.read()
        if not ret:
            raise Exception("Could not read frame from camera")
        
        cap.release()
        
        camera.last_status = 'online'
        camera.last_checked = timezone.now()
        camera.save()
        # Matplotlib orqali tasvirni ko‘rsatish (faqat lokal test uchun)
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            plt.imshow(frame_rgb)
            plt.title(f"{camera.name} - Test Frame")
            plt.axis('off')
            plt.show()
        except Exception as e:
            print(e)
        messages.success(request, "Kamera test qilindi va ishlayotgani tasdiqlandi")
    except Exception as e:
        camera.last_status = 'offline'
        camera.last_checked = timezone.now()
        camera.save()
        messages.error(request, f"Kamera test qilishda xatolik: {str(e)}")
    
    return redirect('app:camera_list')

@login_required
def camera_delete(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    if request.method == 'POST':
        camera.delete()
        messages.success(request, "Kamera muvaffaqiyatli o'chirildi")
        return redirect('app:camera_list')
    return render(request, 'cameras/delete.html', {'camera': camera})
